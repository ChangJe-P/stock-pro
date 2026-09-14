from fastapi.testclient import TestClient

from app import main


def _client() -> TestClient:
    return TestClient(main.app)


def test_health_ok_when_db_connected(monkeypatch):
    monkeypatch.setattr(main, "check_database", lambda: True)
    res = _client().get("/health")
    assert res.status_code == 200
    body = res.json()
    assert body["status"] == "ok"
    assert body["database"] == "connected"


def test_health_503_when_db_down(monkeypatch):
    # DB 연결 실패를 정상 상태로 보고하지 않는지 확인한다.
    monkeypatch.setattr(main, "check_database", lambda: False)
    res = _client().get("/health")
    assert res.status_code == 503
    body = res.json()
    assert body["status"] == "unhealthy"
    assert body["database"] == "unavailable"
