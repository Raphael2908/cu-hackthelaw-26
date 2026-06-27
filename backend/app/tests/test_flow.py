from __future__ import annotations

ASSOC_HEADERS = {"X-User-Email": "amara@firm.example", "X-User-Role": "associate"}

CASE = {
    "title": "Project Atlas — supplier agreement review",
    "brief_text": "Supplier processes customer personal data including via US affiliates.",
    "goal": "Review the Project Atlas agreement against the firm standard before signing.",
    # The partner sets ONE severity for the matter up front (architecture.md §7.1); every task in
    # the plan inherits it. Low here so a clean, low-uncertainty task can demonstrate the auto-clear
    # lane, while a hard-flag citation still forces its task to the top of the review queue.
    "severity": "low",
}


def _new_case_with_plan(client):
    case = client.post("/api/cases", json=CASE).json()
    plan = client.post(f"/api/cases/{case['id']}/plan").json()
    return case, plan


def _resolve_remaining(client, case_id):
    """Drive every still-pending task to a terminal state so the case can be closed: submit any work
    still with an associate (human + hybrid in the inbox), then decide everything now in review."""
    for item in client.get("/api/inbox", headers=ASSOC_HEADERS).json():
        t = item["task"]
        if t.get("case_id") == case_id and t["status"] in ("dispatched", "in_progress", "returned"):
            client.post(
                f"/api/tasks/{t['id']}/submit",
                json={"summary": "Reviewed; matches the standard.", "findings": []},
                headers=ASSOC_HEADERS,
            )
    for card in client.get(f"/api/cases/{case_id}/cockpit").json()["queue"]:
        client.post(
            f"/api/tasks/{card['task']['id']}/decision",
            json={"action": "approve", "note": "Signed off."},
        )


def test_approval_gate_blocks_dispatch(client):
    """Nothing is dispatched before the partner approves the plan (architecture.md §14.7)."""
    _, plan = _new_case_with_plan(client)
    assert all(t["status"] == "proposed" for t in plan["tasks"])


def test_plan_proposes_assignee_type_and_severity(client):
    _, plan = _new_case_with_plan(client)
    assert {t["assignee_type"] for t in plan["tasks"]} >= {"ai", "human", "hybrid"}
    # Severity is the partner's single up-front choice on the case, applied to every task.
    assert {t["severity"] for t in plan["tasks"]} == {"low"}


def test_plan_decomposes_one_task_per_process_section(client):
    """The planner walks the process doc and emits one task per section, so the plan tracks the
    process doc rather than a fixed list (architecture.md §6)."""
    from app.fixtures import process_doc

    _, plan = _new_case_with_plan(client)
    sections = set(process_doc()["task_types"])
    assert {t["task_type"] for t in plan["tasks"]} == sections
    assert len(plan["tasks"]) == len(sections)


def test_case_instructions_steer_the_planner(client):
    """The partner's up-front instructions shape the plan: 'human-led' gives AI work human oversight
    (AI → hybrid). Recorded on the plan_proposed event (the partner authoring the delegation)."""
    case = client.post(
        "/api/cases",
        json={**CASE, "instructions": "Keep all the review human-led."},
    ).json()
    plan = client.post(f"/api/cases/{case['id']}/plan").json()
    assert all(t["assignee_type"] != "ai" for t in plan["tasks"])
    audit = client.get(f"/api/cases/{case['id']}/audit").json()
    proposed = next(e for e in audit["accountability"] if e["type"] == "plan_proposed")
    assert "human-led" in proposed["payload"]["instructions"].lower()


def test_plan_carries_rationale_and_hybrid_split(client):
    _, plan = _new_case_with_plan(client)
    # Every task explains its reasoning; the hybrid task carries both halves of the split.
    assert all(t.get("rationale") for t in plan["tasks"])
    hybrid = next(t for t in plan["tasks"] if t["assignee_type"] == "hybrid")
    assert hybrid["ai_instruction"] and hybrid["human_instruction"]


def test_revise_plan_respects_feedback_and_stays_proposed(client):
    case, plan = _new_case_with_plan(client)
    plan_id = plan["plan"]["id"]
    assert any(t["assignee_type"] == "ai" for t in plan["tasks"])

    # "human-led" → the AI tasks gain human oversight (become hybrid); still a fresh PROPOSAL.
    revised = client.post(
        f"/api/cases/{case['id']}/plan/revise",
        json={"feedback": "Make all the review human-led."},
    )
    assert revised.status_code == 201
    body = revised.json()
    assert body["plan"]["status"] == "proposed"
    assert body["plan"]["id"] != plan_id  # latest plan wins, like regenerate
    assert all(t["assignee_type"] != "ai" for t in body["tasks"])
    # The partner's direction is recorded as part of the delegation record.
    audit = client.get(f"/api/cases/{case['id']}/audit").json()
    assert "plan_revised" in {e["type"] for e in audit["accountability"]}

    # An approved plan can't be revised.
    client.post(f"/api/plans/{body['plan']['id']}/approve")
    blocked = client.post(
        f"/api/cases/{case['id']}/plan/revise", json={"feedback": "one more change"}
    )
    assert blocked.status_code == 409


