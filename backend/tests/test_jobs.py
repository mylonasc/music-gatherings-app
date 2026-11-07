"""S06 durable-job tests: queue, claims, retries, recovery, auth, worker CLI."""

import json
import shutil
import subprocess
import sys
import threading
import time
from datetime import timedelta
from pathlib import Path

import pytest

from app.jobs import service
from app.jobs.context import JobContext
from app.jobs.service import (
    JobKind,
    claim_next_available,
    create_job,
    get_kind,
    register_kind,
    request_cancel,
    run_claimed_job,
)
from app.models import Job
from app.models.base import utcnow_naive
from tests.conftest import make_test_app
from tests.test_auth import login, seed_admin
from tests.test_library import setup_two_users


@pytest.fixture(autouse=True)
def clean_registry():  # type: ignore[no-untyped-def]
    snapshot = dict(service._REGISTRY)
    yield
    service._REGISTRY.clear()
    service._REGISTRY.update(snapshot)
    # Builtins must always be present: create_app() re-registers them on every
    # app build, so restore that invariant after wiping test-only kinds.
    from app.jobs.handlers import register_builtin_kinds

    register_builtin_kinds()


def echo_handler(ctx: JobContext):  # type: ignore[no-untyped-def]
    ctx.check_cancelled()
    ctx.set_progress(0.5)
    return {"echo": ctx.payload.get("message", "")}


def register_echo(max_retries: int | None = None) -> None:
    register_kind(JobKind(name="test.echo", handler=echo_handler, max_retries=max_retries))


def test_create_claim_run_end_to_end(tmp_path, monkeypatch):  # type: ignore[no-untyped-def]
    app, client = make_test_app(tmp_path, monkeypatch)
    register_echo()
    admin_id, _crew = seed_admin(app)
    csrf = login(client, "admin", "admin-pass-1")
    created = client.post(
        "/api/v1/jobs",
        json={"kind": "test.echo", "payload": {"message": "hi"}},
        headers={"X-CSRF-Token": csrf},
    )
    assert created.status_code == 201, created.text
    job_id = created.json()["id"]
    assert created.json()["status"] == "queued"

    factory = app.state.session_factory
    with factory() as db:
        claimed = claim_next_available(db, worker_id="w1", settings=app.state.settings)
        assert claimed is not None and claimed.id == job_id
        assert claimed.status == "running"
        db.commit()
    with factory() as db:
        claimed = db.get(Job, job_id)
        assert claimed is not None
        finished = run_claimed_job(db, app.state.object_store, app.state.settings, claimed)
        assert finished.status == "succeeded"
        assert finished.result == {"echo": "hi"}
        db.commit()

    fetched = client.get(f"/api/v1/jobs/{job_id}")
    assert fetched.json()["status"] == "succeeded"
    assert fetched.json()["progress"] == 1.0


def test_idempotent_create_returns_original(tmp_path, monkeypatch):  # type: ignore[no-untyped-def]
    _app, client = make_test_app(tmp_path, monkeypatch)
    register_echo()
    from tests.test_auth import seed_admin as _seed

    _seed(_app)
    csrf = login(client, "admin", "admin-pass-1")
    first = client.post(
        "/api/v1/jobs",
        json={"kind": "test.echo", "idempotency_key": "k1"},
        headers={"X-CSRF-Token": csrf},
    )
    second = client.post(
        "/api/v1/jobs",
        json={"kind": "test.echo", "payload": {"other": True}, "idempotency_key": "k1"},
        headers={"X-CSRF-Token": csrf},
    )
    assert first.json()["id"] == second.json()["id"]


