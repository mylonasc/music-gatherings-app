"""Authentication flows: request, approve, login, expiry, revocation, throttle."""

from sqlalchemy import select

from app.core.security import hash_password
from app.models import AuditEvent, CrewMembership, User
from tests.conftest import make_test_app


def seed_admin(app, username="admin", password="admin-pass-1"):  # type: ignore[no-untyped-def]
    from app.api.v1.access_requests import get_or_create_default_crew

    factory = app.state.session_factory
    with factory() as db:
        admin = User(
            username=username,
            password_hash=hash_password(password),
            status="active",
            is_admin=True,
        )
        db.add(admin)
        db.flush()
        crew = get_or_create_default_crew(db)
        db.add(CrewMembership(crew_id=crew.id, user_id=admin.id, role="owner"))
        db.commit()
        return admin.id, crew.id


def login(client, username, password):  # type: ignore[no-untyped-def]
    response = client.post("/api/v1/auth/login", json={"username": username, "password": password})
    assert response.status_code == 200, response.text
    return response.json()["csrf_token"]


def test_full_access_flow(tmp_path, monkeypatch):  # type: ignore[no-untyped-def]
    app, client = make_test_app(tmp_path, monkeypatch)
    admin_id, crew_id = seed_admin(app)

    created = client.post(
        "/api/v1/access-requests",
        json={"username": "mia", "password": "s3cret-long", "message": "drummer"},
    )
    assert created.status_code == 201, created.text
    request_id = created.json()["id"]

    # Non-admin approval is covered in test_non_admin_cannot_approve.
    csrf = login(client, "admin", "admin-pass-1")
    approved = client.post(
        f"/api/v1/access-requests/{request_id}/approve", headers={"X-CSRF-Token": csrf}
    )
    assert approved.status_code == 200, approved.text
    assert approved.json()["status"] == "approved"

    # Approved user is a member of the default crew.
    factory = app.state.session_factory
    with factory() as db:
        user = db.execute(select(User).where(User.username == "mia")).scalar_one()
        membership = db.execute(
            select(CrewMembership).where(
                CrewMembership.crew_id == crew_id, CrewMembership.user_id == user.id
            )
        ).scalar_one_or_none()
        assert membership is not None
        assert user.password_hash.startswith("$argon2")

    # Login -> me -> logout -> me is unauthorized.
    from fastapi.testclient import TestClient

    user_client = TestClient(app)
    user_csrf = login(user_client, "mia", "s3cret-long")
    me = user_client.get("/api/v1/auth/me")
    assert me.status_code == 200
    assert me.json()["user"]["username"] == "mia"
    assert me.json()["user"]["is_admin"] is False
    assert me.json()["csrf_token"] == user_csrf
    done = user_client.post("/api/v1/auth/logout", headers={"X-CSRF-Token": user_csrf})
    assert done.status_code == 204
    assert user_client.get("/api/v1/auth/me").status_code == 401


def test_non_admin_cannot_approve(tmp_path, monkeypatch):  # type: ignore[no-untyped-def]
    from fastapi.testclient import TestClient

    app, admin_client = make_test_app(tmp_path, monkeypatch)
    seed_admin(app)
    csrf = login(admin_client, "admin", "admin-pass-1")
    created = admin_client.post(
        "/api/v1/access-requests", json={"username": "ned", "password": "s3cret-long"}
    )
    request_id = created.json()["id"]
    approved = admin_client.post(
        f"/api/v1/access-requests/{request_id}/approve", headers={"X-CSRF-Token": csrf}
    )
    assert approved.status_code == 200
    user_client = TestClient(app)
    user_csrf = login(user_client, "ned", "s3cret-long")
    other = user_client.post(
        "/api/v1/access-requests", json={"username": "kim", "password": "s3cret-long"}
    )
    other_id = other.json()["id"]
    forbidden = user_client.post(
        f"/api/v1/access-requests/{other_id}/approve", headers={"X-CSRF-Token": user_csrf}
    )
    assert forbidden.status_code == 403
    assert user_client.get("/api/v1/access-requests").status_code == 403


def test_login_rejects_bad_credentials(tmp_path, monkeypatch):  # type: ignore[no-untyped-def]
    app, client = make_test_app(tmp_path, monkeypatch)
    seed_admin(app)
    bad = client.post("/api/v1/auth/login", json={"username": "admin", "password": "wrong"})
    assert bad.status_code == 401
    assert bad.json() == {"detail": "invalid credentials"}
    missing = client.post("/api/v1/auth/login", json={"username": "ghost", "password": "x" * 9})
    assert missing.status_code == 401
    assert missing.json() == {"detail": "invalid credentials"}


def test_disabled_user_cannot_login(tmp_path, monkeypatch):  # type: ignore[no-untyped-def]
    app, client = make_test_app(tmp_path, monkeypatch)
    factory = app.state.session_factory
    with factory() as db:
        db.add(User(username="hal", password_hash=hash_password("s3cret-long"), status="disabled"))
        db.commit()
    response = client.post(
        "/api/v1/auth/login", json={"username": "hal", "password": "s3cret-long"}
    )
    assert response.status_code == 401


def test_csrf_required_on_mutations(tmp_path, monkeypatch):  # type: ignore[no-untyped-def]
    app, client = make_test_app(tmp_path, monkeypatch)
    seed_admin(app)
    csrf = login(client, "admin", "admin-pass-1")
    no_header = client.post("/api/v1/crews", json={"name": "X"})
    assert no_header.status_code == 403
    wrong = client.post("/api/v1/crews", json={"name": "X"}, headers={"X-CSRF-Token": "bogus"})
    assert wrong.status_code == 403
    ok = client.post("/api/v1/crews", json={"name": "X"}, headers={"X-CSRF-Token": csrf})
    assert ok.status_code == 201, ok.text


def test_expired_session_rejected(tmp_path, monkeypatch):  # type: ignore[no-untyped-def]
    from datetime import timedelta

    from app.models.base import utcnow_naive

    app, client = make_test_app(tmp_path, monkeypatch)
    seed_admin(app)
    login(client, "admin", "admin-pass-1")
    factory = app.state.session_factory
    with factory() as db:
        from app.models import AuthSession

        row = db.execute(select(AuthSession)).scalar_one()
        row.expires_at = utcnow_naive() - timedelta(seconds=1)
        db.commit()
    assert client.get("/api/v1/auth/me").status_code == 401


def test_login_throttled(tmp_path, monkeypatch):  # type: ignore[no-untyped-def]
    app, client = make_test_app(
        tmp_path,
        monkeypatch,
        MUSIC_GATHERINGS_LOGIN_MAX_ATTEMPTS="3",
        MUSIC_GATHERINGS_LOGIN_WINDOW_SECONDS="300",
    )
    seed_admin(app)
    for _ in range(3):
        response = client.post(
            "/api/v1/auth/login", json={"username": "admin", "password": "wrong"}
        )
        assert response.status_code == 401
    limited = client.post(
        "/api/v1/auth/login", json={"username": "admin", "password": "admin-pass-1"}
    )
    assert limited.status_code == 429


def test_audit_trail_for_login(tmp_path, monkeypatch):  # type: ignore[no-untyped-def]
    app, client = make_test_app(tmp_path, monkeypatch)
    seed_admin(app)
    login(client, "admin", "admin-pass-1")
    client.post("/api/v1/auth/login", json={"username": "admin", "password": "wrong"})
    factory = app.state.session_factory
    with factory() as db:
        actions = sorted(
            r.action for r in db.execute(select(AuditEvent)).scalars().all()
        )
    assert "auth.login" in actions
    assert "auth.login_failed" in actions
