from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Callable
from dataclasses import dataclass, field

# A source lookup the worker can hand to review_document so the model can fetch a real EU source by
# CELEX on demand (Anthropic tool-use). A plain callable — not the CellarConnector type — so this
# module gains no import and there is no provider -> cellar cycle. Returns a corpus-doc-shaped dict
# on a hit, None on absence. The worker owns the implementation (and the corpus caching).
SourceLookup = Callable[[str], "dict | None"]


class ProviderError(Exception):
    """Base for provider failures."""


class RetryableError(ProviderError):
    """429 / 5xx / timeout — safe to retry."""


class FatalError(ProviderError):
    """4xx validation / policy — fail fast."""


@dataclass
class Finding:
    """One observation a worker makes about a clause. A finding may cite a source; the citation is
    a *checkable claim*, never a verdict."""

    id: str
    clause_ref: str
    statement: str
    citation: dict | None = None  # {"celex": str, "claim": str} or None


@dataclass
class ReviewResult:
    summary: str
    findings: list[Finding] = field(default_factory=list)
    clauses_relied_on: list[str] = field(default_factory=list)
    audit_sources: list[str] = field(default_factory=list)


@dataclass
class CitationCheck:
    """Whether a cited source supports a specific claim. Checkable: the partner can open the source
    and confirm in seconds."""

    supported: bool
    rationale: str


@dataclass
class Deviation:
    clause_ref: str
    standard_key: str
    draft_text: str
    score: float  # 0..1, higher = further from the firm standard
    rationale: str


class LLMProvider(ABC):
    """The single seam every external model call goes through. Orchestration depends only on this
    interface; swapping mock <-> real Anthropic is a drop-in (architecture.md §3)."""

    @abstractmethod
    def review_document(
        self,
        *,
        draft: dict,
        firm_standard: dict,
        process_section: str,
        run_index: int = 0,
        source_lookup: SourceLookup | None = None,
    ) -> ReviewResult:
        """Review a draft document against the firm standard → structured findings (depth). When
        `source_lookup` is given, a capable provider may call it (tool-use) to ground a citation in
        the real source by CELEX while drafting; providers without tool-use ignore it."""

    @abstractmethod
    def check_citation_support(self, *, claim: str, source: dict) -> CitationCheck:
        """Test whether a retrieved source actually supports a cited claim."""

    @abstractmethod
    def assess_deviations(self, *, draft: dict, firm_standard: dict) -> list[Deviation]:
        """Structural + semantic distance of the draft's clauses from the firm standard."""

    @abstractmethod
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
        """Scope a goal into a proposed task list — RAW scoping only (title, description,
        task_type, assignee_type, target_document_id, input_brief_slice, ai_instruction,
        human_instruction for hybrid tasks, and a one-line rationale). `instructions` is the
        partner's free-text direction up front, which the provider should respect. The planner
        service applies the partner's severity, the process-section label, a default assignee and
        ordering. A
        proposal; nothing dispatches until the partner approves."""

    def revise_plan(
        self, *, case: dict, current_tasks: list[dict], feedback: str
    ) -> list[dict]:
        """Revise the current proposed task list given the partner's free-text direction. Returns
        FULL task dicts (same shape as the stored tasks, so partner edits are preserved), which the
        planner service re-stamps onto a fresh proposed plan. Default: a no-op returning the current
        tasks unchanged — providers that can interpret the feedback override this. Still a proposal;
        nothing dispatches until the partner approves."""
        return [dict(t) for t in current_tasks]

    @abstractmethod
    def generate_debrief(
        self, *, case: dict, tasks: list[dict], flags: list[dict], decisions: list[dict]
    ) -> str:
        """Templated debrief markdown from the case record."""
