from __future__ import annotations

import httpx
import pytest

from app.db.tables import CORPUS, TASKS
from app.providers.base import ProviderError, RetryableError
from app.providers.cellar import CellarConnector, HttpCellarConnector
from app.services import checker, worker

# The worker's mock review of this draft cites CELEX 32020R9999, which is NOT in the seeded corpus —
# i.e. fabricated as far as fixtures are concerned. With a live Cellar connector that CELEX can be
# resolved, which is exactly what these tests exercise. All offline: a fake connector is injected
# into citation_support, and the HTTP impl is driven by httpx.MockTransport — never the network.

FABRICATED_CELEX = "32020R9999"
GOVLAW_CLAIM = "parties may freely select the governing law of a contract"


class FakeCellar(CellarConnector):
    """Injectable stand-in: returns a fixed doc, returns None (absence), or raises (outage)."""

    def __init__(self, *, result: dict | None = None, exc: Exception | None = None) -> None:
        self._result = result
        self._exc = exc
        self.calls: list[str] = []

    def fetch_by_celex(self, celex: str) -> dict | None:
        self.calls.append(celex)
        if self._exc is not None:
            raise self._exc
        return self._result


def _govlaw_submission(repo, provider):
    task = repo.insert(
        TASKS,
        {
            "case_id": "case-x",
            "plan_id": "plan-x",
            "target_document_id": "draft-govlaw-atlas",
            "task_type": "review_governing_law",
            "assignee_type": "ai",
            "severity": "medium",
            "input_process_section": "test",
            "status": "submitted",
            "title": "draft-govlaw-atlas",
        },
    )
    sub = worker.run_review(repo, task=task, provider=provider)
    return task, sub


# --- checker integration -------------------------------------------------------------------------


def test_cellar_hit_resolves_and_caches_the_source(in_memory_repo, provider):
    """A live hit turns a fixtures-fabricated CELEX into a real, supported citation — no fabricated
    flag — and the fetched doc is cached into the corpus (resolvable via GET /api/corpus/{id})."""
    repo = in_memory_repo
    task, sub = _govlaw_submission(repo, provider)
    fake = FakeCellar(
        result={
            "celex": FABRICATED_CELEX,
            "title": "Rome I (fetched)",
            "kind": "legislation",
            "source_url": f"http://publications.europa.eu/resource/celex/{FABRICATED_CELEX}",
            "text": "Article 3 — freedom of choice of governing law.",
            "case_id": None,
            "ground_truth": {"supported_claims": [GOVLAW_CLAIM]},
        }
    )
    res = checker.citation_support(repo, task, sub, provider, fake)

    assert fake.calls == [FABRICATED_CELEX]  # consulted only on the local miss
    assert not any("Fabricated" in f["title"] for f in res["flags"])
    assert res["rate"] == 1.0  # the support check ran against the fetched doc and passed
    cached = checker._corpus_by_celex(repo, FABRICATED_CELEX)
    assert cached is not None and repo.get(CORPUS, cached["id"]) is not None  # one-click resolvable


def test_cellar_absence_keeps_the_hard_fabricated_flag(in_memory_repo, provider):
    repo = in_memory_repo
    task, sub = _govlaw_submission(repo, provider)
    fake = FakeCellar(result=None)  # Cellar authoritatively reports no such CELEX
    res = checker.citation_support(repo, task, sub, provider, fake)

    flag = next(f for f in res["flags"] if "Fabricated" in f["title"])
    assert flag["hard"] is True
    assert flag["source_ref"]["exists"] is False
    assert res["rate"] < 1.0  # genuine fabrication lowers the rate


def test_cellar_outage_is_soft_unverifiable_not_fabrication(in_memory_repo, provider):
    """A transient failure must never read as fabrication (architecture.md §14.1): soft flag, and
    the claim drops out of the support-rate denominator instead of scoring as unsupported."""
    repo = in_memory_repo
    task, sub = _govlaw_submission(repo, provider)
    fake = FakeCellar(exc=RetryableError("EU Cellar unreachable"))
    res = checker.citation_support(repo, task, sub, provider, fake)

    assert not any("Fabricated" in f["title"] for f in res["flags"])
    flag = next(f for f in res["flags"] if f["signal_type"] == "citation_support")
    assert flag["hard"] is False
    assert "unverifiable" in flag["title"].lower()
    assert flag["source_ref"]["exists"] is None
    assert res["n_unverifiable"] == 1
    assert res["rate"] == 1.0  # the only citation was excluded, not counted as a failure


