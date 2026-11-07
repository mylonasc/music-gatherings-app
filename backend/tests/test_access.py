"""Access-request edge cases and crew membership authorization."""

from sqlalchemy import select

from app.models import User
from tests.conftest import make_test_app
from tests.test_auth import login, seed_admin


def test_duplicate_requests_rejected(tmp_path, monkeypatch):  # type: ignore[no-untyped-def]
    _app, client = make_test_app(tmp_path, monkeypatch)
    first = client.post(
        "/api/v1/access-requests", json={"username": "sam", "password": "s3cret-long"}
    )
    assert first.status_code == 201
    again = client.post(
        "/api/v1/access-requests", json={"username": "sam", "password": "s3cret-long"}
    )
    assert again.status_code == 409


def test_existing_username_rejected(tmp_path, monkeypatch):  # type: ignore[no-untyped-def]
    app, client = make_test_app(tmp_path, monkeypatch)
    seed_admin(app)
    taken = client.post(
        "/api/v1/access-requests", json={"username": "admin", "password": "s3cret-long"}
    )
    assert taken.status_code == 409


def test_approve_reject_edge_cases(tmp_path, monkeypatch):  # type: ignore[no-untyped-def]
    app, client = make_test_app(tmp_path, monkeypatch)
    seed_admin(app)
    csrf = login(client, "admin", "admin-pass-1")

    missing = client.post(
        "/api/v1/access-requests/!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!/approve",
        headers={"X-CSRF-Token": csrf},
    )
    assert missing.status_code == 404

    created = client.post(
        "/api/v1/access-requests", json={"username": "ruth", "password": "s3cret-long"}
    )
    request_id = created.json()["id"]
    rejected = client.post(
        f"/api/v1/access-requests/{request_id}/reject", headers={"X-CSRF-Token": csrf}
    )
    assert rejected.status_code == 200
    assert rejected.json()["status"] == "rejected"
    # Decided requests cannot be decided again.
    assert (
        client.post(
            f"/api/v1/access-requests/{request_id}/approve",
            headers={"X-CSRF-Token": csrf},
        ).status_code
        == 409
    )
    factory = app.state.session_factory
    with factory() as db:
        assert (
            db.execute(select(User).where(User.username == "ruth")).scalar_one_or_none()
            is None
        )


def test_access_request_listing_requires_admin(tmp_path, monkeypatch):  # type: ignore[no-untyped-def]
    from fastapi.testclient import TestClient

    app, client = make_test_app(tmp_path, monkeypatch)
    seed_admin(app)
    assert client.get("/api/v1/access-requests").status_code == 401
    login(client, "admin", "admin-pass-1")
    listed = client.get("/api/v1/access-requests")
    assert listed.status_code == 200

    other = TestClient(app)
    login(other, "admin", "admin-pass-1")
    assert other.get("/api/v1/access-requests").status_code == 200
    assert isinstance(listed.json(), list)


def test_guessed_ids_and_nonmember_access(tmp_path, monkeypatch):  # type: ignore[no-untyped-def]
    from fastapi.testclient import TestClient

    app, client = make_test_app(tmp_path, monkeypatch)
    _admin_id, crew_id = seed_admin(app)
    assert client.get(f"/api/v1/crews/{crew_id}/members").status_code == 401

    csrf = login(client, "admin", "admin-pass-1")
    created = client.post(
        "/api/v1/access-requests", json={"username": "ted", "password": "s3cret-long"}
    )
    client.post(
        f"/api/v1/access-requests/{created.json()['id']}/approve",
        headers={"X-CSRF-Token": csrf},
    )
    member_client = TestClient(app)
    member_csrf = login(member_client, "ted", "s3cret-long")

    # A member sees the default crew and its roster.
    mine = member_client.get("/api/v1/crews")
    assert mine.status_code == 200
    assert any(c["id"] == crew_id for c in mine.json())
    roster = member_client.get(f"/api/v1/crews/{crew_id}/members")
    assert roster.status_code == 200
    assert {m["username"] for m in roster.json()} >= {"admin", "ted"}

    # Guessed crew IDs and non-member crews are indistinguishable 404s.
    assert (
        member_client.get("/api/v1/crews/0badf00d0badf00d0badf00d0badf00d/members").status_code
        == 404
    )
    new_crew = client.post(
        "/api/v1/crews", json={"name": "Secret"}, headers={"X-CSRF-Token": csrf}
    ).json()
    assert member_client.get(f"/api/v1/crews/{new_crew['id']}/members").status_code == 404
    # Non-admins cannot create crews or manage members.
    denied = member_client.post(
        "/api/v1/crews",
        json={"name": "Nope"},
        headers={"X-CSRF-Token": member_csrf},
    )
    assert denied.status_code == 403


