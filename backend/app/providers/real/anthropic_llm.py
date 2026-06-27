from __future__ import annotations

import json

from app.config import settings
from app.providers.base import (
    CitationCheck,
    Deviation,
    FatalError,
    Finding,
    LLMProvider,
    ProviderError,
    RetryableError,
    ReviewResult,
)

# Real Claude implementation. Wired but not exercised by the demo (which runs on the mock). It is
# imported lazily by the factory only when PROVIDER_MODE=real, so the mock path never needs the SDK
# or a key. Prompts are intentionally minimal; tune them when going live (see todo.md).

_REVIEW_SYS = (
    "You are a legal document reviewer. Compare the DRAFT against the FIRM STANDARD and return "
    'STRICT JSON: {"summary": str, "clauses_relied_on": [str], "audit_sources": [str], '
    '"findings": [{"id": str, "clause_ref": str, "statement": str, '
    '"citation": {"celex": str, "claim": str} | null}]}. '
    "Surface checkable observations. Do NOT render a pass/fail verdict."
)

# Worker grounding: when a source lookup is supplied, the model can call this tool to fetch the real
# EU source by CELEX before citing it, reducing fabricated citations at the source (architecture.md
# §9, §13.1). The checker still does the authoritative citation-support verification afterwards.
_FETCH_TOOL = {
    "name": "fetch_eu_source",
    "description": (
        "Fetch the full text of an EU legal document by its CELEX identifier from EUR-Lex/Cellar. "
        "Use this to ground a citation in the real source before citing it. Returns the document "
        "text, or a not-found note if no such document exists."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "celex": {"type": "string", "description": "CELEX id, e.g. 32016R0679 or 62018CJ0311"}
        },
        "required": ["celex"],
    },
}
_MAX_TOOL_TURNS = 6  # bound the agentic loop so a misbehaving model can't fetch indefinitely
_TOOL_RESULT_CHARS = 20000  # cap a fetched source so it can't blow the context window


