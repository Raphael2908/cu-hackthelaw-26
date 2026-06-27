from __future__ import annotations

from app.core import audit
from app.core.tasks import run_dispatch_task
from app.db.repo import InMemoryRepo

CASE = {
    "title": "Project Atlas — supplier agreement review",
    "brief_text": "Supplier processes customer personal data including via US affiliates.",
    "goal": "Review the Project Atlas agreement against the firm standard before signing.",
    "severity": "low",
}


def test_insert_chained_links_each_event_and_chain_verifies():
    """The atomic chained append (which now backs the audit log across processes) builds each
    event on the previous one's hash, and verify_chain confirms the result."""
    repo = InMemoryRepo()
    for i in range(5):
        audit.record_accountability(repo, type="t", actor="tester", payload={"i": i})
    events = repo.list("audit_events")
    assert events[0]["prev_hash"] == "GENESIS"
    for prev, cur in zip(events, events[1:], strict=False):
        assert cur["prev_hash"] == prev["hash"]
    assert audit.verify_chain(repo) is True


def test_run_dispatch_task_reconstructs_repo_and_provider_and_routes(client, in_memory_repo):
    """The Celery task takes only a serializable task_id, rebuilds repo + provider from their
    factories, runs the supervision pipeline, and routes the task off the approval path."""
    case = client.post("/api/cases", json=CASE).json()
    plan = client.post(f"/api/cases/{case['id']}/plan").json()
    ai_task = next(t for t in plan["tasks"] if t["assignee_type"] == "ai")

    # Approve it without dispatching, then invoke the task body directly (as a worker does).
    in_memory_repo.update("tasks", ai_task["id"], {"status": "approved"})
    run_dispatch_task.run(ai_task["id"])  # .run() executes the task body synchronously

    routed = client.get(f"/api/tasks/{ai_task['id']}").json()
    assert routed["task"]["status"] in ("in_review", "cleared")
    assert audit.verify_chain(in_memory_repo) is True
