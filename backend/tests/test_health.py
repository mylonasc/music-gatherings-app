from fastapi.testclient import TestClient

from app.main import create_app


def test_health_endpoints() -> None:
    client = TestClient(create_app())
    for path in ("/health", "/api/v1/health"):
        response = client.get(path)
        assert response.status_code == 200
        body = response.json()
        assert body["status"] == "ok"
        assert body["service"] == "backend"
