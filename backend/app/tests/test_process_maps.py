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
