from __future__ import annotations

from app import fixtures
from app.providers.base import (
    CitationCheck,
    Deviation,
    Finding,
    LLMProvider,
    TaskResult,
)


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
        return tasks

    def generate_debrief(
        self, *, case: dict, tasks: list[dict], flags: list[dict], decisions: list[dict]
    ) -> str:
        lines = [
            f"# Case debrief — {case['title']}",
            "",
            f"**Goal:** {case['goal']}",
            "",
            f"## Tasks ({len(tasks)})",
        ]
        for t in tasks:
            lines.append(
                f"- **{t['title']}** — {t['assignee_type']}, severity {t['severity']}, "
                f"status {t['status']}"
            )
        lines += ["", f"## Flags raised ({len(flags)})"]
        for f in flags:
            hard = " (hard)" if f.get("hard") else ""
            lines.append(f"- [{f['signal_type']}]{hard} {f['title']}")
        lines += ["", f"## Partner decisions ({len(decisions)})"]
        for d in decisions:
            amend = f" — amendment: {d['amendment']}" if d.get("amendment") else ""
            lines.append(f"- **{d['action']}** on task {d['task_id']}: {d.get('note', '')}{amend}")
        lines += [
            "",
            "## Carry forward",
            "- Confirm the liability-cap and governing-law deviations are resolved before signing.",
            "- Re-verify any non-supporting citation before the next matter relies on it.",
        ]
        return "\n".join(lines)
