from __future__ import annotations

import re

from app import fixtures
from app.providers.base import (
    CitationCheck,
    Deviation,
    Finding,
    LLMProvider,
    TaskResult,
)

# Generic words that appear in most task titles — too low-signal to match a task by.
_REVISE_STOP = {
    "review",
    "clause",
    "clauses",
    "against",
    "standard",
    "document",
    "summarise",
    "background",
}


def _match_task(tasks: list[dict], feedback: str) -> int | None:
    """Index of the task whose title best overlaps the feedback's salient words, or None. Lets the
    mock target the task the partner actually named ('remove the recital') instead of guessing."""
    words = {w for w in re.findall(r"[a-z]{4,}", feedback.lower())} - _REVISE_STOP
    best, score = None, 0
    for i, t in enumerate(tasks):
        title_words = set(re.findall(r"[a-z]{4,}", t.get("title", "").lower()))
        overlap = len(words & title_words)
        if overlap > score:
            best, score = i, overlap
    return best


class MockLLMProvider(LLMProvider):
    """Deterministic, network-free implementation that replays the fixtures. This is what the whole
    demo runs on with no API key. It honours the planted defects and produces controlled divergence
    across runs so the multi-run-disagreement signal has something real to measure."""

    def run_task(
        self,
        *,
        instruction: str,
        documents: list[dict],
        kind: str = "review",
        reference: dict | None = None,
        checklist=None,
        run_index: int = 0,
        source_lookup=None,  # ignored: the mock is deterministic and offline
    ) -> TaskResult:
        # Deterministic replay keyed off the target document — instruction/kind/checklist don't
        # change the offline fixture, but the output carries the requested `kind` + its payload.
        draft = documents[0] if documents else None
        data = fixtures.mock_reviews().get(draft["id"]) if draft else None
        if not data:
            title = draft["title"] if draft else "the task"
            return TaskResult(summary=f"No issues identified in {title}.", output_kind=kind)
        findings = [
            Finding(
                id=f["id"],
                clause_ref=f["clause_ref"],
                statement=f["statement"],
                citation=f.get("citation"),
            )
            for f in data["findings"]
            # A finding may only surface on some runs — that divergence is the disagreement signal.
            if run_index in f.get("runs", [run_index])
        ]
        return TaskResult(
            summary=data["summary"],
            output_kind=kind,
            findings=findings,
            payload=data.get("payload", {}),
            clauses_relied_on=data.get("clauses_relied_on", []),
            audit_sources=data.get("audit_sources", []),
        )

    def check_citation_support(self, *, claim: str, source: dict) -> CitationCheck:
        supported_claims = source.get("ground_truth", {}).get("supported_claims", [])
        claim_l = claim.strip().lower()
        for s in supported_claims:
            if claim_l == s.strip().lower() or claim_l in s.strip().lower():
                return CitationCheck(True, f"The source supports the proposition: '{s}'.")
        return CitationCheck(
            False,
            f"'{source.get('title', source.get('celex'))}' does not support the cited proposition.",
        )

    def assess_deviations(self, *, draft: dict, firm_standard: dict) -> list[Deviation]:
        data = fixtures.mock_reviews().get(draft["id"], {})
        return [
            Deviation(
                clause_ref=d["clause_ref"],
                standard_key=d["standard_key"],
                draft_text=d["draft_text"],
                score=d["score"],
                rationale=d["rationale"],
            )
            for d in data.get("deviations", [])
        ]

    def plan_case(
        self,
        *,
        goal: str,
        brief: str,
        process_doc: dict,
        drafts: list[dict],
        associates: list[dict],
        instructions: str = "",
    ) -> list[dict]:
        # Decompose the matter by walking the process doc's sections IN DOCUMENT ORDER and
        # emitting one task per section, so the plan reflects the process doc, not a fixed list.
        # Raw scoping only: the planner SERVICE applies severity (the partner's choice), the
        # process-section label, a default assignee and ordering — so mock and real stay symmetric
        # and severity is never a model inference (architecture.md §6, §7.1).
        scoping = fixtures.mock_plan_by_type()
        fallback_doc_id = drafts[0]["id"] if drafts else None
        tasks: list[dict] = []
        for task_type, section in process_doc.get("task_types", {}).items():
            spec = scoping.get(task_type)
            if spec is None:
                # A process-doc section with no scripted scoping: still cover it deterministically.
                label = section.get("label", task_type)
                spec = {
                    "title": label,
                    "description": f"Review the draft against the process-doc section: {label}.",
                    "assignee_type": "ai",
                    "target_document_id": fallback_doc_id,
                    "input_brief_slice": "",
                    "ai_instruction": None,
                }
            task = dict(spec)
            task["task_type"] = task_type
            tasks.append(task)

        # Deterministic, offline influence of the partner's up-front instructions: "human-led" gives
        # the human oversight (AI tasks become hybrid). A real model interprets the instructions
        # properly; this keeps the steer visible with no network/key. The partner still approves.
        if "human" in (instructions or "").lower():
            for t in tasks:
                if t.get("assignee_type") == "ai":
                    t["assignee_type"] = "hybrid"
                    t["ai_instruction"] = (
                        t.get("ai_instruction") or "Run a first-pass review for the associate."
                    )
                    t["human_instruction"] = "Review the AI's first pass and own the conclusion."
                    t["rationale"] = "Partner asked for human oversight in the case instructions."
        return tasks

    def revise_plan(
        self, *, case: dict, current_tasks: list[dict], feedback: str
    ) -> list[dict]:
        """Deterministic, offline stand-in for a model revising the plan from the partner's words.
        Applies clear transforms to the CURRENT tasks (so partner edits are preserved), targeting
        the task the partner named where possible. ANY feedback produces a visible change: if no
        structural rule fires, the partner's note is attached to the relevant task's rationale, so
        the partner always sees their input reflected. The real provider interprets the feedback
        properly — this keeps the loop exercisable with no network/key."""
        fb = feedback.lower()
        tasks = [dict(t) for t in current_tasks]
        if not tasks:
            return tasks
        named = _match_task(tasks, feedback)
        # Broad changes apply to the named task if the partner pointed at one, else across the plan.
        scope = [named] if named is not None else list(range(len(tasks)))
        changed = False

        # "human-led" → give the human oversight: AI work in scope becomes hybrid.
        if "human" in fb:
            for i in scope:
                if tasks[i].get("assignee_type") == "ai":
                    tasks[i]["assignee_type"] = "hybrid"
                    tasks[i]["human_instruction"] = (
                        tasks[i].get("human_instruction")
                        or "Review the AI's first pass and own the conclusion."
                    )
                    tasks[i]["rationale"] = "Partner asked for human oversight on this work."
                    changed = True
        # "automate"/"use ai" → give the AI a first pass: human work in scope becomes hybrid.
        elif any(w in fb for w in ("automate", "use ai", "more ai")):
            for i in scope:
                if tasks[i].get("assignee_type") == "human":
                    tasks[i]["assignee_type"] = "hybrid"
                    tasks[i]["ai_instruction"] = (
                        tasks[i].get("ai_instruction")
                        or "Run a first-pass review for the associate."
                    )
                    tasks[i]["rationale"] = "Partner asked for AI assistance on this work."
                    changed = True

        # "remove"/"drop" → drop the NAMED task (else the last one); keep at least one.
        if any(w in fb for w in ("remove", "drop", "delete", "without")) and len(tasks) > 1:
            tasks.pop(named if named is not None else len(tasks) - 1)
            changed = True

        # "add"/"another"/"include" → append a partner-requested task.
        if any(w in fb for w in ("add", "another", "additional", "include", "also", "split")):
            primary = tasks[0]
            tasks.append(
                {
                    "title": "Partner-requested additional review",
                    "description": f"Added at the partner's request: {feedback.strip()[:160]}",
                    "task_type": primary.get("task_type", "review_binding_obligation"),
                    "assignee_type": "hybrid",
                    "assignee_id": None,
                    "severity": case.get("severity", "medium"),
                    "target_document_id": primary.get("target_document_id"),
                    "input_brief_slice": "",
                    "ai_instruction": "Run a first-pass review for the associate.",
                    "human_instruction": "Own the conclusion on the partner's specific request.",
                    "rationale": "Added in response to the partner's revision request.",
                }
            )
            changed = True

        # Fallback: no structural rule fired — record the partner's note on the relevant task so the
        # feedback is always visibly reflected (offline mock can't restructure from free text).
        if not changed:
            idx = named if named is not None else 0
            tasks[idx] = dict(tasks[idx])
            tasks[idx]["rationale"] = f"Partner note: {feedback.strip()}"

        return tasks

    def debrief_carry_forward(
        self, *, case: dict, tasks: list[dict], flags: list[dict], decisions: list[dict]
    ) -> list[str]:
        # Deterministic, offline carry-forward notes derived from what was actually flagged/amended.
        notes: list[str] = []
        if any(f["signal_type"] == "precedent_deviation" for f in flags):
            notes.append(
                "Confirm liability-cap and governing-law deviations are resolved before signing."
            )
        if any(f["signal_type"] == "citation_support" for f in flags):
            notes.append(
                "Re-verify any non-supporting citation before the next matter relies on it."
            )
        if any(d.get("action") == "amend" for d in decisions):
            notes.append(
                "Fold the partner's amendments into the firm's standard wording where they recur."
            )
        return notes or ["No outstanding items — the matter closed clean."]