class AnthropicLLMProvider(LLMProvider):
    def __init__(self) -> None:
        if not settings.ANTHROPIC_API_KEY:
            raise FatalError("ANTHROPIC_API_KEY is required for PROVIDER_MODE=real.")
        import anthropic  # lazy: only when real mode is actually used

        self._client = anthropic.Anthropic(api_key=settings.ANTHROPIC_API_KEY)
        self._model = settings.ANTHROPIC_MODEL

    def _complete_json(self, system: str, user: str) -> dict:
        import anthropic

        try:
            msg = self._client.messages.create(
                model=self._model,
                max_tokens=32768,
                system=system,
                messages=[{"role": "user", "content": user}],
            )
        except anthropic.RateLimitError as e:  # pragma: no cover - real-mode only
            raise RetryableError(str(e)) from e
        except anthropic.APIStatusError as e:  # pragma: no cover
            raise (RetryableError if e.status_code >= 500 else FatalError)(str(e)) from e
        text = "".join(b.text for b in msg.content if getattr(b, "type", None) == "text")
        try:
            return json.loads(text)
        except json.JSONDecodeError as e:  # pragma: no cover
            raise ProviderError(f"Model did not return valid JSON: {text[:200]}") from e

    def _run_source_tool(self, source_lookup, celex: str) -> str:  # pragma: no cover - real-mode
        """Execute one fetch_eu_source call. A failed lookup never aborts the review — it returns a
        note so the model proceeds; the checker still verifies the citation authoritatively."""
        try:
            doc = source_lookup(celex)
        except ProviderError as e:
            return f"Source service unavailable for {celex}: {e}. Proceed without it."
        if not doc:
            return f"No EU document found for CELEX {celex}."
        return f"{doc.get('title', '')}\n\n{doc.get('text', '')}"[:_TOOL_RESULT_CHARS]

    def _complete_json_grounded(self, system: str, user: str, source_lookup) -> dict:
        """Tool-use loop: let the model fetch real sources by CELEX, then return STRICT JSON."""
        import anthropic  # pragma: no cover - real-mode only

        messages = [{"role": "user", "content": user}]
        for _ in range(_MAX_TOOL_TURNS):  # pragma: no cover - real-mode only
            try:
                msg = self._client.messages.create(
                    model=self._model,
                    max_tokens=32768,
                    system=system,
                    tools=[_FETCH_TOOL],
                    messages=messages,
                )
            except anthropic.RateLimitError as e:
                raise RetryableError(str(e)) from e
            except anthropic.APIStatusError as e:
                raise (RetryableError if e.status_code >= 500 else FatalError)(str(e)) from e

            if msg.stop_reason != "tool_use":
                text = "".join(b.text for b in msg.content if getattr(b, "type", None) == "text")
                try:
                    return json.loads(text)
                except json.JSONDecodeError as e:
                    raise ProviderError(f"Model did not return valid JSON: {text[:200]}") from e

            messages.append({"role": "assistant", "content": msg.content})
            results = [
                {
                    "type": "tool_result",
                    "tool_use_id": b.id,
                    "content": self._run_source_tool(source_lookup, b.input.get("celex", "")),
                }
                for b in msg.content
                if getattr(b, "type", None) == "tool_use" and b.name == _FETCH_TOOL["name"]
            ]
            messages.append({"role": "user", "content": results})
        raise ProviderError("Worker review exceeded the tool-use turn limit.")

    def review_document(
        self,
        *,
        draft: dict,
        firm_standard: dict,
        process_section: str,
        run_index: int = 0,
        source_lookup=None,
    ) -> ReviewResult:
        user = (
            f"PROCESS SECTION: {process_section}\n\nFIRM STANDARD:\n{firm_standard['text']}\n\n"
            f"DRAFT ({draft['title']}):\n{draft['text']}\n\n(variation seed: {run_index})"
        )
        if source_lookup is None:
            data = self._complete_json(_REVIEW_SYS, user)
        else:  # pragma: no cover - real-mode only
            data = self._complete_json_grounded(_REVIEW_SYS, user, source_lookup)
        return ReviewResult(
            summary=data.get("summary", ""),
            findings=[Finding(**f) for f in data.get("findings", [])],
            clauses_relied_on=data.get("clauses_relied_on", []),
            audit_sources=data.get("audit_sources", []),
        )

    def check_citation_support(self, *, claim: str, source: dict) -> CitationCheck:
        sys = (
            "Decide whether SOURCE supports CLAIM. Return STRICT JSON "
            '{"supported": bool, "rationale": str}.'
        )
        data = self._complete_json(sys, f"CLAIM: {claim}\n\nSOURCE:\n{source.get('text', '')}")
        return CitationCheck(bool(data.get("supported")), data.get("rationale", ""))

    def assess_deviations(self, *, draft: dict, firm_standard: dict) -> list[Deviation]:
        sys = (
            "List clauses in DRAFT that deviate from FIRM STANDARD. Return STRICT JSON "
            '{"deviations": [{"clause_ref": str, "standard_key": str, "draft_text": str, '
            '"score": float, "rationale": str}]}.'
        )
        user = f"FIRM STANDARD:\n{firm_standard['text']}\n\nDRAFT:\n{draft['text']}"
        data = self._complete_json(sys, user)
        return [Deviation(**d) for d in data.get("deviations", [])]

    def plan_case(
        self,
        *,
        goal: str,
        brief: str,
        process_doc: dict,
        drafts: list[dict],
        associates: list[dict],
    ) -> list[dict]:
        sys = (
            "Scope the GOAL into review tasks by DECOMPOSING the process doc: produce at least "
            "one task per applicable process-doc section (use the section key as task_type), so "
            "the plan tracks the actual process rather than a fixed template.\n\n"
            "Choose assignee_type (human|ai|hybrid) with the TRUST MATRIX. Read each task on two "
            "independent axes that are properties of the task's NATURE, never the matter's "
            "severity:\n"
            "  - STAKES = the consequence if THIS task's output is wrong. High for binding "
            "obligations and legal judgment (liability, indemnity, governing law, data transfer, "
            "anything a court relies on); low for mechanical/low-judgment work (grammar, a "
            "first-look data-room triage, summarising non-operative recitals/background).\n"
            "  - VERIFIABILITY = how cheaply a human can CHECK the output against an objective "
            "source. High when it can be checked against a citation, the firm standard, or a "
            "document already in hand; low when judging it needs experienced legal judgement with "
            "no objective scaffold to check against.\n"
            "The two axes give four modes — pick the assignee_type for the quadrant:\n"
            "  - High stakes, low verifiability -> RESERVE: 'human' (zero tolerance, no way to "
            "cheaply check — human judgement, checked by human judgement).\n"
            "  - High stakes, high verifiability -> AUGMENT: 'hybrid' (AI does the volume, a human "
            "verifies and signs off and OWNS the result).\n"
            "  - Low stakes, low verifiability -> MONITOR: 'ai' (let AI run; quality is held by "
            "downstream sampling, not a human on every item).\n"
            "  - Low stakes, high verifiability -> DELEGATE: 'ai' (AI runs end-to-end within the "
            "guardrails; errors are cheap and easy to catch).\n"
            "Tasks are rarely all-human or all-AI: when a task is high-stakes but checkable, "
            "prefer 'hybrid' over 'human' so AI carries the volume under human sign-off.\n\n"
            "Do NOT route by the matter's severity: severity is the partner's separate up-front "
            "triage dial, set elsewhere — a high-severity matter can still contain low-stakes, "
            "checkable tasks that are right for AI. Judge stakes per task, not per matter.\n\n"
            "Bind target_document_id to one of the supplied DOCUMENTS. Return STRICT JSON "
            '{"tasks": [...]} where each task has title, description, task_type, assignee_type, '
            "target_document_id, input_brief_slice, ai_instruction|null. The plan is a proposal — "
            "severity is set by the partner, not here."
        )
        types = json.dumps(process_doc.get("task_types", {}))
        docs = json.dumps([{"id": d["id"], "title": d["title"]} for d in drafts])
        user = f"GOAL: {goal}\n\nBRIEF: {brief}\n\nTASK TYPES: {types}\n\nDOCUMENTS: {docs}"
        return self._complete_json(sys, user).get("tasks", [])

    def generate_debrief(
        self, *, case: dict, tasks: list[dict], flags: list[dict], decisions: list[dict]
    ) -> str:
        sys = "Write a concise markdown debrief of the matter from the record provided."
        user = json.dumps(
            {"case": case, "tasks": tasks, "flags": flags, "decisions": decisions}, default=str
        )
        msg = self._client.messages.create(
            model=self._model,
            max_tokens=32768,
            system=sys,
            messages=[{"role": "user", "content": user}],
        )
        return "".join(b.text for b in msg.content if getattr(b, "type", None) == "text")
