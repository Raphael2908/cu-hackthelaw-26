from __future__ import annotations

from app.config import settings
from app.core.audit import record_supervision
from app.db.repo import Repo
from app.db.tables import CORPUS, FLAGS
from app.fixtures import firm_standard
from app.providers.base import LLMProvider, ProviderError
from app.providers.cellar import CellarConnector, get_cellar
from app.schemas.models import DEFAULT_CHECKS
from app.services.task_spec import TaskSpec, build_task_spec

# Thresholds at which a measured signal becomes a flag the partner should see. Tunable.
DEVIATION_FLAG_THRESHOLD = 0.5
DISAGREEMENT_FLAG_THRESHOLD = 0.3


def _corpus_by_celex(repo: Repo, celex: str) -> dict | None:
    for d in repo.list(CORPUS):
        if d.get("celex") == celex:
            return d
    return None


def _flag(repo: Repo, task: dict, submission: dict, **fields) -> dict:
    """Persist a flag and mirror it into the supervision audit stream (kept separate from the
    accountability stream — architecture.md §11). Flags are checkable claims, never verdicts."""
    flag = {"task_id": task["id"], "submission_id": submission["id"], **fields}
    saved = repo.insert(FLAGS, flag)
    record_supervision(
        repo,
        type="flag_raised",
        actor="checker",
        case_id=task["case_id"],
        task_id=task["id"],
        payload={
            "signal_type": fields["signal_type"],
            "title": fields["title"],
            "hard": fields.get("hard", False),
        },
    )
    return saved


# --- Signal 1: citation support rate -------------------------------------------------------------


def citation_support(
    repo: Repo,
    task: dict,
    submission: dict,
    provider: LLMProvider,
    cellar: CellarConnector | None = None,
) -> dict:
    """For each cited claim, retrieve the source and test whether it supports the claim. A
    fabricated or non-supporting citation is a HARD signal, surfaced regardless of severity.

    Sources are resolved first from the corpus, then — if CELLAR_ENABLED — fetched live from the EU
    Cellar by CELEX and cached into the corpus. A fetch that authoritatively reports no such CELEX
    is a genuine fabrication (hard); a fetch that *fails* (network/outage) is NOT — it surfaces a
    soft "unverifiable" flag and the claim is excluded from the support-rate denominator, so an
    outage can never masquerade as a fabricated citation (architecture.md §14.1)."""
    cellar = cellar or get_cellar()
    findings = [f for f in submission["findings"] if f.get("citation")]
    flags: list[dict] = []
    supported = 0
    unverifiable = 0
    for f in findings:
        cit = f["citation"]
        source = _corpus_by_celex(repo, cit["celex"])
        if source is None:
            try:
                fetched = cellar.fetch_by_celex(cit["celex"])
            except ProviderError as e:
                unverifiable += 1
                flags.append(
                    _flag(
                        repo,
                        task,
                        submission,
                        signal_type="citation_support",
                        hard=False,
                        title=f"Citation unverifiable: {cit['celex']} (source service unavailable)",
                        description="The EU Cellar source service could not be reached, so this "
                        f"citation could not be checked: {e}. Excluded from the support rate.",
                        evidence={"claim": cit["claim"], "celex": cit["celex"]},
                        source_ref={
                            "celex": cit["celex"],
                            "exists": None,
                            "clause_ref": f["clause_ref"],
                        },
                    )
                )
                continue
            if fetched is not None:
                source = repo.insert(CORPUS, fetched)  # cache: resolvable via GET /api/corpus/{id}
        if source is None:
            flags.append(
                _flag(
                    repo,
                    task,
                    submission,
                    signal_type="citation_support",
                    hard=True,
                    title=f"Fabricated citation: {cit['celex']} does not exist",
                    description=f"Finding on '{f['clause_ref']}' cites {cit['celex']}, "
                    "which is not in the corpus.",
                    evidence={"claim": cit["claim"], "celex": cit["celex"]},
                    source_ref={
                        "celex": cit["celex"],
                        "exists": False,
                        "clause_ref": f["clause_ref"],
                    },
                )
            )
            continue
        check = provider.check_citation_support(claim=cit["claim"], source=source)
        if check.supported:
            supported += 1
        else:
            flags.append(
                _flag(
                    repo,
                    task,
                    submission,
                    signal_type="citation_support",
                    hard=True,
                    title=f"Citation does not support the claim ({cit['celex']})",
                    description=check.rationale,
                    evidence={"claim": cit["claim"], "source_title": source["title"]},
                    source_ref={
                        "corpus_document_id": source["id"],
                        "celex": cit["celex"],
                        "exists": True,
                        "clause_ref": f["clause_ref"],
                    },
                )
            )
    verifiable = len(findings) - unverifiable
    rate = 1.0 if verifiable <= 0 else supported / verifiable
    return {
        "rate": rate,
        "flags": flags,
        "n_citations": len(findings),
        "n_unverifiable": unverifiable,
    }


# --- Signal 2: precedent deviation ---------------------------------------------------------------


