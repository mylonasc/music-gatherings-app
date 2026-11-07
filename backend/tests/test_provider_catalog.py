import httpx

from app.jobs import online
from tests.test_online import make_env


def test_provider_catalog_requires_auth_and_never_fetches_content(tmp_path, monkeypatch):
    app, client, csrf, crew_id = make_env(tmp_path, monkeypatch)
    seen = []

    def handle(request):
        seen.append(request.url.path)
        assert request.url.path == "/v1/capabilities"
        return httpx.Response(200, json={
            "supports_search": True, "supports_fetch": True,
            "allows_storage": False, "artifact_types": ["lyrics"],
            "storage_note": "Reference-only",
        })

    for provider in ("fake", "lrclib", "ultimate_guitar"):
        monkeypatch.setitem(online.PROVIDER_TRANSPORTS, provider, httpx.MockTransport(handle))
    response = client.get("/api/v1/providers")
    assert response.status_code == 200
    assert len(response.json()) == 3 and len(seen) == 3
    assert response.json()[0]["storage_note"] == "Reference-only"
    assert "http://" not in response.text
    client.cookies.clear()
    assert client.get("/api/v1/providers").status_code == 401


def test_catalog_sanitizes_unreachable_service_errors(tmp_path, monkeypatch):
    app, client, csrf, crew_id = make_env(tmp_path, monkeypatch)

    def handle(request):
        raise httpx.ConnectError("internal address secret", request=request)

    for provider in ("fake", "lrclib", "ultimate_guitar"):
        monkeypatch.setitem(online.PROVIDER_TRANSPORTS, provider, httpx.MockTransport(handle))
    response = client.get("/api/v1/providers")
    assert response.status_code == 200
    assert all(not p["available"] for p in response.json())
    assert "secret" not in response.text