# --- HttpCellarConnector: official API (content negotiation + SPARQL), offline via MockTransport --
# fetch_by_celex makes up to two calls — the content GET (resource/celex) and a best-effort SPARQL
# metadata GET — so handlers route by path. _NO_META is the default empty SPARQL result.

_NO_META = {"results": {"bindings": []}}


def _http(*, content, sparql=None) -> HttpCellarConnector:
    """Build a connector whose client routes content vs SPARQL requests to separate handlers."""

    def handler(request: httpx.Request) -> httpx.Response:
        if "/webapi/rdf/sparql" in request.url.path:
            return (sparql or (lambda r: httpx.Response(200, json=_NO_META)))(request)
        return content(request)

    return HttpCellarConnector(client=httpx.Client(transport=httpx.MockTransport(handler)))


def test_http_parses_xhtml_to_clean_text():
    xhtml = (
        '<html xmlns="http://www.w3.org/1999/xhtml"><head><title>Rome I Regulation</title></head>'
        "<body><p>Article 3</p><p>Freedom of choice.</p></body></html>"
    )

    def content(request: httpx.Request) -> httpx.Response:
        assert request.url.path.endswith("/resource/celex/32008R0593")
        assert request.headers["accept-language"] == "en"
        assert "xhtml" in request.headers["accept"]
        assert request.headers["user-agent"].startswith("supervision-cockpit")
        return httpx.Response(200, text=xhtml, headers={"content-type": "application/xhtml+xml"})

    doc = _http(content=content).fetch_by_celex("32008R0593")
    assert doc is not None
    assert doc["title"] == "Rome I Regulation"  # no SPARQL title → falls back to the XML <title>
    assert "Freedom of choice." in doc["text"]
    assert "<p>" not in doc["text"]  # markup stripped
    assert "Rome I Regulation" not in doc["text"]  # title not duplicated into the body
    assert doc["kind"] == "legislation"
    assert doc["source_url"].endswith("/resource/celex/32008R0593")


def test_http_parses_formex_xml_by_same_path():
    # Pre-2014 docs come back as Formex (a different XML schema) — the namespace-agnostic walk
    # handles it with no schema-specific code.
    formex = (
        '<ACT xmlns="http://formex.publications.europa.eu"><TITLE><P>Directive 90/314</P></TITLE>'
        "<ENACTING.TERMS><ARTICLE><P>Package travel obligations apply.</P></ARTICLE>"
        "</ENACTING.TERMS></ACT>"
    )
    doc = _http(content=lambda r: httpx.Response(200, text=formex)).fetch_by_celex("31990L0314")
    assert doc is not None
    assert "Package travel obligations apply." in doc["text"]
    assert doc["title"] == "EU document 31990L0314"  # no <title> element, no SPARQL → fallback


def test_http_sparql_title_takes_precedence():
    xhtml = "<html><head><title>scraped</title></head><body><p>body text</p></body></html>"
    meta = {"results": {"bindings": [{"title": {"value": "Official SPARQL Title"}}]}}
    doc = _http(
        content=lambda r: httpx.Response(200, text=xhtml),
        sparql=lambda r: httpx.Response(200, json=meta),
    ).fetch_by_celex("32008R0593")
    assert doc is not None and doc["title"] == "Official SPARQL Title"


def test_http_sparql_type_refines_kind_to_case_law():
    # Sector 3 would default to legislation, but the SPARQL resource-type says it's a judgment.
    meta = {"results": {"bindings": [{"type": {"value": ".../resource-type/JUDG"}}]}}
    doc = _http(
        content=lambda r: httpx.Response(200, text="<html><body><p>text</p></body></html>"),
        sparql=lambda r: httpx.Response(200, json=meta),
    ).fetch_by_celex("32008R0593")
    assert doc is not None and doc["kind"] == "case_law"


def test_http_malformed_xml_falls_back_to_regex():
    # Unescaped & makes this invalid XML → the connector falls back to the regex strip rather than
    # losing the document.
    bad = "<html><body><p>freedom & choice of law</p></body></html>"
    doc = _http(content=lambda r: httpx.Response(200, text=bad)).fetch_by_celex("32008R0593")
    assert doc is not None and "freedom & choice of law" in doc["text"]


