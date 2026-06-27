from __future__ import annotations


def test_list_process_maps_includes_seeded_maps(client):
    maps = client.get("/api/process-maps").json()
    ids = {m["id"] for m in maps}
    assert {"process-doc-review", "process-map-nda-fresh"} <= ids
    seeded = next(m for m in maps if m["id"] == "process-doc-review")
    assert "review_binding_obligation" in seeded["task_types"]


def test_create_process_map_starts_clean_slate(client):
    body = {
        "title": "Standard licensing review",
        "task_types": {
            "review_grant": {"label": "Review of the licence grant", "severity": "high"},
            "review_fees": {"label": "Review of fees and royalties", "severity": "medium"},
        },
    }
    created = client.post("/api/process-maps", json=body)
    assert created.status_code == 201
    new_map = created.json()
    assert new_map["title"] == "Standard licensing review"
    assert set(new_map["task_types"]) == {"review_grant", "review_fees"}

    # It appears in the list and has no track record yet.
    assert new_map["id"] in {m["id"] for m in client.get("/api/process-maps").json()}
    rec = client.get(f"/api/track-record?process_doc_id={new_map['id']}").json()
    assert rec["by_section"] == {}


def test_create_process_map_round_trips_worker_spec(client):
    """A section can carry the flexible-worker spec (kind, instruction, checklist, applicable
    checks, requires_standard); it round-trips through create + list (architecture.md §6)."""
    body = {
        "title": "Schedule obligations extraction",
        "task_types": {
            "extract_obligations": {
                "label": "Extract operative obligations",
                "severity": "low",
                "kind": "extract",
                "instruction": "Extract every operative obligation.",
                "checklist": ["List each obligation", "Name the obligated party"],
                "checks": ["citation_support", "multi_run_disagreement"],
                "requires_standard": False,
            }
        },
    }
    created = client.post("/api/process-maps", json=body)
    assert created.status_code == 201
    section = created.json()["task_types"]["extract_obligations"]
    assert section["kind"] == "extract"
    assert section["requires_standard"] is False
    assert section["checks"] == ["citation_support", "multi_run_disagreement"]
    assert section["checklist"] == ["List each obligation", "Name the obligated party"]


def test_seeded_extraction_map_is_listed(client):
    """The seeded non-review process map is selectable and carries its no-standard extract."""
    maps = client.get("/api/process-maps").json()
    extraction = next(m for m in maps if m["id"] == "process-map-extraction")
    section = extraction["task_types"]["extract_obligations"]
    assert section["kind"] == "extract"
    assert section["requires_standard"] is False
