from __future__ import annotations

ASSOC_HEADERS = {"X-User-Email": "amara@firm.example", "X-User-Role": "associate"}

CASE = {
    "title": "Project Atlas — supplier agreement review",
    "brief_text": "Supplier processes customer personal data including via US affiliates.",
    "goal": "Review the Project Atlas agreement against the firm standard before signing.",
}


def _approved_case(client):
    case = client.post("/api/cases", json=CASE).json()
    plan = client.post(f"/api/cases/{case['id']}/plan").json()
    client.post(f"/api/plans/{plan['plan']['id']}/approve")
    return case


def _submit_human_task(client, case):
    """Submit the human task so it leaves the inbox into the partner's lanes; return the task."""
    inbox = client.get("/api/inbox", headers=ASSOC_HEADERS).json()
    task = next(i["task"] for i in inbox if i["task"]["assignee_type"] == "human")
    client.post(
        f"/api/tasks/{task['id']}/submit",
        json={"summary": "Initial review.", "findings": []},
        headers=ASSOC_HEADERS,
    )
    return task


def test_reject_returns_human_work_to_associate(client):
    """A reject on human work is not a dead end — it returns to the associate's inbox for rework,
    carrying the partner's note, and can be resubmitted back to the partner."""
    case = _approved_case(client)
    task = _submit_human_task(client, case)

    rejected = client.post(
        f"/api/tasks/{task['id']}/decision",
        json={"action": "reject", "note": "Please cite the governing-law clause."},
    )
    assert rejected.status_code == 200

    detail = client.get(f"/api/tasks/{task['id']}").json()
    assert detail["task"]["status"] == "returned"
    # The partner's reason is in the thread.
    assert any(m["kind"] == "return" and "governing-law" in m["body"] for m in detail["messages"])

    # It is back in the associate's inbox.
    inbox = client.get("/api/inbox", headers=ASSOC_HEADERS).json()
    assert any(i["task"]["id"] == task["id"] for i in inbox)

    # The associate reworks and resubmits → back out of the inbox.
    resub = client.post(
        f"/api/tasks/{task['id']}/submit",
        json={"summary": "Revised: cites Art. 7 governing law.", "findings": []},
        headers=ASSOC_HEADERS,
    )
    assert resub.status_code == 200
    inbox2 = client.get("/api/inbox", headers=ASSOC_HEADERS).json()
    assert not any(i["task"]["id"] == task["id"] for i in inbox2)


def test_associate_question_and_partner_answer_loop(client):
    """Associate → partner question surfaces in the cockpit; the partner's answer returns the task
    to the associate. Both hops are in the audit trail."""
    case = _approved_case(client)
    inbox = client.get("/api/inbox", headers=ASSOC_HEADERS).json()
    task = next(i["task"] for i in inbox if i["task"]["assignee_type"] == "human")

    # Associate raises a question.
    asked = client.post(
        f"/api/tasks/{task['id']}/message",
        json={"body": "Which template version is current — v3 or v4?"},
        headers=ASSOC_HEADERS,
    )
    assert asked.status_code == 200

    detail = client.get(f"/api/tasks/{task['id']}").json()
    assert detail["task"]["status"] == "awaiting_clarification"

    # It surfaces in the partner cockpit's needs-reply lane, not the inbox lane.
    cockpit = client.get(f"/api/cases/{case['id']}/cockpit").json()
    assert any(c["task"]["id"] == task["id"] for c in cockpit["needs_reply"])

    # The partner answers → returns to the associate.
    answered = client.post(
        f"/api/tasks/{task['id']}/message",
        json={"body": "Use v4."},
    )
    assert answered.status_code == 200
    detail2 = client.get(f"/api/tasks/{task['id']}").json()
    assert detail2["task"]["status"] == "returned"
    kinds = [m["kind"] for m in detail2["messages"]]
    assert kinds == ["question", "answer"]

    # Audit trail recorded both hops.
    audit = client.get(f"/api/cases/{case['id']}/audit").json()
    types = {e["type"] for e in audit["accountability"]}
    assert {"clarification_requested", "clarification_answered"} <= types


def test_partner_cannot_answer_when_no_open_question(client):
    case = _approved_case(client)
    task = _submit_human_task(client, case)
    resp = client.post(f"/api/tasks/{task['id']}/message", json={"body": "FYI"})
    assert resp.status_code == 409


def test_reject_on_ai_task_still_escalates(client):
    """AI-only work has no associate to receive a return, so a reject escalates as before."""
    case = _approved_case(client)
    cockpit = client.get(f"/api/cases/{case['id']}/cockpit").json()
    ai_card = next(
        (c for c in cockpit["queue"] if c["task"]["assignee_type"] == "ai"), None
    )
    assert ai_card, "expected an AI task in the review queue"
    rejected = client.post(
        f"/api/tasks/{ai_card['task']['id']}/decision",
        json={"action": "reject", "note": "Redo."},
    )
    assert rejected.status_code == 200
    detail = client.get(f"/api/tasks/{ai_card['task']['id']}").json()
    assert detail["task"]["status"] == "escalated"