def test_http_sector_6_is_case_law():
    def content(r):
        return httpx.Response(200, text="<html><body><p>Judgment of the Court.</p></body></html>")

    doc = _http(content=content).fetch_by_celex("62018CJ0311")
    assert doc is not None and doc["kind"] == "case_law"


def test_http_404_and_406_are_absence():
    for code in (404, 406):
        doc = _http(content=lambda r, c=code: httpx.Response(c)).fetch_by_celex("99999X9999")
        assert doc is None


def test_http_empty_document_is_absence():
    content = lambda r: httpx.Response(200, text="<html><body>   </body></html>")  # noqa: E731
    assert _http(content=content).fetch_by_celex("32008R0593") is None


def test_http_5xx_raises_retryable():
    with pytest.raises(RetryableError):
        _http(content=lambda r: httpx.Response(503)).fetch_by_celex("32008R0593")


def test_http_4xx_raises_provider_error():
    with pytest.raises(ProviderError):
        _http(content=lambda r: httpx.Response(403)).fetch_by_celex("32008R0593")


def test_http_connection_error_raises_retryable():
    def content(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("connection refused")

    with pytest.raises(RetryableError):
        _http(content=content).fetch_by_celex("32008R0593")


def test_http_sparql_failure_is_swallowed():
    # Metadata is non-essential: a SPARQL error must not fail the fetch — content still returns.
    doc = _http(
        content=lambda r: httpx.Response(200, text="<html><body><p>text</p></body></html>"),
        sparql=lambda r: httpx.Response(500),
    ).fetch_by_celex("32008R0593")
    assert doc is not None and doc["title"] == "EU document 32008R0593"


# --- Worker grounding (offline) ------------------------------------------------------------------


def _govlaw_task(repo):
    return repo.insert(
        TASKS,
        {
            "case_id": "case-x",
            "plan_id": "plan-x",
            "target_document_id": "draft-govlaw-atlas",
            "task_type": "review_governing_law",
            "assignee_type": "ai",
            "severity": "medium",
            "input_process_section": "test",
            "status": "approved",
            "title": "draft-govlaw-atlas",
        },
    )


def test_worker_source_lookup_caches_into_corpus(in_memory_repo, provider):
    """The worker's source_lookup resolves corpus-first, fetches on a miss, and caches the result so
    a second lookup (and the checker) is served from the corpus without another fetch."""
    repo = in_memory_repo
    new_celex = "32099R0001"
    fake = FakeCellar(
        result={
            "celex": new_celex,
            "title": "Fetched Reg",
            "kind": "legislation",
            "source_url": f"http://publications.europa.eu/resource/celex/{new_celex}",
            "text": "Real text.",
            "case_id": None,
        }
    )
    lookup = worker._make_source_lookup(repo, fake)

    first = lookup(new_celex)
    assert first is not None and first.get("id")  # inserted into the corpus
    assert checker._corpus_by_celex(repo, new_celex) is not None  # cached + one-click resolvable

    lookup(new_celex)  # served from the corpus now
    assert fake.calls == [new_celex]  # the connector was hit exactly once


def test_worker_offers_the_tool_only_when_cellar_enabled(in_memory_repo, provider):
    """Mock/offline path stays tool-free: source_lookup is only handed to the model when enabled."""
    from app.config import settings
    from app.providers.cellar import NullCellarConnector

    repo = in_memory_repo
    task = _govlaw_task(repo)

    class RecordingProvider(type(provider)):
        last_source_lookup = "unset"

        def review_document(self, *, source_lookup=None, **kw):
            self.last_source_lookup = source_lookup
            return super().review_document(source_lookup=source_lookup, **kw)

    rec = RecordingProvider()
    worker.run_review(repo, task=task, provider=rec, cellar=NullCellarConnector())
    assert rec.last_source_lookup is None  # disabled by default (conftest)

    settings.CELLAR_ENABLED = True
    try:
        worker.run_review(repo, task=task, provider=rec, cellar=NullCellarConnector())
        assert callable(rec.last_source_lookup)
    finally:
        settings.CELLAR_ENABLED = False