def test_admin_member_management(tmp_path, monkeypatch):  # type: ignore[no-untyped-def]
    from fastapi.testclient import TestClient

    app, client = make_test_app(tmp_path, monkeypatch)
    _admin_id, crew_id = seed_admin(app)
    csrf = login(client, "admin", "admin-pass-1")
    created = client.post(
        "/api/v1/access-requests", json={"username": "uma", "password": "s3cret-long"}
    )
    client.post(
        f"/api/v1/access-requests/{created.json()['id']}/approve",
        headers={"X-CSRF-Token": csrf},
    )
    factory = app.state.session_factory
    with factory() as db:
        uma = db.execute(select(User).where(User.username == "uma")).scalar_one()

    second = client.post(
        "/api/v1/crews", json={"name": "Second"}, headers={"X-CSRF-Token": csrf}
    )
    assert second.status_code == 201
    second_id = second.json()["id"]

    added = client.post(
        f"/api/v1/crews/{second_id}/members",
        json={"user_id": uma.id, "role": "member"},
        headers={"X-CSRF-Token": csrf},
    )
    assert added.status_code == 201, added.text
    assert added.json()["username"] == "uma"
    duplicate = client.post(
        f"/api/v1/crews/{second_id}/members",
        json={"user_id": uma.id},
        headers={"X-CSRF-Token": csrf},
    )
    assert duplicate.status_code == 409
    bad_role = client.post(
        f"/api/v1/crews/{second_id}/members",
        json={"user_id": uma.id, "role": "drummer"},
        headers={"X-CSRF-Token": csrf},
    )
    assert bad_role.status_code == 422

    removed = client.delete(
        f"/api/v1/crews/{second_id}/members/{uma.id}", headers={"X-CSRF-Token": csrf}
    )
    assert removed.status_code == 204
    assert (
        client.delete(
            f"/api/v1/crews/{second_id}/members/{uma.id}",
            headers={"X-CSRF-Token": csrf},
        ).status_code
        == 404
    )
    member_client = TestClient(app)
    login(member_client, "uma", "s3cret-long")
    assert member_client.get(f"/api/v1/crews/{second_id}/members").status_code == 404


def test_bootstrap_cli_creates_admin_and_default_crew(tmp_path, monkeypatch):  # type: ignore[no-untyped-def]
    from sqlalchemy import select

    from app import cli
    from app.core.database import create_engine, create_session_factory
    from app.models import Base, Crew, CrewMembership, User

    db_file = tmp_path / "bootstrap.db"
    monkeypatch.setenv("MUSIC_GATHERINGS_DATABASE_URL", f"sqlite:///{db_file}")
    monkeypatch.setenv("MUSIC_GATHERINGS_BOOTSTRAP_PASSWORD", "first-secret-1")
    engine = create_engine(f"sqlite:///{db_file}")
    Base.metadata.create_all(engine)
    engine.dispose()
    cli.main(["create-admin", "--username", "root"])

    factory = create_session_factory(create_engine(f"sqlite:///{db_file}"))
    with factory() as db:
        admin = db.execute(select(User).where(User.username == "root")).scalar_one()
        assert admin.is_admin and admin.status == "active"
        crew = db.execute(select(Crew).where(Crew.name == "Jam Crew")).scalar_one()
        membership = db.execute(
            select(CrewMembership).where(
                CrewMembership.crew_id == crew.id, CrewMembership.user_id == admin.id
            )
        ).scalar_one()
        assert membership.role == "owner"
