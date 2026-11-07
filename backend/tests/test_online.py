"""S10 tests: search jobs don't mutate, imports attach/dedupe, contexts select."""

from contextlib import contextmanager

import httpx
from sqlalchemy import select

from app.jobs import online as online_module
from app.jobs.service import claim_next_available, get_kind, run_claimed_job
from app.models import Artifact, ArtifactDerivation, Job, SourceRecord, Track
from tests.conftest import make_test_app
from tests.test_auth import login, seed_admin

FAKE_SEARCH = {
    "items": [
        {
            "provider": "fake",
            "external_id": "fake-song-1",
            "title": "Blue Test Train",
            "artist": "The Determinists",
            "artifact_types": ["lyrics", "chord_chart"],
            "source_url": "https://example.local/fake-song-1",
            "attribution": "Fake",
        }
    ],
    "provider": "fake",
}

FAKE_FETCH = {
    "provider": "fake",
    "external_id": "fake-song-1",
    "title": "Blue Test Train",
    "artist": "The Determinists",
    "source_url": "https://example.local/fake-song-1",
    "artifacts": [
        {
            "artifact_type": "lyrics",
            "mime_type": "text/plain",
            "content_text": "Rolling down the test track line\n",
            "attribution": "Fake",
            "storage_allowed": True,
        },
        {
            "artifact_type": "chord_chart",
            "mime_type": "text/plain",
            "content_text": "[C] Rolling [G] down the line\n",
            "attribution": "Fake",
            "storage_allowed": True,
        },
    ],
    "warnings": [],
}

GENIUS_FETCH = {
    "provider": "genius",
    "external_id": "111",
    "title": "Blue Test",
    "artist": "Tester",
    "source_url": "https://genius.com/Tester-blue-test-lyrics",
    "artifacts": [],
    "warnings": ["reference-only"],
}

PROCESSOR_OK = {
    "canonical": {"schema_version": 1, "sections": []},
    "outputs": {
        "canonical_json": '{"schema_version": 1, "sections": []}',
        "lyrics_html": "<div class=\"song\"><p>hi</p></div>",
    },
    "warnings": [],
    "processor_version": "0.1.0",
}

PROFILE = {
    "schema_version": 1,
    "steps": [{"type": "transpose", "config": {"semitones": 2}}],
    "outputs": ["canonical_json", "lyrics_html"],
}


def install_transports(monkeypatch, fetch_payload=None, processor_payload=None, search_payload=None, providers=("fake",)):  # type: ignore[no-untyped-def]
    seen = {"search": 0, "fetch": 0, "process": 0}

    def provider_handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/v1/search":
            seen["search"] += 1
            return httpx.Response(200, json=search_payload or FAKE_SEARCH)
        if request.url.path == "/v1/fetch":
            seen["fetch"] += 1
            return httpx.Response(200, json=fetch_payload or FAKE_FETCH)
        return httpx.Response(404, json={})

    def processor_handler(request: httpx.Request) -> httpx.Response:
        seen["process"] += 1
        return httpx.Response(200, json=processor_payload or PROCESSOR_OK)

    for provider in providers:
        monkeypatch.setitem(
            online_module.PROVIDER_TRANSPORTS, provider, httpx.MockTransport(provider_handler)
        )
    monkeypatch.setattr(online_module, "PROCESSOR_TRANSPORT", httpx.MockTransport(processor_handler))
    return seen


def make_env(tmp_path, monkeypatch, **extra):  # type: ignore[no-untyped-def]
    app, client = make_test_app(tmp_path, monkeypatch, **extra)
    assert get_kind("online.search") is not None
    assert get_kind("online.import") is not None
    _admin_id, crew_id = seed_admin(app)
    csrf = login(client, "admin", "admin-pass-1")
    return app, client, csrf, crew_id


def run_job(app, job_id):  # type: ignore[no-untyped-def]
    factory = app.state.session_factory
    with factory() as db:
        claimed = claim_next_available(db, worker_id="w1", settings=app.state.settings)
        assert claimed is not None and claimed.id == job_id
        db.commit()
    with factory() as db:
        claimed = db.get(Job, job_id)
        finished = run_claimed_job(db, app.state.object_store, app.state.settings, claimed)
        result = dict(finished.result or {})
        status = finished.status
        db.commit()
    return status, result


@contextmanager
def factory_session(app):  # type: ignore[no-untyped-def]
    session = app.state.session_factory()
    try:
        yield session
    finally:
        session.close()


def test_search_does_not_mutate_library(tmp_path, monkeypatch):  # type: ignore[no-untyped-def]
    app, client, csrf, crew_id = make_env(tmp_path, monkeypatch)
    install_transports(monkeypatch)
    with factory_session(app) as db:
        assert db.execute(select(Track)).scalars().all() == []
    started = client.post(
        "/api/v1/search/online",
        json={"query": "blue", "providers": ["fake"], "crew_id": crew_id},
        headers={"X-CSRF-Token": csrf},
    )
    assert started.status_code == 202, started.text
    job_id = started.json()["id"]
    status, result = run_job(app, job_id)
    assert status == "succeeded"
    assert result["results"]["fake"][0]["external_id"] == "fake-song-1"
    with factory_session(app) as db:
        assert db.execute(select(Track)).scalars().all() == []
    fetched = client.get(f"/api/v1/jobs/{job_id}")
    assert fetched.json()["status"] == "succeeded"


