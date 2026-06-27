from __future__ import annotations

import random

from app.config import settings
from app.db.repo import Repo
from app.db.tables import RISK_SCORES

# Severity is set up front (architecture.md §7.1); these are its numeric weights for ordering.
SEVERITY_WEIGHT = {"low": 0.2, "medium": 0.55, "high": 0.9, "extreme": 1.0}
# An item only auto-clears if it is low severity AND its measured uncertainty is below this.
LOW_UNCERTAINTY_THRESHOLD = 0.15


def compute_uncertainty(signals: dict) -> float:
    """Tunable weighted composite of the independent signals that APPLY to this task. A signal the
    task didn't run (e.g. precedent deviation on a from-scratch draft with no firm standard) is
    excluded from BOTH numerator and denominator — i.e. the composite is renormalised over the
    applied checks, so a task is never made to look more certain just because a signal couldn't run
    (architecture.md §7.2/§14.4). Each signal is also stored separately so no single number is
    load-bearing in the UI.

    `applied_checks` defaults to all-applied when absent, preserving the original three-signal
    behaviour for any caller that doesn't supply it."""
    applied = signals.get("applied_checks") or {}
    weighted: list[tuple[float, float]] = []  # (weight, contribution)
    if applied.get("citation_support", True):
        weighted.append((settings.W_CITATION, 1.0 - signals["citation_support_rate"]))
    if applied.get("precedent_deviation", True):
        weighted.append((settings.W_DEVIATION, signals["deviation_score"]))
    if applied.get("multi_run_disagreement", True):
        weighted.append((settings.W_DISAGREEMENT, signals["disagreement_score"]))
    total = sum(w for w, _ in weighted)
    if total <= 0:
        return 0.0
    return sum(w * c for w, c in weighted) / total


def score_task(repo: Repo, task: dict, signals: dict, *, rng: random.Random | None = None) -> dict:
    """Combine the up-front severity with the measured uncertainty into a queue priority, assign the
    review lane, and randomly sample from the auto-clear lane. Nothing is auto-approved — this only
    triages the partner's attention (architecture.md §7.3)."""
    rng = rng or random
    severity = task["severity"]
    sev_w = SEVERITY_WEIGHT.get(severity, 0.55)
    uncertainty = compute_uncertainty(signals)
    has_hard = signals.get("has_hard_flag", False)

    priority = 0.5 * sev_w + 0.5 * uncertainty
    if has_hard:
        # Hard signals (e.g. a citation to a source that does not exist) are always surfaced.
        priority = max(priority, 0.95)

    auto_clear = severity == "low" and uncertainty < LOW_UNCERTAINTY_THRESHOLD and not has_hard
    lane = "auto_clear" if auto_clear else "review"
    # Like a financial audit: a random sample of auto-cleared work is still pulled for review.
    sampled = bool(auto_clear and rng.random() < settings.SAMPLE_RATE)

    record = {
        "task_id": task["id"],
        "severity_label": severity,
        "citation_support_rate": signals["citation_support_rate"],
        "deviation_score": signals["deviation_score"],
        "disagreement_score": signals["disagreement_score"],
        "uncertainty": round(uncertainty, 4),
        "priority": round(priority, 4),
        "lane": lane,
        "sampled": sampled,
        "has_hard_flag": has_hard,
        # Which signals actually ran — so the cockpit shows a non-applicable signal as "n/a" instead
        # of a misleading measured 0.0 (architecture.md §14.4).
        "applied_checks": signals.get("applied_checks", {}),
    }
    return repo.insert(RISK_SCORES, record)
