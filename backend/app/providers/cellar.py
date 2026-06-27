from __future__ import annotations

import re
from abc import ABC, abstractmethod
from functools import lru_cache

from app.config import settings
from app.providers.base import ProviderError, RetryableError

# Live EU Cellar connector for the citation-support signal (architecture.md §7.1, §9). It resolves a
# CELEX to a real source document so the support check runs against actual EU law, not just the
# seeded fixtures. Behind a factory like the LLM provider: the Null impl keeps the stack offline by
# default; the Http impl is only built when CELLAR_ENABLED. Returns a corpus-doc-shaped dict on a
# hit, None on authoritative absence (genuine fabrication), and RAISES on transient failure — so an
# outage is never mistaken for a fabricated citation (architecture.md §14.1).


def _celex_kind(celex: str) -> str:
    """Map a CELEX to a corpus `kind`. The first character is the document sector: sector 6 is the
    EU courts (case law); everything else we treat as legislation for this corpus."""
    return "case_law" if celex[:1] == "6" else "legislation"


_TAG_RE = re.compile(r"<[^>]+>")
_WS_RE = re.compile(r"[ \t\f\v]+")
_BLANKLINES_RE = re.compile(r"\n\s*\n\s*\n+")
_TITLE_RE = re.compile(r"<title[^>]*>(.*?)</title>", re.IGNORECASE | re.DOTALL)


def _strip_html(html: str) -> tuple[str, str | None]:
    """Best-effort HTML → (plain text, title). No extra deps; mirrors the best-effort plain-text
    extraction used for document upload (no OCR, no rich parsing)."""
    title_match = _TITLE_RE.search(html)
    title = _TAG_RE.sub("", title_match.group(1)).strip() if title_match else None
    # Drop script/style blocks wholesale before stripping the remaining tags.
    body = re.sub(r"<(script|style)[^>]*>.*?</\1>", " ", html, flags=re.IGNORECASE | re.DOTALL)
    body = re.sub(r"<br\s*/?>", "\n", body, flags=re.IGNORECASE)
    body = re.sub(r"</(p|div|li|tr|h[1-6])>", "\n", body, flags=re.IGNORECASE)
    text = _TAG_RE.sub("", body)
    text = re.sub(r"&nbsp;", " ", text)
    text = _WS_RE.sub(" ", text)
    text = _BLANKLINES_RE.sub("\n\n", text)
    return text.strip(), title


class CellarConnector(ABC):
    """The single seam citation lookups fall through to on a corpus miss. Orchestration depends only
    on this interface; swapping Null <-> Http is config-driven (CELLAR_ENABLED)."""

    @abstractmethod
    def fetch_by_celex(self, celex: str) -> dict | None:
        """Return a corpus-doc-shaped dict on a hit, None on authoritative absence, or raise
        (RetryableError / ProviderError) on transient failure."""
        raise NotImplementedError


class NullCellarConnector(CellarConnector):
    """Default. Always reports absence so the stack stays fully offline and tests never hit the
    network. With this active, behaviour is identical to fixtures-only (the pre-connector world)."""

    def fetch_by_celex(self, celex: str) -> dict | None:
        return None


class HttpCellarConnector(CellarConnector):
    """Fetches a document by CELEX from the EU Publications Office via REST content negotiation.
    httpx is lazy-imported (like the Anthropic provider lazy-imports its SDK) so the mock/offline
    path never needs it at import time. A `client` may be injected for offline testing."""

    def __init__(self, client=None) -> None:
        self._base = settings.CELLAR_BASE_URL.rstrip("/")
        self._lang = settings.CELLAR_LANGUAGE
        self._timeout = settings.CELLAR_TIMEOUT
        self._client = client  # tests inject an httpx.Client backed by MockTransport

    def _get_client(self):
        if self._client is None:
            import httpx  # lazy: only when live mode is actually used

            self._client = httpx.Client(timeout=self._timeout, follow_redirects=True)
        return self._client

    def fetch_by_celex(self, celex: str) -> dict | None:
        import httpx

        url = f"{self._base}/resource/celex/{celex}"
        headers = {
            "Accept": "application/xhtml+xml, text/html;q=0.9, text/plain;q=0.8",
            "Accept-Language": self._lang,
        }
        try:
            resp = self._get_client().get(url, headers=headers)
        except httpx.HTTPError as e:  # timeout / connection / transport — transient
            raise RetryableError(f"EU Cellar unreachable for {celex}: {e}") from e

        if resp.status_code in (404, 406):
            # 404: no such CELEX. 406: nothing satisfies the language/format request — treat the
            # document as not retrievable rather than fabricated-but-asserted.
            return None
        if resp.status_code >= 500:
            raise RetryableError(f"EU Cellar {resp.status_code} for {celex}")
        if resp.status_code != 200:
            raise ProviderError(f"EU Cellar {resp.status_code} for {celex}")

        text, title = _strip_html(resp.text)
        if not text:
            # A document with no extractable text is no more verifiable than an absent one.
            return None
        return {
            "celex": celex,
            "title": title or f"EU document {celex}",
            "kind": _celex_kind(celex),
            "source_url": url,
            "text": text,
            "case_id": None,
        }


@lru_cache
def get_cellar() -> CellarConnector:
    """Null unless CELLAR_ENABLED. Cached so the live client is reused across checks in a run."""
    if not settings.CELLAR_ENABLED:
        return NullCellarConnector()
    return HttpCellarConnector()