def test_import_stores_artifacts_and_indexes_lyrics(tmp_path, monkeypatch):  # type: ignore[no-untyped-def]
    app, client, csrf, crew_id = make_env(tmp_path, monkeypatch)
    install_transports(monkeypatch)
    started = client.post(
        "/api/v1/imports",
        json={"provider": "fake", "external_id": "fake-song-1", "crew_id": crew_id},
        headers={"X-CSRF-Token": csrf},
    )
    assert started.status_code == 202, started.text
    status, result = run_job(app, started.json()["id"])
    assert status == "succeeded", result
    assert result["reused"] is False
    assert len(result["artifact_ids"]) == 2
    with factory_session(app) as db:
        track = db.get(Track, result["track_id"])
        assert track is not None and track.title == "Blue Test Train"
        assert db.execute(select(SourceRecord)).scalars().all()[0].provider == "fake"
    content = client.get(f"/api/v1/artifacts/{result['artifact_ids'][0]}/content")
    assert content.status_code == 200
    assert b"Rolling down" in content.content
    # Lyrics are now locally searchable.
    found = client.get("/api/v1/search/local", params={"q": "rolling down"})
    assert found.json()["total"] == 1


def test_import_is_idempotent(tmp_path, monkeypatch):  # type: ignore[no-untyped-def]
    app, client, csrf, crew_id = make_env(tmp_path, monkeypatch)
    install_transports(monkeypatch)
    body = {"provider": "fake", "external_id": "fake-song-1", "crew_id": crew_id}
    first = client.post("/api/v1/imports", json=body, headers={"X-CSRF-Token": csrf})
    status, result = run_job(app, first.json()["id"])
    assert status == "succeeded"
    with factory_session(app) as db:
        count_before = len(db.execute(select(Artifact)).scalars().all())
    second = client.post("/api/v1/imports", json=body, headers={"X-CSRF-Token": csrf})
    status, result2 = run_job(app, second.json()["id"])
    assert status == "succeeded"
    assert result2["reused"] is True
    assert result2["artifact_ids"] == result["artifact_ids"]
    with factory_session(app) as db:
        assert len(db.execute(select(Artifact)).scalars().all()) == count_before


def test_genius_import_is_reference_only(tmp_path, monkeypatch):  # type: ignore[no-untyped-def]
    app, client, csrf, crew_id = make_env(tmp_path, monkeypatch)
    install_transports(monkeypatch, fetch_payload=GENIUS_FETCH, providers=("genius",))
    started = client.post(
        "/api/v1/imports",
        json={"provider": "genius", "external_id": "111", "crew_id": crew_id},
        headers={"X-CSRF-Token": csrf},
    )
    assert started.status_code == 202
    status, result = run_job(app, started.json()["id"])
    assert status == "succeeded"
    assert any("reference" in w for w in result["warnings"])
    with factory_session(app) as db:
        artifacts = db.execute(select(Artifact)).scalars().all()
        assert len(artifacts) == 1
        assert artifacts[0].is_external is True
        assert artifacts[0].object_key is None
    assert (
        client.get(f"/api/v1/artifacts/{result['artifact_ids'][0]}/content").status_code
        == 404
    )


def test_import_with_profile_derives_and_caches(tmp_path, monkeypatch):  # type: ignore[no-untyped-def]
    app, client, csrf, crew_id = make_env(tmp_path, monkeypatch)
    seen = install_transports(monkeypatch)
    body = {
        "provider": "fake",
        "external_id": "fake-song-1",
        "crew_id": crew_id,
        "profile": PROFILE,
    }
    first = client.post("/api/v1/imports", json=body, headers={"X-CSRF-Token": csrf})
    status, result = run_job(app, first.json()["id"])
    assert status == "succeeded"
    assert seen["process"] == 1
    with factory_session(app) as db:
        derivations = db.execute(select(ArtifactDerivation)).scalars().all()
        assert len(derivations) == 2  # canonical_json + lyrics_html
        assert all(d.processor_version == "0.1.0" for d in derivations)
        kinds = {a.kind for a in db.execute(select(Artifact)).scalars().all()}
        assert "canonical_document" in kinds
    # Second import of the same content reuses the derivation (no new process call).
    second = client.post("/api/v1/imports", json=body, headers={"X-CSRF-Token": csrf})
    status, result2 = run_job(app, second.json()["id"])
    assert status == "succeeded"
    assert result2["reused"] is True
    assert seen["process"] == 1


