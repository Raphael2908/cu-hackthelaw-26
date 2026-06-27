from __future__ import annotations

from app.config import settings
from app.db.tables import CASES, DECISIONS, FLAGS, TASKS
from app.services import track_record

MAP_A = "process-doc-review"
MAP_B = "process-map-nda-fresh"


def _completed_ai_task(repo, *, case_id, task_type, action="approve", status="signed_off"):
    task = repo.insert(
        TASKS,
        {
            "case_id": case_id,
            "task_type": task_type,
            "assignee_type": "ai",
            "status": status,
            "title": f"prior {task_type}",
            "input_process_section": task_type,
        },
    )
    if status == "signed_off":
        repo.insert(DECISIONS, {"task_id": task["id"], "action": action, "amendment": None})
    return task


# --- apply_record: the pure overlay (no repo) -------------------------------------------------


def test_apply_record_graduates_on_clean_record():
    clean = {"completed": 3, "adverse": 0, "clean": True}
    assignee, rationale = track_record.apply_record(suggested_type="human", section_record=clean)
    assert assignee == "ai"
    assert "clean record" in rationale


def test_apply_record_pulls_back_on_adverse_record():
    adverse = {"completed": 4, "adverse": 2, "clean": False}
    assignee, rationale = track_record.apply_record(suggested_type="ai", section_record=adverse)
    assert assignee == "hybrid"  # AI suggestion pulled back to a human owner
    assert "amended/rejected" in rationale
    # A human suggestion stays human.
    assert track_record.apply_record(suggested_type="human", section_record=adverse)[0] == "human"


def test_apply_record_fresh_map_keeps_suggestion():
    for suggested in ("ai", "human", "hybrid"):
        assignee, rationale = track_record.apply_record(
            suggested_type=suggested, section_record=None
        )
        assert assignee == suggested
        assert "Fresh process map" in rationale


# --- aggregate: per-map scoping ----------------------------------------------------------------


def test_aggregate_is_scoped_per_process_map(in_memory_repo):
    """The seeded prior matter belongs to Map A; Map B must see none of it (no cross-map leak)."""
    rec_a = track_record.aggregate(in_memory_repo, process_doc_id=MAP_A)
    section = rec_a["by_section"]["review_binding_obligation"]
    assert section["completed"] >= settings.AI_TRACK_RECORD_MIN
    assert section["adverse"] == 0
    assert section["clean"] is True
    assert len(rec_a["log"]) >= settings.AI_TRACK_RECORD_MIN

    rec_b = track_record.aggregate(in_memory_repo, process_doc_id=MAP_B)
    assert rec_b["by_section"] == {}
    assert rec_b["log"] == []


def test_aggregate_marks_adverse_history_not_clean(in_memory_repo):
    case = in_memory_repo.insert(CASES, {"process_doc_id": MAP_B, "status": "closed"})
    for _ in range(settings.AI_TRACK_RECORD_MIN):
        _completed_ai_task(in_memory_repo, case_id=case["id"], task_type="review_governing_law")
    # One amendment makes the whole section "not clean".
    _completed_ai_task(
        in_memory_repo, case_id=case["id"], task_type="review_governing_law", action="amend"
    )
    section = track_record.aggregate(in_memory_repo, process_doc_id=MAP_B)["by_section"][
        "review_governing_law"
    ]
    assert section["adverse"] == 1
    assert section["amended"] == 1
    assert section["clean"] is False


def test_section_carries_flag_breakdown_lessons_and_cases(in_memory_repo):
    """Beyond the outcome counts, each section surfaces the feedback detail a partner reads: flags
    by checker signal (hard/soft), the carry-forward lesson (the partner's own words), and the
    matters the section ran in."""
    case = in_memory_repo.insert(
        CASES, {"process_doc_id": MAP_B, "status": "closed", "title": "Atlas review"}
    )
    task = in_memory_repo.insert(
        TASKS,
        {
            "case_id": case["id"],
            "task_type": "review_binding_obligation",
            "assignee_type": "ai",
            "status": "signed_off",
            "title": "binding obligation",
            "input_process_section": "Binding obligation",
        },
    )
    in_memory_repo.insert(
        DECISIONS,
        {"task_id": task["id"], "action": "amend", "amendment": "Raise liability cap to 100%."},
    )
    in_memory_repo.insert(
        FLAGS,
        {"task_id": task["id"], "signal_type": "citation_support", "hard": True, "title": "Fab"},
    )
    in_memory_repo.insert(
        FLAGS,
        {"task_id": task["id"], "signal_type": "precedent_deviation", "hard": False, "title": "D"},
    )

    section = track_record.aggregate(in_memory_repo, process_doc_id=MAP_B)["by_section"][
        "review_binding_obligation"
    ]
    assert section["flags_by_signal"]["citation_support"] == {"count": 1, "hard": 1}
    assert section["flags_by_signal"]["precedent_deviation"]["count"] == 1
    assert section["hard_flags"] == 1
    lesson = section["lessons"][0]
    assert lesson["action"] == "amend" and "liability cap" in lesson["text"]
    assert lesson["case_id"] == case["id"] and lesson["case_title"] == "Atlas review"
    assert section["cases"][0]["case_id"] == case["id"] and section["cases"][0]["adverse"] == 1


def test_escalated_task_counts_as_adverse(in_memory_repo):
    case = in_memory_repo.insert(CASES, {"process_doc_id": MAP_B, "status": "closed"})
    _completed_ai_task(
        in_memory_repo, case_id=case["id"], task_type="review_recital_summary", status="escalated"
    )
    section = track_record.aggregate(in_memory_repo, process_doc_id=MAP_B)["by_section"][
        "review_recital_summary"
    ]
    assert section["escalated"] == 1
    assert section["adverse"] == 1


# --- planner integration -----------------------------------------------------------------------


def test_planner_graduates_seeded_section_to_ai(client):
    """A case on the seeded (reused) map proposes the binding-obligation section as AI, citing the
    map's clean track record."""
    case = client.post("/api/cases", json={
        "title": "New DPA review",
        "brief_text": "supplier data processing",
        "goal": "review the agreement",
        "severity": "high",
    }).json()
    plan = client.post(f"/api/cases/{case['id']}/plan").json()
    task = next(t for t in plan["tasks"] if t["task_type"] == "review_binding_obligation")
    assert task["assignee_type"] == "ai"
    assert "clean record" in task["assignee_rationale"]


def test_planner_clean_slate_on_fresh_map(client):
    """A case on the fresh map carries the clean-slate rationale (no graduation)."""
    case = client.post("/api/cases", json={
        "title": "NDA review",
        "brief_text": "mutual NDA",
        "goal": "review the NDA",
        "severity": "high",
        "process_doc_id": MAP_B,
    }).json()
    plan = client.post(f"/api/cases/{case['id']}/plan").json()
    assert plan["tasks"]
    assert all("Fresh process map" in t["assignee_rationale"] for t in plan["tasks"])


def test_track_record_endpoint_reports_graduated_section(client):
    rec = client.get(f"/api/track-record?process_doc_id={MAP_A}").json()
    assert rec["by_section"]["review_binding_obligation"]["clean"] is True
    # The fresh map has nothing yet.
    assert client.get(f"/api/track-record?process_doc_id={MAP_B}").json()["by_section"] == {}
