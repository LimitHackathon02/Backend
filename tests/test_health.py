from fastapi.testclient import TestClient

from app.main import app


def test_health():
    res = TestClient(app).get("/health")
    assert res.status_code == 200
    body = res.json()
    assert body["ok"] is True
    assert "mock" in body