def test_whole_plan_edit_add_remove_reorder(client):
    case, plan = _new_case_with_plan(client)
    n = len(plan["tasks"])

    # Add a blank proposed task.
    added = client.post(f"/api/cases/{case['id']}/plan/tasks")
    assert added.status_code == 201
    new_id = added.json()["id"]
    assert len(client.get(f"/api/cases/{case['id']}/plan").json()["tasks"]) == n + 1

    # Reorder via order_index patch.
    patched = client.patch(f"/api/tasks/{new_id}", json={"order_index": 0})
    assert patched.status_code == 200 and patched.json()["order_index"] == 0

    # Remove it.
    removed = client.delete(f"/api/tasks/{new_id}")
    assert removed.status_code == 204
    assert len(client.get(f"/api/cases/{case['id']}/plan").json()["tasks"]) == n
    audit = client.get(f"/api/cases/{case['id']}/audit").json()
    assert {"task_added", "task_removed"} <= {e["type"] for e in audit["accountability"]}

    # Once approved, structural edits are refused.
    client.post(f"/api/plans/{plan['plan']['id']}/approve")
    assert client.post(f"/api/cases/{case['id']}/plan/tasks").status_code == 409


def test_flags_carry_both_sides_for_verification(client):
    """Citation + deviation flags carry a work_ref (the quoting passage in the submitted work)
    alongside source_ref (the quoted source), so the partner can compare both sides."""
    case, plan = _new_case_with_plan(client)
    client.post(f"/api/plans/{plan['plan']['id']}/approve")
    top = client.get(f"/api/cases/{case['id']}/cockpit").json()["queue"][0]
    flags = client.get(f"/api/tasks/{top['task']['id']}").json()["flags"]

    cite = next(f for f in flags if f["signal_type"] == "citation_support")
    dev = next(f for f in flags if f["signal_type"] == "precedent_deviation")
    for f in (cite, dev):
        assert f.get("work_ref") and f["work_ref"].get("statement"), f["signal_type"]
        assert f.get("source_ref")
    # The citation flag also records the proposition the work attributed to the source.
    assert cite["work_ref"].get("claim")


def test_happy_path_end_to_end(client):
    case, plan = _new_case_with_plan(client)
    plan_id = plan["plan"]["id"]

    # Approve → dispatch. Only the partner (default user) can approve.
    approved = client.post(f"/api/plans/{plan_id}/approve")
    assert approved.status_code == 200

    cockpit = client.get(f"/api/cases/{case['id']}/cockpit").json()
    # Queue sorted highest-risk first; the top item is the hard-flag DPA review — a citation to a
    # non-existent source forces it to the top regardless of the case's low severity.
    assert cockpit["queue"], "expected a triaged review queue"
    top = cockpit["queue"][0]
    assert top["risk"]["priority"] >= 0.9
    assert top["risk"]["has_hard_flag"] is True
    # A low-risk item cleared into the audit lane.
    assert cockpit["auto_clear_lane"], "expected an auto-clear lane"

    # The human task is waiting in the associate inbox; submit it back into the flow.
    inbox = client.get("/api/inbox", headers=ASSOC_HEADERS).json()
    assert inbox
    human_task = next(i["task"] for i in inbox if i["task"]["assignee_type"] == "human")
    submitted = client.post(
        f"/api/tasks/{human_task['id']}/submit",
        json={"summary": "Confidentiality clause matches the standard.", "findings": []},
        headers=ASSOC_HEADERS,
    )
    assert submitted.status_code == 200

    # A hybrid task carries the AI instruction and the AI first pass.
    hybrid = next(i for i in inbox if i["task"]["assignee_type"] == "hybrid")
    assert hybrid["task"]["ai_instruction"]
    assert hybrid["ai_first_pass"] is not None

    # Open the top item: the planted defects are present as checkable flags with sources.
    detail = client.get(f"/api/tasks/{top['task']['id']}").json()
    signal_types = {f["signal_type"] for f in detail["flags"]}
    assert "citation_support" in signal_types
    assert "precedent_deviation" in signal_types
    for f in detail["flags"]:
        assert "verdict" not in f  # never a pass/fail

    # Approve with an amendment → an immutable signed record.
    decision = client.post(
        f"/api/tasks/{top['task']['id']}/decision",
        json={
            "action": "amend",
            "note": "Raise liability cap to 100%.",
            "amendment": "Clause 3.2 cap set to 100% of annual fees.",
        },
    )
    assert decision.status_code == 200

    # Audit: accountability and supervision are separate; the chain verifies.
    audit = client.get(f"/api/cases/{case['id']}/audit").json()
    assert audit["chain_valid"] is True
    acc_types = {e["type"] for e in audit["accountability"]}
    assert {"plan_proposed", "plan_approved", "decision_recorded"} <= acc_types
    assert audit["supervision"], "flags should appear in the supervision stream"

    # Close requires every task resolved first — resolve the rest, then close → debrief generates.
    _resolve_remaining(client, case["id"])
    closed = client.post(f"/api/cases/{case['id']}/close")
    assert closed.status_code == 200
    # The debrief is an issue-centric structured payload: each needs-attention task joins its flags
    # and the partner's decision in ONE entry; routine work collapses to a count.
    report = closed.json()["content"]
    assert report["goal"] and report["summary"]["tasks"] >= 1
    amended = next(
        i for i in report["issues"] if i["decision"] and i["decision"]["action"] == "amend"
    )
    assert amended["flags"] and amended["decision"]["amendment"]  # the join, in one record


