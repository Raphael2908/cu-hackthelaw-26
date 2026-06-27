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


# --- HttpCellarConnector parsing (offline via MockTransport) -------------------------------------


def _http(handler) -> HttpCellarConnector:
    return HttpCellarConnector(client=httpx.Client(transport=httpx.MockTransport(handler)))


def test_http_parses_text_title_and_kind():
    html = (
        "<html><head><title>Rome I Regulation</title></head>"
        "<body><p>Article 3</p><p>Freedom of choice.</p></body></html>"
    )

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path.endswith("/resource/celex/32008R0593")
        assert request.headers["accept-language"] == "en"
        return httpx.Response(200, text=html, headers={"content-type": "application/xhtml+xml"})

    doc = _http(handler).fetch_by_celex("32008R0593")
    assert doc is not None
    assert doc["celex"] == "32008R0593"
    assert doc["title"] == "Rome I Regulation"
    assert "Freedom of choice." in doc["text"]
    assert "<p>" not in doc["text"]  # markup stripped
    assert doc["kind"] == "legislation"
    assert doc["source_url"].endswith("/resource/celex/32008R0593")


def test_http_sector_6_is_case_law():
    handler = lambda r: httpx.Response(200, text="<html><body>Judgment of the Court.</body></html>")  # noqa: E731
    doc = _http(handler).fetch_by_celex("62018CJ0311")
    assert doc is not None and doc["kind"] == "case_law"


def test_http_404_and_406_are_absence():
    for code in (404, 406):
        doc = _http(lambda r, c=code: httpx.Response(c)).fetch_by_celex("99999X9999")
        assert doc is None


def test_http_empty_document_is_absence():
    handler = lambda r: httpx.Response(200, text="<html><body>   </body></html>")  # noqa: E731
    assert _http(handler).fetch_by_celex("32008R0593") is None


def test_http_5xx_raises_retryable():
    with pytest.raises(RetryableError):
        _http(lambda r: httpx.Response(503)).fetch_by_celex("32008R0593")


def test_http_4xx_raises_provider_error():
    with pytest.raises(ProviderError):
        _http(lambda r: httpx.Response(403)).fetch_by_celex("32008R0593")


def test_http_connection_error_raises_retryable():
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("connection refused")

    with pytest.raises(RetryableError):
        _http(handler).fetch_by_celex("32008R0593")
