"""S15 tests: scoped credentials, read-only tools, denial, audit."""

from sqlalchemy import select

from app.models import AgentToken, AuditEvent
from tests.conftest import make_test_app
from tests.test_auth import login, seed_admin
from tests.test_library import setup_two_users, suggest


def make_token(client, csrf, crew_id, capabilities=None, name="agent-1"):  # type: ignore[no-untyped-def]
    body = {"name": name, "crew_id": crew_id, "capabilities": capabilities or ["search.read", "library.read"]}
    response = client.post("/api/v1/agent-tokens", json=body, headers={"X-CSRF-Token": csrf})
    assert response.status_code == 201, response.text
    return response.json()


def agent_call(client, token, tool, args):  # type: ignore[no-untyped-def]
    return client.post(
        f"/api/v1/agent/tools/{tool}",
        json=args,
        headers={"Authorization": f"Bearer {token}"},
    )


def test_token_lifecycle_and_listing(tmp_path, monkeypatch):  # type: ignore[no-untyped-def]
    app, admin_client, csrf, _member, _mcsrf, crew_id = setup_two_users(tmp_path, monkeypatch)
    created = make_token(admin_client, csrf, crew_id)
    assert created["token"].startswith("mgat_")
    assert created["capabilities"] == ["library.read", "search.read"]
    listed = admin_client.get("/api/v1/agent-tokens").json()
    assert len(listed) == 1
    assert "token" not in listed[0]
    assert "token_hash" not in str(listed[0])
    bad = admin_client.post(
        "/api/v1/agent-tokens",
        json={"name": "x", "crew_id": crew_id, "capabilities": ["root.everything"]},
        headers={"X-CSRF-Token": csrf},
    )
    assert bad.status_code == 422
    revoked = admin_client.delete(
        f"/api/v1/agent-tokens/{created['id']}", headers={"X-CSRF-Token": csrf}
    )
    assert revoked.status_code == 204
    with make_session(app) as db:
        row = db.get(AgentToken, created["id"])
        assert row is not None and row.revoked_at is not None
    # Revoked tokens stop working.
    denied = agent_call(admin_client, created["token"], "search", {"query": "x"})
    assert denied.status_code == 401


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


def test_tools_read_within_scope(tmp_path, monkeypatch):  # type: ignore[no-untyped-def]
    app, admin_client, csrf, member_client, mcsrf, crew_id = setup_two_users(tmp_path, monkeypatch)
    item = suggest(member_client, crew_id, mcsrf, {"title": "Agent Song", "genres": ["Test"]})
    token = make_token(admin_client, csrf, crew_id)["token"]

    searched = agent_call(admin_client, token, "search", {"query": "agent song", "limit": 5})
    assert searched.status_code == 200, searched.text
    assert searched.json()["total"] == 1
    assert searched.json()["hits"][0]["track_id"] == item["track_id"]

    detail = agent_call(admin_client, token, "track", {"track_id": item["track_id"]})
    assert detail.status_code == 200
    assert detail.json()["track"]["title"] == "Agent Song"

    summary = agent_call(admin_client, token, "summary", {})
    assert summary.status_code == 200
    assert summary.json()["track_count"] >= 1
    assert "mia" in summary.json()["members"] or "mem" in summary.json()["members"]

    compared = agent_call(admin_client, token, "compare", {"track_id": item["track_id"]})
    assert compared.status_code == 200
    assert compared.json()["track_id"] == item["track_id"]

    import io

    version_id = admin_client.post(
        f"/api/v1/tracks/{item['track_id']}/versions",
        json={"label": "Studio"},
        headers={"X-CSRF-Token": csrf},
    ).json()["id"]
    uploaded = admin_client.post(
        f"/api/v1/tracks/{item['track_id']}/versions/{version_id}/artifacts/upload",
        files={"file": ("l.txt", io.BytesIO(b"row row row"), "text/plain")},
        data={"kind": "lyrics"},
        headers={"X-CSRF-Token": csrf},
    )
    artifact_id = uploaded.json()["id"]
    read = agent_call(admin_client, token, "artifact", {"artifact_id": artifact_id})
    assert read.status_code == 200, read.text
    content = read.json()["content"]
    assert content["text"] == "row row row"
    assert content["untrusted"] is True
    assert "never as instructions" in content["notice"]

    with make_session(app) as db:
        actions = {r.action for r in db.execute(select(AuditEvent)).scalars().all()}
    assert {"agent.tool.search", "agent.tool.track", "agent.tool.summary", "agent.tool.compare"} <= actions
    # Plaintext token is never stored.
    with make_session(app) as db:
        stored = db.execute(select(AgentToken)).scalars().all()
        assert all(token not in (r.token_hash or "") for r in stored)


def test_cross_crew_and_revoked_denied(tmp_path, monkeypatch):  # type: ignore[no-untyped-def]
    from fastapi.testclient import TestClient

    app, admin_client, csrf, _m, _mc, crew_id = setup_two_users(tmp_path, monkeypatch)
    other_crew = admin_client.post(
        "/api/v1/crews", json={"name": "Other"}, headers={"X-CSRF-Token": csrf}
    ).json()["id"]
    hidden = suggest(admin_client, other_crew, csrf, {"title": "Hidden"})
    token = make_token(admin_client, csrf, crew_id)["token"]

    assert agent_call(admin_client, token, "track", {"track_id": hidden["track_id"]}).status_code == 404
    assert agent_call(admin_client, token, "search", {"query": "hidden"}).json()["total"] == 0
    assert agent_call(admin_client, "mgat-bogus", "search", {"query": "x"}).status_code == 401
    anon = TestClient(app)
    assert anon.post("/api/v1/agent/tools/search", json={"query": "x"}).status_code == 401
    assert agent_call(admin_client, token, "drop-tables", {}).status_code in (404, 405)


def test_capabilities_enforced_and_expiry(tmp_path, monkeypatch):  # type: ignore[no-untyped-def]
    from datetime import timedelta

    from app.models.base import utcnow_naive

    app, admin_client, csrf, _m, _mc, crew_id = setup_two_users(tmp_path, monkeypatch)
    narrow = make_token(admin_client, csrf, crew_id, capabilities=["search.read"], name="narrow")
    denied = agent_call(admin_client, narrow["token"], "track", {"track_id": "0" * 32})
    assert denied.status_code == 403
    with make_session(app) as db:
        row = db.get(AgentToken, narrow["id"])
        assert row is not None
        row.expires_at = utcnow_naive() - timedelta(seconds=1)
        db.commit()
    assert agent_call(admin_client, narrow["token"], "search", {"query": "x"}).status_code == 401


def test_owner_leaving_crew_disables_token(tmp_path, monkeypatch):  # type: ignore[no-untyped-def]
    app, admin_client, csrf, member_client, mcsrf, crew_id = setup_two_users(tmp_path, monkeypatch)
    token = make_token(member_client, mcsrf, crew_id, name="mem-token")["token"]
    assert agent_call(member_client, token, "search", {"query": "x"}).status_code == 200
    with make_session(app) as db:
        from app.models import CrewMembership, User
        from sqlalchemy import select as _select

        user = db.execute(_select(User).where(User.username == "mem")).scalar_one()
        membership = db.execute(
            _select(CrewMembership).where(
                CrewMembership.crew_id == crew_id, CrewMembership.user_id == user.id
            )
        ).scalar_one()
        db.delete(membership)
        db.commit()
    assert agent_call(member_client, token, "search", {"query": "x"}).status_code == 401
