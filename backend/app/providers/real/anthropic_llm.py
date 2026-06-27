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
                max_tokens=2048,
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

    def review_document(
        self, *, draft: dict, firm_standard: dict, process_section: str, run_index: int = 0
    ) -> ReviewResult:
        user = (
            f"PROCESS SECTION: {process_section}\n\nFIRM STANDARD:\n{firm_standard['text']}\n\n"
            f"DRAFT ({draft['title']}):\n{draft['text']}\n\n(variation seed: {run_index})"
        )
        data = self._complete_json(_REVIEW_SYS, user)
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
            "the plan tracks the actual process rather than a fixed template. Choose assignee_type "
            "(human|ai|hybrid) from the section's risk — higher-risk binding obligations lean "
            "human or hybrid. Bind target_document_id to one of the supplied DOCUMENTS. Return "
            'STRICT JSON {"tasks": [...]} where each task has title, description, task_type, '
            "assignee_type, target_document_id, input_brief_slice, ai_instruction|null. The plan "
            "is a proposal — severity is set by the partner, not here."
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
            max_tokens=2048,
            system=sys,
            messages=[{"role": "user", "content": user}],
        )
        return "".join(b.text for b in msg.content if getattr(b, "type", None) == "text")