def test_retry_then_fail(tmp_path, monkeypatch):  # type: ignore[no-untyped-def]
    app, _client = make_test_app(tmp_path, monkeypatch)

    def always_fail(ctx: JobContext):  # type: ignore[no-untyped-def]
        raise RuntimeError("boom")

    register_kind(JobKind(name="test.fail", handler=always_fail, max_retries=1))
    factory = app.state.session_factory
    with factory() as db:
        job, _ = create_job(db, kind="test.fail")
        job_id = job.id
        db.commit()
    with factory() as db:
        claimed = claim_next_available(db, worker_id="w1", settings=app.state.settings)
        assert claimed is not None
        finished = run_claimed_job(db, app.state.object_store, app.state.settings, claimed)
        assert finished.status == "queued"
        assert finished.attempts == 1
        assert "retry 1/1" in (finished.wait_reason or "")
        assert finished.available_at is not None and finished.available_at > utcnow_naive()
        # Fast-forward past the backoff.
        finished.available_at = utcnow_naive() - timedelta(seconds=1)
        db.commit()
    with factory() as db:
        claimed = claim_next_available(db, worker_id="w1", settings=app.state.settings)
        assert claimed is not None and claimed.id == job_id
        finished = run_claimed_job(db, app.state.object_store, app.state.settings, claimed)
        assert finished.status == "failed"
        assert finished.attempts == 2
        assert "boom" in (finished.error or "")
        db.commit()


def test_cancel_queued_job(tmp_path, monkeypatch):  # type: ignore[no-untyped-def]
    app, client = make_test_app(tmp_path, monkeypatch)
    register_echo()
    from tests.test_auth import seed_admin as _seed

    _seed(app)
    csrf = login(client, "admin", "admin-pass-1")
    created = client.post(
        "/api/v1/jobs", json={"kind": "test.echo"}, headers={"X-CSRF-Token": csrf}
    )
    job_id = created.json()["id"]
    cancelled = client.post(
        f"/api/v1/jobs/{job_id}/cancel", headers={"X-CSRF-Token": csrf}
    )
    assert cancelled.json()["status"] == "cancelled"
    factory = app.state.session_factory
    with factory() as db:
        assert claim_next_available(db, worker_id="w1", settings=app.state.settings) is None


def test_cancel_running_job(tmp_path, monkeypatch):  # type: ignore[no-untyped-def]
    app, _client = make_test_app(tmp_path, monkeypatch)
    register_echo()
    factory = app.state.session_factory
    with factory() as db:
        job, _ = create_job(db, kind="test.echo")
        job_id = job.id
        db.commit()
    with factory() as db:
        claimed = claim_next_available(db, worker_id="w1", settings=app.state.settings)
        assert claimed is not None
        db.commit()
    with factory() as db:
        assert request_cancel(db, job_id) is not None
        db.commit()
    with factory() as db:
        claimed = db.get(Job, job_id)
        assert claimed is not None
        finished = run_claimed_job(db, app.state.object_store, app.state.settings, claimed)
        assert finished.status == "cancelled"
        db.commit()


def test_stale_lease_recovery(tmp_path, monkeypatch):  # type: ignore[no-untyped-def]
    app, _client = make_test_app(tmp_path, monkeypatch)
    register_echo()
    factory = app.state.session_factory
    with factory() as db:
        job, _ = create_job(db, kind="test.echo")
        job_id = job.id
        db.commit()
    with factory() as db:
        claimed = claim_next_available(db, worker_id="crashed", settings=app.state.settings)
        assert claimed is not None
        # Simulate a crashed worker: lease in the past, row stays 'running'.
        claimed.lease_expires_at = utcnow_naive() - timedelta(seconds=1)
        db.commit()
    with factory() as db:
        reclaimed = claim_next_available(db, worker_id="w2", settings=app.state.settings)
        assert reclaimed is not None and reclaimed.id == job_id
        assert reclaimed.attempts == 0
        finished = run_claimed_job(db, app.state.object_store, app.state.settings, reclaimed)
        assert finished.status == "succeeded"
        db.commit()


