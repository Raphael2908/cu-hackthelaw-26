from __future__ import annotations


def test_create_and_get_task(client):
    res = client.post(
        "/api/tasks",
        json={"title": "Acme M&A", "brief": "First-draft M&A plan for Acme/Beta merger."},
    )
    assert res.status_code == 200
    task = res.json()
    assert task["title"] == "Acme M&A"
    assert task["user_id"] == "u1"
    assert task["eval_doc_count"] == 5  # DEFAULT_EVAL_DOC_COUNT

    got = client.get(f"/api/tasks/{task['id']}")
    assert got.status_code == 200
    assert got.json()["id"] == task["id"]


def test_list_tasks_scoped_to_user(client):
    client.post("/api/tasks", json={"title": "T1", "brief": "b"})
    res = client.get("/api/tasks")
    assert res.status_code == 200
    assert len(res.json()) == 1


def test_get_missing_task_404(client):
    res = client.get("/api/tasks/does-not-exist")
    assert res.status_code == 404


def test_presign_upload(client):
    res = client.post(
        "/api/uploads/presign",
        json={"filename": "deed.pdf", "content_type": "application/pdf", "size_bytes": 1024},
    )
    assert res.status_code == 200
    body = res.json()
    assert body["s3_key"].endswith("deed.pdf")
    assert body["url"]
