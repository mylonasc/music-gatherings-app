"""S14 backend tests: admin-only access, profiles, isolated previews, audit."""

import httpx

from app.jobs import online as online_module
from app.models import AuditEvent
from tests.conftest import make_test_app
from tests.test_auth import login, seed_admin


def make_apps(tmp_path, monkeypatch):  # type: ignore[no-untyped-def]
    app, admin_client = make_test_app(tmp_path, monkeypatch)
    _admin_id, _crew_id = seed_admin(app)
    csrf = login(admin_client, "admin", "admin-pass-1")
    return app, admin_client, csrf


def make_member(app, admin_client, csrf, username="mem", password="s3cret-long"):  # type: ignore[no-untyped-def]
    from fastapi.testclient import TestClient

    created = admin_client.post(
        "/api/v1/access-requests", json={"username": username, "password": password}
    )
    admin_client.post(
        f"/api/v1/access-requests/{created.json()['id']}/approve",
        headers={"X-CSRF-Token": csrf},
    )
    member_client = TestClient(app)
    member_csrf = login(member_client, username, password)
    return member_client, member_csrf


def install_processor(monkeypatch, validate_payload=None, process_payload=None):  # type: ignore[no-untyped-def]
    seen = {"validate": 0, "process": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/v1/validate-profile":
            seen["validate"] += 1
            return httpx.Response(200, json=validate_payload or {"valid": True, "errors": []})
        if request.url.path == "/v1/process":
            seen["process"] += 1
            return httpx.Response(
                200,
                json=process_payload
                or {
                    "outputs": {"lyrics_html": "<p>hi</p>"},
                    "warnings": [],
                    "processor_version": "0.1.0",
                },
            )
        return httpx.Response(404, json={})

    monkeypatch.setattr(
        online_module, "PROCESSOR_TRANSPORT", httpx.MockTransport(handler)
    )
    return seen


def install_provider(monkeypatch, provider="fake", payload=None):  # type: ignore[no-untyped-def]
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=payload or {"items": [], "provider": provider})

    monkeypatch.setitem(
        online_module.PROVIDER_TRANSPORTS, provider, httpx.MockTransport(handler)
    )


def test_admin_endpoints_reject_non_admins(tmp_path, monkeypatch):  # type: ignore[no-untyped-def]
    app, admin_client, csrf = make_apps(tmp_path, monkeypatch)
    member_client, member_csrf = make_member(app, admin_client, csrf)
    from fastapi.testclient import TestClient

    anon = TestClient(app)
    for method, path, body in [
        ("get", "/api/v1/admin/providers", None),
        ("get", "/api/v1/admin/processing-profiles", None),
        ("get", "/api/v1/admin/jobs", None),
        ("get", "/api/v1/admin/audit", None),
        ("post", "/api/v1/admin/tests/provider-search", {"provider": "fake", "query": "x"}),
        ("post", "/api/v1/admin/tests/process", {"source_text": "hi", "profile": {}}),
        ("post", "/api/v1/admin/processing-profiles", {"name": "x"}),
    ]:
        assert anon.request(method, path, json=body).status_code == 401
        response = member_client.request(
            method, path, json=body, headers={"X-CSRF-Token": member_csrf}
        )
        assert response.status_code == 403, (method, path, response.text)


def test_provider_status_and_isolated_search(tmp_path, monkeypatch):  # type: ignore[no-untyped-def]
    from sqlalchemy import select

    from app.models import Track

    app, admin_client, csrf = make_apps(tmp_path, monkeypatch)
    install_provider(
        monkeypatch,
        "fake",
        {"items": [{"provider": "fake", "external_id": "fake-song-1"}], "provider": "fake"},
    )
    statuses = admin_client.get("/api/v1/admin/providers").json()
    assert {s["provider"] for s in statuses} >= {"fake", "genius", "ultimate_guitar"}
    fake_status = next(s for s in statuses if s["provider"] == "fake")
    assert fake_status["reachable"] is True

    with make_session(app) as db:
        assert db.execute(select(Track)).scalars().all() == []
    searched = admin_client.post(
        "/api/v1/admin/tests/provider-search",
        json={"provider": "fake", "query": "blue"},
        headers={"X-CSRF-Token": csrf},
    )
    assert searched.status_code == 200, searched.text
    assert searched.json()["items"][0]["external_id"] == "fake-song-1"
    with make_session(app) as db:
        # Isolated by design: testing never writes library content.
        assert db.execute(select(Track)).scalars().all() == []


