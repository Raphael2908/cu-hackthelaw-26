from __future__ import annotations


def test_healthz(client):
    res = client.get("/healthz")
    assert res.status_code == 200
    assert res.json() == {"status": "ok"}


def test_api_healthz(client):
    res = client.get("/api/healthz")
    assert res.status_code == 200
