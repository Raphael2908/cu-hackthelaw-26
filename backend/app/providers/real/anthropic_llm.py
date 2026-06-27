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


def _strip_fences(text: str) -> str:
    """Tolerate a model that wraps its JSON in a ```json … ``` markdown fence."""
    t = text.strip()
    if t.startswith("```"):
        t = t.split("\n", 1)[-1] if "\n" in t else t
        if t.endswith("```"):
            t = t[: -3]
        t = t.removeprefix("json").strip()
    return t.strip()


class AnthropicLLMProvider(LLMProvider):
    def __init__(self) -> None:
        if not settings.ANTHROPIC_API_KEY:
            raise FatalError("ANTHROPIC_API_KEY is required for PROVIDER_MODE=real.")
        import anthropic  # lazy: only when real mode is actually used

        self._client = anthropic.Anthropic(api_key=settings.ANTHROPIC_API_KEY)
        self._model = settings.ANTHROPIC_MODEL

    def _complete_text(self, system: str, user: str) -> str:
        """One streamed completion → accumulated text. Streaming (vs create) is required: the
        SDK refuses non-streaming requests whose max_tokens could run past its 10-minute ceiling,
        which a large ANTHROPIC_MAX_TOKENS does (see todo.md / config)."""
        import anthropic

        try:
            with self._client.messages.stream(
                model=self._model,
                max_tokens=settings.ANTHROPIC_MAX_TOKENS,
                system=system,
                messages=[{"role": "user", "content": user}],
            ) as stream:
                msg = stream.get_final_message()
        except anthropic.RateLimitError as e:  # pragma: no cover - real-mode only
            raise RetryableError(str(e)) from e
        except anthropic.APIStatusError as e:  # pragma: no cover
            raise (RetryableError if e.status_code >= 500 else FatalError)(str(e)) from e
        return "".join(b.text for b in msg.content if getattr(b, "type", None) == "text")

    def _complete_json(self, system: str, user: str) -> dict:
        text = self._complete_text(system, user)
        try:
            return json.loads(_strip_fences(text))
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
            'Scope the GOAL into review tasks. Return STRICT JSON {"tasks": [...]} where each task '
            "has title, description, task_type, assignee_type (human|ai|hybrid), "
            "target_document_id, input_brief_slice, ai_instruction|null. The plan is a proposal."
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
        return self._complete_text(sys, user)