def make_session(app):  # type: ignore[no-untyped-def]
    from contextlib import contextmanager

    @contextmanager
    def _session():  # type: ignore[no-untyped-def]
        session = app.state.session_factory()
        try:
            yield session
        finally:
            session.close()

    return _session()


def test_profiles_validated_and_audited(tmp_path, monkeypatch):  # type: ignore[no-untyped-def]
    from sqlalchemy import select

    app, admin_client, csrf = make_apps(tmp_path, monkeypatch)
    seen = install_processor(monkeypatch)
    created = admin_client.post(
        "/api/v1/admin/processing-profiles",
        json={
            "name": "lyrics",
            "steps": [{"type": "transpose", "config": {"semitones": 2}}],
            "outputs": ["lyrics_html"],
        },
        headers={"X-CSRF-Token": csrf},
    )
    assert created.status_code == 201, created.text
    assert created.json()["version"] == 1
    second = admin_client.post(
        "/api/v1/admin/processing-profiles",
        json={"name": "lyrics", "steps": [], "outputs": []},
        headers={"X-CSRF-Token": csrf},
    )
    assert second.json()["version"] == 2
    listed = admin_client.get("/api/v1/admin/processing-profiles").json()
    assert len(listed) == 2
    deactivated = admin_client.post(
        f"/api/v1/admin/processing-profiles/{created.json()['id']}/deactivate",
        headers={"X-CSRF-Token": csrf},
    )
    assert deactivated.json()["is_active"] is False
    assert seen["validate"] >= 2
    with make_session(app) as db:
        actions = {r.action for r in db.execute(select(AuditEvent)).scalars().all()}
    assert "admin.profile_created" in actions
    assert "admin.profile_deactivated" in actions

    install_processor(
        monkeypatch, validate_payload={"valid": False, "errors": ["bad step"]}
    )
    bad = admin_client.post(
        "/api/v1/admin/processing-profiles",
        json={"name": "bad", "steps": [], "outputs": []},
        headers={"X-CSRF-Token": csrf},
    )
    assert bad.status_code == 422


def test_process_preview_is_isolated(tmp_path, monkeypatch):  # type: ignore[no-untyped-def]
    from sqlalchemy import select

    from app.models import Artifact, Track

    app, admin_client, csrf = make_apps(tmp_path, monkeypatch)
    install_processor(monkeypatch)
    preview = admin_client.post(
        "/api/v1/admin/tests/process",
        json={
            "source_text": "hello",
            "profile": {"schema_version": 1, "steps": [], "outputs": ["lyrics_html"]},
        },
        headers={"X-CSRF-Token": csrf},
    )
    assert preview.status_code == 200
    assert preview.json()["outputs"]["lyrics_html"] == "<p>hi</p>"
    with make_session(app) as db:
        assert db.execute(select(Track)).scalars().all() == []
        assert db.execute(select(Artifact)).scalars().all() == []


def test_jobs_and_audit_visible_to_admin(tmp_path, monkeypatch):  # type: ignore[no-untyped-def]
    app, admin_client, csrf = make_apps(tmp_path, monkeypatch)
    jobs = admin_client.get("/api/v1/admin/jobs").json()
    assert jobs["total"] == 0
    audit = admin_client.get("/api/v1/admin/audit").json()
    assert isinstance(audit, list)
    filtered = admin_client.get("/api/v1/admin/audit", params={"action": "nope"}).json()
    assert filtered == []
