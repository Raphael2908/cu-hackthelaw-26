from __future__ import annotations

# Logical tables (resources). See architecture.md §5 for the field shapes.
ASSOCIATES = "associates"
CORPUS = "corpus_documents"
CASES = "cases"
PLANS = "plans"
TASKS = "tasks"
SUBMISSIONS = "submissions"
FLAGS = "flags"
RISK_SCORES = "risk_scores"
DECISIONS = "decisions"
AUDIT_EVENTS = "audit_events"
DEBRIEFS = "debriefs"
TASK_MESSAGES = "task_messages"

ALL_TABLES = [
    ASSOCIATES,
    CORPUS,
    CASES,
    PLANS,
    TASKS,
    SUBMISSIONS,
    FLAGS,
    RISK_SCORES,
    DECISIONS,
    AUDIT_EVENTS,
    DEBRIEFS,
    TASK_MESSAGES,
]
