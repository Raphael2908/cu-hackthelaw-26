from __future__ import annotations

import re
import xml.etree.ElementTree as ET
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
#
# We use the OFFICIAL machine-readable API, not HTML scraping:
#   - content: the CELLAR REST API via HTTP content negotiation — GET {base}/resource/celex/{CELEX}
#     with Accept: application/xhtml+xml selects the clean XHTML manifestation (Formex XML for
#     pre-2014 documents). Both are XML, so one namespace-agnostic parse handles them.
#   - metadata (title, type): the SPARQL endpoint over the CDM knowledge graph.
# Both are public (no auth). The regex strip below is only a defensive fallback if XML parse fails.


def _celex_kind(celex: str) -> str:
    """Map a CELEX to a corpus `kind`. The first character is the document sector: sector 6 is the
    EU courts (case law); everything else we treat as legislation for this corpus."""
    return "case_law" if celex[:1] == "6" else "legislation"


def _refine_kind(celex: str, type_uri: str | None) -> str:
    """Refine the sector-derived kind with the SPARQL resource-type when present; otherwise keep the
    sector default (which needs no network call)."""
    if type_uri and any(k in type_uri.upper() for k in ("JUDG", "ORDER", "OPIN_JUR")):
        return "case_law"
    return _celex_kind(celex)


_TAG_RE = re.compile(r"<[^>]+>")
_WS_RE = re.compile(r"[ \t\f\v]+")
_BLANKLINES_RE = re.compile(r"\n\s*\n\s*\n+")
_TITLE_RE = re.compile(r"<title[^>]*>(.*?)</title>", re.IGNORECASE | re.DOTALL)


def _local(tag: str) -> str:
    """Strip the `{namespace}` prefix ElementTree puts on tags."""
    return tag.rsplit("}", 1)[-1].lower()


def _xml_to_text(payload: str) -> tuple[str, str | None]:
    """Parse an XHTML or Formex manifestation namespace-agnostically into (plain text, title).
    Raises ET.ParseError on malformed XML so the caller can fall back to the regex strip."""
    root = ET.fromstring(payload)
    skip = {"script", "style", "head", "title"}  # title is captured separately, not body text
    title: str | None = None
    parts: list[str] = []
    for el in root.iter():
        name = _local(el.tag)
        if name == "title" and title is None and el.text and el.text.strip():
            title = el.text.strip()
        if name in skip:
            continue
        if el.text and el.text.strip():
            parts.append(el.text.strip())
        if el.tail and el.tail.strip():
            parts.append(el.tail.strip())
    text = _BLANKLINES_RE.sub("\n\n", "\n".join(parts)).strip()
    return text, title


def _strip_html(html: str) -> tuple[str, str | None]:
    """Defensive fallback when XML parsing fails: best-effort HTML → (plain text, title)."""
    title_match = _TITLE_RE.search(html)
    title = _TAG_RE.sub("", title_match.group(1)).strip() if title_match else None
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
    """Fetches a document by CELEX from the EU Publications Office via the official CELLAR REST API
    (content negotiation) + SPARQL for metadata. httpx is lazy-imported (like the Anthropic provider
    lazy-imports its SDK) so the mock/offline path never needs it. A `client` may be injected for
    offline testing."""

    def __init__(self, client=None) -> None:
        self._base = settings.CELLAR_BASE_URL.rstrip("/")
        self._lang = settings.CELLAR_LANGUAGE
        self._timeout = settings.CELLAR_TIMEOUT
        self._sparql = f"{self._base}{settings.CELLAR_SPARQL_PATH}"
        self._ua = settings.CELLAR_USER_AGENT
        self._client = client  # tests inject an httpx.Client backed by MockTransport

    def _get_client(self):
        if self._client is None:
            import httpx  # lazy: only when live mode is actually used

            self._client = httpx.Client(timeout=self._timeout, follow_redirects=True)
        return self._client

    def _fetch_metadata(self, celex: str) -> tuple[str | None, str | None]:
        """Best-effort (title, resource-type URI) from the SPARQL knowledge graph. Never raises —
        metadata is non-essential; a failure just leaves the sector-derived kind and a fallback
        title. This is what replaces scraping the document's <title>."""
        import httpx

        query = (
            "PREFIX cdm: <http://publications.europa.eu/ontology/cdm#> "
            "SELECT ?title ?type WHERE { "
            "?work cdm:resource_legal_id_celex ?celex . "
            f'FILTER(STR(?celex) = "{celex}") '
            "OPTIONAL { ?work cdm:work_has_resource-type ?type . } "
            "OPTIONAL { ?exp cdm:expression_belongs_to_work ?work ; "
            "cdm:expression_title ?title . } "
            "} LIMIT 1"
        )
        try:
            resp = self._get_client().get(
                self._sparql,
                params={"query": query},
                headers={"Accept": "application/sparql-results+json", "User-Agent": self._ua},
            )
            if resp.status_code != 200:
                return None, None
            bindings = resp.json().get("results", {}).get("bindings", [])
        except (httpx.HTTPError, ValueError):
            return None, None
        if not bindings:
            return None, None
        b = bindings[0]
        return b.get("title", {}).get("value"), b.get("type", {}).get("value")

    def fetch_by_celex(self, celex: str) -> dict | None:
        import httpx

        url = f"{self._base}/resource/celex/{celex}"
        headers = {
            "Accept": "application/xhtml+xml, application/xml;q=0.9, text/html;q=0.5",
            "Accept-Language": self._lang,
            "User-Agent": self._ua,
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

        try:
            text, xml_title = _xml_to_text(resp.text)  # handles XHTML and Formex
        except ET.ParseError:
            text, xml_title = _strip_html(resp.text)  # defensive: not well-formed XML
        if not text:
            # A document with no extractable text is no more verifiable than an absent one.
            return None

        sparql_title, type_uri = self._fetch_metadata(celex)
        return {
            "celex": celex,
            "title": sparql_title or xml_title or f"EU document {celex}",
            "kind": _refine_kind(celex, type_uri),
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
