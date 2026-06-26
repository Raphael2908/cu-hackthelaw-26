from __future__ import annotations

ASSOC_HEADERS = {"X-User-Email": "amara@firm.example", "X-User-Role": "associate"}

CASE = {
    "title": "Project Atlas — supplier agreement review",
    "brief_text": "Supplier processes customer personal data including via US affiliates.",
    "goal": "Review the Project Atlas agreement against the firm standard before signing.",
}


def _new_case_with_plan(client):
    case = client.post("/api/cases", json=CASE).json()
    plan = client.post(f"/api/cases/{case['id']}/plan").json()
    return case, plan


def test_approval_gate_blocks_dispatch(client):
    """Nothing is dispatched before the partner approves the plan (architecture.md §14.7)."""
    _, plan = _new_case_with_plan(client)
    assert all(t["status"] == "proposed" for t in plan["tasks"])


def test_plan_proposes_assignee_type_and_severity(client):
    _, plan = _new_case_with_plan(client)
    assert {t["assignee_type"] for t in plan["tasks"]} >= {"ai", "human", "hybrid"}
    assert {t["severity"] for t in plan["tasks"]} >= {"high", "low"}


def test_happy_path_end_to_end(client):
    case, plan = _new_case_with_plan(client)
    plan_id = plan["plan"]["id"]

    # Approve → dispatch. Only the partner (default user) can approve.
    approved = client.post(f"/api/plans/{plan_id}/approve")
    assert approved.status_code == 200

    cockpit = client.get(f"/api/cases/{case['id']}/cockpit").json()
    # Queue sorted highest-risk first; the top item is the high-severity hard-flag DPA review.
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

    # Close → debrief generates from the record.
    debrief = client.post(f"/api/cases/{case['id']}/close").json()
    assert "Case debrief" in debrief["content"]


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


def test_associate_cannot_approve_plan(client):
    _, plan = _new_case_with_plan(client)
    r = client.post(f"/api/plans/{plan['plan']['id']}/approve", headers=ASSOC_HEADERS)
    assert r.status_code == 403


def test_double_approval_is_rejected(client):
    _, plan = _new_case_with_plan(client)
    plan_id = plan["plan"]["id"]
    assert client.post(f"/api/plans/{plan_id}/approve").status_code == 200
    assert client.post(f"/api/plans/{plan_id}/approve").status_code == 409
