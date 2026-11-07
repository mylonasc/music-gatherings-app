"""Security regressions discovered during the implementation review."""

from urllib.parse import quote

from app.core.config import Settings
from app.jobs.service import create_job
from tests.test_library import setup_two_users, suggest


def test_online_jobs_cannot_bypass_validated_endpoints(tmp_path, monkeypatch):
    _app, admin, csrf, member, mcsrf, crew = setup_two_users(tmp_path, monkeypatch)
    for client, token in ((admin, csrf), (member, mcsrf)):
        for kind in ("online.search", "online.import"):
            response = client.post(
                "/api/v1/jobs",
                json={
                    "kind": kind,
                    "crew_id": crew,
                    "payload": {"crew_id": "another-crew", "created_by_id": "victim"},
                },
                headers={"X-CSRF-Token": token},
            )
            assert response.status_code == 422
    assert admin.get("/api/v1/admin/jobs").json()["total"] == 0


def test_idempotency_keys_are_scoped_to_owner_crew_and_kind(tmp_path, monkeypatch):
    app, admin, _csrf, member, _mcsrf, crew = setup_two_users(tmp_path, monkeypatch)
    owner = admin.get("/api/v1/auth/me").json()["user"]["id"]
    other = member.get("/api/v1/auth/me").json()["user"]["id"]
    with app.state.session_factory() as db:
        def enqueue(user=owner, crew_id=crew, kind="online.import"):
            return create_job(
                db, kind=kind, created_by_id=user, crew_id=crew_id,
                idempotency_key="predictable-key",
            )

        first, created = enqueue()
        assert created
        duplicate, created = enqueue()
        assert not created and duplicate.id == first.id
        for kwargs in ({"user": other}, {"crew_id": None}, {"kind": "online.search"}):
            different, created = enqueue(**kwargs)
            assert created and different.id != first.id


def test_production_always_uses_secure_session_cookies():
    assert Settings(app_env="production", session_cookie_secure=False).session_cookie_secure
    assert not Settings(app_env="development", session_cookie_secure=False).session_cookie_secure


def test_upload_limit_and_unicode_download_filename(tmp_path, monkeypatch):
    _app, admin, csrf, _member, _mcsrf, crew = setup_two_users(
        tmp_path, monkeypatch, MUSIC_GATHERINGS_MAX_OBJECT_BYTES="8"
    )
    track = suggest(admin, crew, csrf, {"title": "Upload", "versions": [{"label": "Live"}]})
    version = admin.get(f"/api/v1/tracks/{track['track_id']}").json()["versions"][0]
    path = f"/api/v1/tracks/{track['track_id']}/versions/{version['id']}/artifacts/upload"
    headers = {"X-CSRF-Token": csrf}
    rejected = admin.post(
        path, files={"file": ("large.txt", b"123456789", "text/plain")},
        data={"kind": "lyrics"}, headers=headers,
    )
    assert rejected.status_code == 413
    uploaded = admin.post(
        path, files={"file": ('τραγούδι".txt', b"12345678", "text/plain")},
        data={"kind": "lyrics"}, headers=headers,
    )
    assert uploaded.status_code == 201, uploaded.text
    content = admin.get(f"/api/v1/artifacts/{uploaded.json()['id']}/content")
    assert content.status_code == 200
    assert content.content == b"12345678"
    assert content.headers["content-disposition"].startswith("attachment; filename*=UTF-8''")
    expected = quote(uploaded.json()["file_name"], safe="")
    assert content.headers["content-disposition"] == f"attachment; filename*=UTF-8''{expected}"
    assert '"' not in content.headers["content-disposition"]
    assert content.headers["x-content-type-options"] == "nosniff"