def test_representations_select_by_context(tmp_path, monkeypatch):  # type: ignore[no-untyped-def]
    app, client, csrf, crew_id = make_env(tmp_path, monkeypatch)
    install_transports(monkeypatch)
    started = client.post(
        "/api/v1/imports",
        json={
            "provider": "fake",
            "external_id": "fake-song-1",
            "crew_id": crew_id,
            "profile": PROFILE,
        },
        headers={"X-CSRF-Token": csrf},
    )
    _status, result = run_job(app, started.json()["id"])
    audience = client.get(
        f"/api/v1/tracks/{result['track_id']}/representations",
        params={"context": "audience"},
    ).json()
    assert {i["artifact"]["kind"] for i in audience["items"]} >= {"lyrics", "rendered_lyrics"}
    raw = [i for i in audience["items"] if not i["derived"]]
    assert raw and all(i["source_provider"] == "fake" for i in raw)
    assert any(i["derived"] for i in audience["items"])
    guitar = client.get(
        f"/api/v1/tracks/{result['track_id']}/representations",
        params={"context": "guitar"},
    ).json()
    assert {i["artifact"]["kind"] for i in guitar["items"]} >= {"chord_chart"}
    piano = client.get(
        f"/api/v1/tracks/{result['track_id']}/representations",
        params={"context": "piano"},
    ).json()
    assert {i["artifact"]["kind"] for i in piano["items"]} >= {"chord_chart"}


def test_per_user_quota_blocks_with_429(tmp_path, monkeypatch):  # type: ignore[no-untyped-def]
    app, client, csrf, crew_id = make_env(
        tmp_path,
        monkeypatch,
        MUSIC_GATHERINGS_ONLINE_SEARCH_PER_USER_PER_HOUR="1",
    )
    install_transports(monkeypatch)
    first = client.post(
        "/api/v1/search/online",
        json={"query": "blue", "providers": ["fake"], "crew_id": crew_id},
        headers={"X-CSRF-Token": csrf},
    )
    assert first.status_code == 202
    second = client.post(
        "/api/v1/search/online",
        json={"query": "blue", "providers": ["fake"], "crew_id": crew_id},
        headers={"X-CSRF-Token": csrf},
    )
    assert second.status_code == 429
    unknown = client.post(
        "/api/v1/search/online",
        json={"query": "blue", "providers": ["nope"], "crew_id": crew_id},
        headers={"X-CSRF-Token": csrf},
    )
    assert unknown.status_code in (422, 429)


def test_throttled_search_requeues_with_cooldown(tmp_path, monkeypatch):  # type: ignore[no-untyped-def]
    from datetime import timedelta

    from app.models import Job
    from app.models.base import utcnow_naive

    app, client, csrf, crew_id = make_env(tmp_path, monkeypatch)

    calls = {"n": 0}

    def flaky(request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        if calls["n"] == 1:
            return httpx.Response(429, headers={"retry-after": "5"}, json={})
        return httpx.Response(200, json=FAKE_SEARCH)

    monkeypatch.setitem(
        online_module.PROVIDER_TRANSPORTS, "fake", httpx.MockTransport(flaky)
    )
    started = client.post(
        "/api/v1/search/online",
        json={"query": "blue", "providers": ["fake"], "crew_id": crew_id},
        headers={"X-CSRF-Token": csrf},
    )
    job_id = started.json()["id"]
    factory = app.state.session_factory
    with factory() as db:
        claimed = claim_next_available(db, worker_id="w1", settings=app.state.settings)
        assert claimed is not None
        finished = run_claimed_job(db, app.state.object_store, app.state.settings, claimed)
        assert finished.status == "queued"
        assert "throttled" in (finished.wait_reason or "")
        assert finished.attempts == 1
        finished.available_at = utcnow_naive() - timedelta(seconds=1)
        db.commit()
    with factory() as db:
        claimed = claim_next_available(db, worker_id="w1", settings=app.state.settings)
        assert claimed is not None and claimed.id == job_id
        finished = run_claimed_job(db, app.state.object_store, app.state.settings, claimed)
        assert finished.status == "succeeded"
        db.commit()
    assert calls["n"] == 2


def test_cross_crew_import_denied(tmp_path, monkeypatch):  # type: ignore[no-untyped-def]
    from fastapi.testclient import TestClient

    from tests.test_auth import login as _login

    app, client, csrf, crew_id = make_env(tmp_path, monkeypatch)
    other_crew = client.post(
        "/api/v1/crews", json={"name": "Other"}, headers={"X-CSRF-Token": csrf}
    ).json()["id"]
    outsider = TestClient(app)
    outsider.post(
        "/api/v1/access-requests", json={"username": "ext", "password": "s3cret-long"}
    )
    pending = client.get("/api/v1/access-requests").json()
    req = [r for r in pending if r["username"] == "ext"][0]
    client.post(
        f"/api/v1/access-requests/{req['id']}/approve", headers={"X-CSRF-Token": csrf}
    )
    ext_csrf = _login(outsider, "ext", "s3cret-long")
    denied = outsider.post(
        "/api/v1/imports",
        json={"provider": "fake", "external_id": "fake-song-1", "crew_id": other_crew},
        headers={"X-CSRF-Token": ext_csrf},
    )
    assert denied.status_code == 404