def test_exhausted_stale_job_fails_instead_of_looping(tmp_path, monkeypatch):  # type: ignore[no-untyped-def]
    app, _client = make_test_app(tmp_path, monkeypatch)
    register_echo(max_retries=0)
    factory = app.state.session_factory
    with factory() as db:
        job, _ = create_job(db, kind="test.echo")
        job_id = job.id
        db.commit()
    with factory() as db:
        claimed = claim_next_available(db, worker_id="crashed", settings=app.state.settings)
        assert claimed is not None
        claimed.attempts = 5
        claimed.lease_expires_at = utcnow_naive() - timedelta(seconds=1)
        db.commit()
    with factory() as db:
        assert claim_next_available(db, worker_id="w2", settings=app.state.settings) is None
        failed = db.get(Job, job_id)
        assert failed is not None and failed.status == "failed"


def test_no_write_transaction_spans_handler(tmp_path, monkeypatch):  # type: ignore[no-untyped-def]
    app, _client = make_test_app(tmp_path, monkeypatch)
    release = threading.Event()

    def blocking(ctx: JobContext):  # type: ignore[no-untyped-def]
        ctx.set_progress(0.1)
        assert release.wait(timeout=30)
        return {"done": True}

    register_kind(JobKind(name="test.blocking", handler=blocking))
    factory = app.state.session_factory
    with factory() as db:
        job, _ = create_job(db, kind="test.blocking")
        job_id = job.id
        db.commit()
    with factory() as db:
        claimed = claim_next_available(db, worker_id="w1", settings=app.state.settings)
        assert claimed is not None
        db.commit()
    errors: list[str] = []

    def run_in_thread() -> None:
        try:
            with factory() as db:
                row = db.get(Job, job_id)
                assert row is not None
                run_claimed_job(db, app.state.object_store, app.state.settings, row)
                db.commit()
        except Exception as exc:  # noqa: BLE001
            errors.append(str(exc))
        finally:
            release.set()

    thread = threading.Thread(target=run_in_thread)
    thread.start()
    try:
        # While the handler sleeps, an unrelated write must proceed immediately.
        started = time.monotonic()
        with factory() as db:
            _other, created = create_job(db, kind="test.blocking")
            assert created
            db.commit()
        elapsed = time.monotonic() - started
        assert elapsed < 5.0, f"writer blocked for {elapsed:.1f}s by running handler"
    finally:
        release.set()
        thread.join(timeout=30)
    assert not errors
    with factory() as db:
        assert db.get(Job, job_id) is not None
        assert db.get(Job, job_id).status == "succeeded"


def test_job_authorization(tmp_path, monkeypatch):  # type: ignore[no-untyped-def]
    app, admin_client, csrf, member_client, mcsrf, crew_id = setup_two_users(
        tmp_path, monkeypatch
    )
    register_echo()
    # Member creates a crew-scoped job.
    created = member_client.post(
        "/api/v1/jobs",
        json={"kind": "test.echo", "crew_id": crew_id},
        headers={"X-CSRF-Token": mcsrf},
    )
    assert created.status_code == 201, created.text
    job_id = created.json()["id"]
    # Non-admin cannot create crew-less jobs or admin-only kinds.
    assert (
        member_client.post(
            "/api/v1/jobs", json={"kind": "test.echo"}, headers={"X-CSRF-Token": mcsrf}
        ).status_code
        == 403
    )
    unknown = member_client.post(
        "/api/v1/jobs",
        json={"kind": "nope.nope", "crew_id": crew_id},
        headers={"X-CSRF-Token": mcsrf},
    )
    assert unknown.status_code == 422
    # Member sees their crew's job; admin sees it too.
    assert member_client.get(f"/api/v1/jobs/{job_id}").status_code == 200
    assert admin_client.get(f"/api/v1/jobs/{job_id}").status_code == 200
    # A second crew's member cannot see it.
    other_crew = admin_client.post(
        "/api/v1/crews", json={"name": "Other"}, headers={"X-CSRF-Token": csrf}
    ).json()["id"]
    stranger = member_client.post(
        "/api/v1/access-requests", json={"username": "stray", "password": "s3cret-long"}
    )
    admin_client.post(
        f"/api/v1/access-requests/{stranger.json()['id']}/approve",
        headers={"X-CSRF-Token": csrf},
    )
    from fastapi.testclient import TestClient

    stray = TestClient(app)
    stray_csrf = login(stray, "stray", "s3cret-long")
    # A user who belongs only to the other crew cannot see it.
    stray_me = stray.get("/api/v1/auth/me").json()
    removed = admin_client.delete(
        f"/api/v1/crews/{crew_id}/members/{stray_me['id']}",
        headers={"X-CSRF-Token": csrf},
    )
    assert removed.status_code == 204
    assert stray.get(f"/api/v1/jobs/{job_id}").status_code == 404
    listed = stray.get("/api/v1/jobs")
    assert listed.json()["total"] == 0
    # Admin-only kind requires admin even with a crew.
    from app.jobs.service import JobKind as _K

    register_kind(_K(name="test.admin", handler=echo_handler, admin_only=True))
    denied = member_client.post(
        "/api/v1/jobs",
        json={"kind": "test.admin", "crew_id": crew_id},
        headers={"X-CSRF-Token": mcsrf},
    )
    assert denied.status_code == 403
    allowed = admin_client.post(
        "/api/v1/jobs",
        json={"kind": "test.admin", "crew_id": crew_id},
        headers={"X-CSRF-Token": csrf},
    )
    assert allowed.status_code == 201
    assert stray_csrf and other_crew


