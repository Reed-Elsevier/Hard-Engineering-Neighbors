from fastapi.testclient import TestClient

from sabwat.api import app


def test_health_reports_status():
    body = TestClient(app).get("/api/health").json()
    assert body["status"] == "ok"
    assert {"data_available", "model_available", "llm_enabled"} <= body.keys()