def test_close_blocked_while_tasks_pending(client):
    """A debrief drawn from an in-flight record would misrepresent the matter: closing is refused
    while any task is still pending, and no debrief is generated."""
    case, plan = _new_case_with_plan(client)
    client.post(f"/api/plans/{plan['plan']['id']}/approve")

    # Straight after approval, work is mid-flight (review queue + associate inbox).
    blocked = client.post(f"/api/cases/{case['id']}/close")
    assert blocked.status_code == 409
    assert "pending" in blocked.json()["detail"].lower()
    assert client.get(f"/api/cases/{case['id']}/debrief").status_code == 404
    assert client.get(f"/api/cases/{case['id']}").json()["status"] == "open"

    # Once everything is resolved, the same call succeeds.
    _resolve_remaining(client, case["id"])
    assert client.post(f"/api/cases/{case['id']}/close").status_code == 200


def test_all_planted_defects_surface(client):
    case, plan = _new_case_with_plan(client)
    client.post(f"/api/plans/{plan['plan']['id']}/approve")
    flags = []
    for t in plan["tasks"]:
        flags += client.get(f"/api/tasks/{t['id']}").json()["flags"]
    citation_flags = [f for f in flags if f["signal_type"] == "citation_support"]
    deviation_flags = [f for f in flags if f["signal_type"] == "precedent_deviation"]
    assert len(citation_flags) >= 2  # one non-supporting + one fabricated
    assert len(deviation_flags) >= 2  # liability + governing law


def test_async_dispatch_returns_immediately_then_completes(client, monkeypatch):
    """With ASYNC_DISPATCH on, approve returns at once and the pipeline finishes in the background.
    Mock mode makes the background work instant, so a short spin is enough to observe completion."""
    import time

    from app.config import settings

    monkeypatch.setattr(settings, "ASYNC_DISPATCH", True)
    case, plan = _new_case_with_plan(client)
    approved = client.post(f"/api/plans/{plan['plan']['id']}/approve")
    assert approved.status_code == 200
    assert approved.json()["dispatched"] == len(plan["tasks"])

    # Poll the cockpit until the AI/hybrid tasks have been triaged (or time out).
    deadline = time.time() + 5
    cockpit = {}
    while time.time() < deadline:
        cockpit = client.get(f"/api/cases/{case['id']}/cockpit").json()
        if cockpit["queue"] or cockpit["auto_clear_lane"]:
            break
        time.sleep(0.05)
    assert cockpit["queue"], "background pipeline should populate the review queue"
    # The audit chain stays intact despite concurrent background writes.
    assert client.get(f"/api/cases/{case['id']}/audit").json()["chain_valid"] is True


def test_reject_moves_task_to_escalated_lane(client):
    """A partner reject escalates the task; the cockpit surfaces it in its own escalations lane,
    separate from signed-off work (architecture.md §8, §14.6)."""
    case, plan = _new_case_with_plan(client)
    client.post(f"/api/plans/{plan['plan']['id']}/approve")
    top = client.get(f"/api/cases/{case['id']}/cockpit").json()["queue"][0]

    decision = client.post(
        f"/api/tasks/{top['task']['id']}/decision",
        json={"action": "reject", "note": "Redraft the liability cap from scratch."},
    )
    assert decision.status_code == 200

    cockpit = client.get(f"/api/cases/{case['id']}/cockpit").json()
    escalated_ids = {c["task"]["id"] for c in cockpit["escalated"]}
    decided_ids = {c["task"]["id"] for c in cockpit["decided"]}
    assert top["task"]["id"] in escalated_ids
    assert top["task"]["id"] not in decided_ids


def test_associate_cannot_approve_plan(client):
    _, plan = _new_case_with_plan(client)
    r = client.post(f"/api/plans/{plan['plan']['id']}/approve", headers=ASSOC_HEADERS)
    assert r.status_code == 403


def test_double_approval_is_rejected(client):
    _, plan = _new_case_with_plan(client)
    plan_id = plan["plan"]["id"]
    assert client.post(f"/api/plans/{plan_id}/approve").status_code == 200
    assert client.post(f"/api/plans/{plan_id}/approve").status_code == 409