def test_worker_once_processes_reindex(tmp_path, monkeypatch):  # type: ignore[no-untyped-def]
    import os

    backend_dir = Path(__file__).resolve().parent.parent
    env = dict(os.environ)
    env["MUSIC_GATHERINGS_DATABASE_URL"] = f"sqlite:///{tmp_path / 'app.db'}"
    env["MUSIC_GATHERINGS_DATA_DIR"] = str(tmp_path / "data")
    app, client = make_test_app(tmp_path, monkeypatch)
    from tests.test_auth import seed_admin as _seed

    _seed(app)
    csrf = login(client, "admin", "admin-pass-1")
    created = client.post(
        "/api/v1/jobs", json={"kind": "maintenance.reindex"}, headers={"X-CSRF-Token": csrf}
    )
    assert created.status_code == 201
    job_id = created.json()["id"]

    completed = subprocess.run(
        [sys.executable, "-m", "app.worker", "--once"],
        cwd=backend_dir,
        env=env,
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert completed.returncode == 0, completed.stderr
    fetched = client.get(f"/api/v1/jobs/{job_id}")
    assert fetched.json()["status"] == "succeeded"
    assert fetched.json()["result"] == {"reindexed": 0}

    idle = subprocess.run(
        [sys.executable, "-m", "app.worker", "--once"],
        cwd=backend_dir,
        env=env,
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert idle.returncode == 0


def test_compose_worker_has_no_public_ports():  # type: ignore[no-untyped-def]

    if shutil.which("docker") is None:
        pytest.skip("docker unavailable")
    repo_root = Path(__file__).resolve().parent.parent.parent
    try:
        rendered = subprocess.run(
            ["docker", "compose", "config", "--format", "json"],
            cwd=repo_root,
            capture_output=True,
            text=True,
            timeout=120,
        )
    except (OSError, subprocess.SubprocessError):
        pytest.skip("docker compose unavailable")
    if rendered.returncode != 0:
        pytest.skip("docker compose config failed")
    config = json.loads(rendered.stdout)
    worker = config["services"]["worker"]
    assert worker.get("ports", []) in ([], None)
    volumes = worker.get("volumes", [])
    assert any("app-data" in str(v) for v in volumes)
    assert "backend" in worker.get("depends_on", {}) or "backend" in worker.get("depends_on", [])
    command = " ".join(str(c) for c in worker.get("command", []))
    assert "app.worker" in command
    assert get_kind("maintenance.reindex") is not None
