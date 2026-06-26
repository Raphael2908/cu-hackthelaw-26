from __future__ import annotations


def test_pipeline_runs_end_to_end_in_mock_mode(client):
    """POST /tasks enqueues the chain; eager Celery runs it inline to completion in mock mode."""
    res = client.post(
        "/api/tasks",
        json={
            "title": "Acme M&A",
            "brief": "First-draft M&A plan for the Acme/Beta merger.",
            "eval_doc_count": 2,
        },
    )
    task_id = res.json()["id"]

    # Task reaches a terminal state and produced an output.
    detail = client.get(f"/api/tasks/{task_id}").json()
    assert detail["status"] == "complete"
    assert detail["plan_md"]

    output = client.get(f"/api/tasks/{task_id}/output").json()
    assert output["version"] == 1
    assert output["content_md"]


def test_pipeline_ranks_and_evaluates_top_n(client):
    res = client.post(
        "/api/tasks",
        json={"title": "Acme M&A", "brief": "merger plan", "eval_doc_count": 2},
    )
    task_id = res.json()["id"]

    candidates = client.get(f"/api/tasks/{task_id}/candidates").json()
    assert candidates, "research should have produced candidates"
    # All candidates ranked.
    assert all(c["rank"] is not None for c in candidates)
    # Exactly N (=2) evaluated.
    evaluated = [c for c in candidates if c["evaluated"]]
    assert len(evaluated) == 2
    assert all(c["use_in_synthesis"] for c in evaluated)
