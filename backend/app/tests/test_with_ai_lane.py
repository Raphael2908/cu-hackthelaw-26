from __future__ import annotations

from app.core import stream
from app.db.tables import SUBMISSIONS, TASKS
from app.services import views


def _task(repo, *, assignee_type, status, case_id="case-x"):
    return repo.insert(
        TASKS,
        {
            "case_id": case_id,
            "title": f"{assignee_type}/{status}",
            "assignee_type": assignee_type,
            "status": status,
        },
    )


def test_cockpit_partitions_with_ai_from_awaiting_human(in_memory_repo):
    """The cockpit must split in-flight work by WHO holds it (assignee_type), not status alone — a
    running AI task is in_progress but belongs under "With AI", never "With a person" (§8)."""
    repo = in_memory_repo
    ai_running = _task(repo, assignee_type="ai", status="in_progress")
    ai_submitted = _task(repo, assignee_type="ai", status="submitted")
    ai_checked = _task(repo, assignee_type="ai", status="checked")
    human_running = _task(repo, assignee_type="human", status="in_progress")
    human_returned = _task(repo, assignee_type="human", status="returned")
    # A hybrid task with no AI first pass yet → the AI is still drafting → "With AI".
    hybrid_drafting = _task(repo, assignee_type="hybrid", status="in_progress")
    # A hybrid task whose AI first pass exists is parked for the associate → "With a person".
    hybrid_awaiting = _task(repo, assignee_type="hybrid", status="in_progress")
    repo.insert(SUBMISSIONS, {"task_id": hybrid_awaiting["id"], "produced_by": "hybrid"})
    hybrid_returned = _task(repo, assignee_type="hybrid", status="returned")

    ck = views.cockpit(repo, "case-x")

    assert {c["task"]["id"] for c in ck["with_ai"]} == {
        ai_running["id"],
        ai_submitted["id"],
        ai_checked["id"],
        hybrid_drafting["id"],
    }
    assert {c["task"]["id"] for c in ck["awaiting_human"]} == {
        human_running["id"],
        human_returned["id"],
        hybrid_awaiting["id"],
        hybrid_returned["id"],
    }
    # The split is presentation only: the pending count (debrief close-gate) still counts every
    # non-terminal task, unchanged by which lane it lands in.
    assert ck["pending"]["total"] == 8


def test_dispatch_stamps_run_started_at(client):
    """Dispatching an AI/hybrid task records a server-authoritative run_started_at so the cockpit's
    elapsed timer measures from dispatch, not from when the poller first saw the task."""
    case = client.post(
        "/api/cases",
        json={"title": "T", "brief_text": "b", "goal": "g", "severity": "low"},
    ).json()
    plan = client.post(f"/api/cases/{case['id']}/plan").json()
    client.post(f"/api/plans/{plan['plan']['id']}/approve")

    tasks = client.get(f"/api/plans/{plan['plan']['id']}").json()["tasks"]
    ai_tasks = [t for t in tasks if t["assignee_type"] in ("ai", "hybrid")]
    assert ai_tasks, "expected at least one AI/hybrid task to dispatch"
    assert all(t.get("run_started_at") for t in ai_tasks)


def test_publish_delta_is_best_effort_without_redis():
    """The live stream is non-essential: publishing a delta must never raise, so inline/offline
    dispatch (and the test suite) is unaffected when no broker is reachable (§14)."""
    stream._sync_client.cache_clear()
    stream.publish_delta("task-none", {"type": "delta", "text": "hello"})
    stream.publish_delta("task-none", {"type": "done"})


def test_mock_run_task_accepts_and_ignores_on_delta(provider):
    """The mock provider takes the streaming sink and ignores it (offline/deterministic), so the
    worker can pass it uniformly regardless of provider."""
    sink_calls: list[str] = []
    result = provider.run_task(
        instruction="x", documents=[], kind="review", on_delta=sink_calls.append
    )
    assert result.output_kind == "review"
    assert sink_calls == []  # mock never streams