def precedent_deviation(
    repo: Repo, task: dict, submission: dict, provider: LLMProvider, *, std: dict | None = None
) -> dict:
    """Structural + semantic distance of the draft's clauses from the firm standard. `std` is the
    reference standard resolved by the caller (the task spec); when omitted it falls back to the
    task's firm standard, preserving the original call shape for existing callers."""
    draft = repo.get(CORPUS, task["target_document_id"])
    if std is None:
        std = (
            repo.get(CORPUS, task.get("firm_standard_id") or firm_standard()["id"])
            or firm_standard()
        )
    deviations = provider.assess_deviations(draft=draft, firm_standard=std)
    flags: list[dict] = []
    max_score = 0.0
    for d in deviations:
        max_score = max(max_score, d.score)
        if d.score >= DEVIATION_FLAG_THRESHOLD:
            flags.append(
                _flag(
                    repo,
                    task,
                    submission,
                    signal_type="precedent_deviation",
                    hard=False,
                    title=f"Deviates from firm standard: {d.clause_ref}",
                    description=d.rationale,
                    evidence={
                        "draft_text": d.draft_text,
                        "score": d.score,
                        "standard_clause": std.get("clauses", {}).get(d.standard_key, ""),
                    },
                    source_ref={
                        "corpus_document_id": std["id"],
                        "standard_key": d.standard_key,
                        "clause_ref": d.clause_ref,
                    },
                )
            )
    return {"score": max_score, "flags": flags, "n_deviations": len(deviations)}


# --- Signal 3: multi-run disagreement ------------------------------------------------------------


def multi_run_disagreement(
    repo: Repo, task: dict, submission: dict, provider: LLMProvider, *, spec: TaskSpec | None = None
) -> dict:
    """Run the task more than once and measure divergence in the findings produced. The cheapest,
    most honest uncertainty signal — it relies on no model self-confidence. The re-runs use the SAME
    task spec the worker's first pass used (built once and threaded in), so the runs being compared
    are genuinely the same call — un-grounded, to bound tool-call cost (architecture.md §7.2/§9)."""
    if spec is None:
        spec = build_task_spec(repo, task)
    runs = max(2, settings.DISAGREEMENT_RUNS)
    run_finding_ids: list[set[str]] = []
    for i in range(runs):
        result = provider.run_task(**spec.run_kwargs(run_index=i, source_lookup=None))
        run_finding_ids.append({f.id for f in result.findings})

    union: set[str] = set().union(*run_finding_ids) if run_finding_ids else set()
    intersection: set[str] = set.intersection(*run_finding_ids) if run_finding_ids else set()
    score = 0.0 if not union else 1.0 - (len(intersection) / len(union))
    flags: list[dict] = []
    if score >= DISAGREEMENT_FLAG_THRESHOLD:
        unstable = sorted(union - intersection)
        flags.append(
            _flag(
                repo,
                task,
                submission,
                signal_type="multi_run_disagreement",
                hard=False,
                title=f"Conclusions unstable across {runs} runs",
                description=f"{len(unstable)} finding(s) appeared in some runs but not others.",
                evidence={
                    "runs": runs,
                    "unstable_findings": unstable,
                    "disagreement": round(score, 3),
                },
                source_ref={"task_id": task["id"]},
            )
        )
    return {"score": score, "flags": flags, "runs": runs}


def run_checks(
    repo: Repo,
    task: dict,
    submission: dict,
    provider: LLMProvider,
    cellar: CellarConnector | None = None,
) -> dict:
    """Run the supervision signals that APPLY to this task. Returns the per-signal scores, the flags
    raised, and `applied_checks` — an honest record of which signals actually ran. A signal that
    does not apply contributes its neutral score AND is marked not-applied, so the ranker drops it
    from the uncertainty composite and the cockpit can show it as "n/a" rather than a misleading 0.0
    (architecture.md §7.2/§14.4). Never a pass/fail.

    Citation support is always run: any task can fabricate a citation, and a fabricated or
    non-supporting citation is the load-bearing hard signal. Precedent deviation runs only when the
    task is checked against a reference standard; multi-run disagreement runs unless opted out."""
    checks = task.get("applicable_checks") or list(DEFAULT_CHECKS)
    spec = build_task_spec(repo, task)
    applied = {
        "citation_support": True,
        "precedent_deviation": False,
        "multi_run_disagreement": False,
    }

    citation = citation_support(repo, task, submission, provider, cellar)

    if "precedent_deviation" in checks and spec.reference is not None:
        deviation = precedent_deviation(repo, task, submission, provider, std=spec.reference)
        applied["precedent_deviation"] = True
    else:
        deviation = {"score": 0.0, "flags": [], "n_deviations": 0}

    if "multi_run_disagreement" in checks:
        disagreement = multi_run_disagreement(repo, task, submission, provider, spec=spec)
        applied["multi_run_disagreement"] = True
    else:
        disagreement = {"score": 0.0, "flags": [], "runs": 0}

    all_flags = citation["flags"] + deviation["flags"] + disagreement["flags"]
    return {
        "citation_support_rate": citation["rate"],
        "deviation_score": deviation["score"],
        "disagreement_score": disagreement["score"],
        "applied_checks": applied,
        "flags": all_flags,
        "has_hard_flag": any(f.get("hard") for f in all_flags),
    }
