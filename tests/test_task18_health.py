import json

from fastapi.testclient import TestClient

from app import main


class HealthyConnection:
    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def execute(self, _statement):
        return 1


class HealthyEngine:
    def connect(self):
        return HealthyConnection()


def test_health_checks_database_and_adds_request_id(monkeypatch):
    monkeypatch.setattr(main, "engine", HealthyEngine())
    with TestClient(main.app) as client:
        response = client.get("/api/v1/health")
    assert response.status_code == 200
    assert response.json()["database"] == "ok"
    assert response.headers["x-request-id"]


def test_health_returns_service_unavailable_when_database_check_fails(monkeypatch):
    class UnhealthyEngine:
        def connect(self):
            raise OSError("database unavailable")

    monkeypatch.setattr(main, "engine", UnhealthyEngine())
    with TestClient(main.app) as client:
        response = client.get("/api/v1/health")
    assert response.status_code == 503
    assert response.json()["detail"] == "Database health check failed"


def test_json_log_formatter_emits_request_fields():
    record = main.logging.LogRecord("ledgerforge.request", main.logging.INFO, __file__, 1,
        "request_complete", (), None)
    record.request_id = "abc123"
    record.method = "GET"
    record.path = "/api/v1/health"
    record.status_code = 200
    record.duration_ms = 1.25
    payload = json.loads(main.JsonLogFormatter().format(record))
    assert payload["message"] == "request_complete"
    assert payload["request_id"] == "abc123" and payload["status_code"] == 200
