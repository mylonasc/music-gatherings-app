"""Job creation, atomic claiming, completion, retry, and cancellation.

All state transitions use short transactions; the worker never holds a write
transaction across handler execution (proven by test_no_write_txn_during_run).
"""

import time
import traceback
import uuid
from collections.abc import Callable
from dataclasses import dataclass
from datetime import timedelta
from typing import Any

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.jobs.context import (
    FatalJobError,
    JobCancelled,
    JobContext,
    JobTimedOut,
    RetryLater,
)
from app.models import Job
from app.models.base import utcnow_naive
from app.storage.local import LocalObjectStore

Handler = Callable[[JobContext], dict[str, Any]]


@dataclass(frozen=True)
class JobKind:
    name: str
    handler: Handler
    admin_only: bool = False
    max_retries: int | None = None
    timeout_seconds: float = 600.0


_REGISTRY: dict[str, JobKind] = {}


def register_kind(kind: JobKind) -> None:
    _REGISTRY[kind.name] = kind


def get_kind(name: str) -> JobKind | None:
    return _REGISTRY.get(name)


def registered_kinds() -> list[str]:
    return sorted(_REGISTRY)


def _retry_limit(kind: JobKind, settings: Settings) -> int:
    return settings.worker_max_retries if kind.max_retries is None else kind.max_retries


def create_job(
    db: Session,
    *,
    kind: str,
    payload: dict[str, Any] | None = None,
    crew_id: str | None = None,
    created_by_id: str | None = None,
    idempotency_key: str | None = None,
) -> tuple[Job, bool]:
    """Create a queued job. Returns (job, created); duplicates return the original."""
    if idempotency_key:
        existing = db.execute(
            select(Job).where(Job.idempotency_key == idempotency_key)
        ).scalar_one_or_none()
        if existing is not None:
            return existing, False
    job = Job(
        kind=kind,
        status="queued",
        crew_id=crew_id,
        created_by_id=created_by_id,
        idempotency_key=idempotency_key,
        payload=dict(payload or {}),
    )
    db.add(job)
    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        if idempotency_key:
            existing = db.execute(
                select(Job).where(Job.idempotency_key == idempotency_key)
            ).scalar_one_or_none()
            if existing is not None:
                return existing, False
        raise
    return job, True


def claim_next_available(
    db: Session, *, worker_id: str, settings: Settings, now: Any = None
) -> Job | None:
    """Atomically claim one queued (or lease-expired) job.

    Selection and claiming are separate statements, but the UPDATE
    re-validates every precondition, so concurrent workers cannot claim the
    same row: exactly one UPDATE wins (``rowcount == 1``).
    """
    from datetime import datetime

    from sqlalchemy import update

    current: datetime = now or utcnow_naive()
    lease_until = current + timedelta(seconds=settings.worker_lease_seconds)

    candidate = db.execute(
        select(Job)
        .where(
            Job.status == "queued",
            Job.cancel_requested.is_(False),
            (Job.available_at.is_(None)) | (Job.available_at <= current),
        )
        .order_by(Job.created_at)
        .limit(1)
    ).scalar_one_or_none()
    if candidate is None:
        candidate = db.execute(
            select(Job)
            .where(
                Job.status == "running",
                Job.cancel_requested.is_(False),
                Job.lease_expires_at.is_not(None),
                Job.lease_expires_at <= current,
            )
            .order_by(Job.created_at)
            .limit(1)
        ).scalar_one_or_none()
    if candidate is None:
        return None

    kind = get_kind(candidate.kind)
    limit = _retry_limit(kind, settings) if kind else settings.worker_max_retries
    if candidate.status == "running":
        if candidate.attempts >= limit:
            db.execute(
                update(Job)
                .where(Job.id == candidate.id, Job.status == "running")
                .values(
                    status="failed",
                    error=(candidate.error or "") + " | lease expired too many times",
                    finished_at=current,
                    worker_id=None,
                    lease_expires_at=None,
                )
            )
            db.flush()
            return None
        guard = [
            Job.status == "running",
            Job.cancel_requested.is_(False),
            Job.lease_expires_at.is_not(None),
            Job.lease_expires_at <= current,
        ]
    else:
        guard = [
            Job.status == "queued",
            Job.cancel_requested.is_(False),
            (Job.available_at.is_(None)) | (Job.available_at <= current),
        ]
    claimed = db.execute(
        update(Job)
        .where(Job.id == candidate.id, *guard)
        .values(
            status="running",
            worker_id=worker_id,
            claimed_at=current,
            lease_expires_at=lease_until,
            wait_reason=None,
        )
    )
    db.flush()
    # Session.execute returns Result in the type stubs; DML always yields a
    # CursorResult at runtime, which carries rowcount.
    if not claimed.rowcount:  # type: ignore[attr-defined]
        return None
    job = db.get(Job, candidate.id)
    assert job is not None
    return job


def run_claimed_job(
    db: Session,
    store: LocalObjectStore,
    settings: Settings,
    job: Job,
) -> Job:
    """Execute the handler for an already-claimed job (no surrounding write txn)."""
    kind = get_kind(job.kind)
    if kind is None:
        job.status = "failed"
        job.error = f"unknown job kind: {job.kind}"
        job.finished_at = utcnow_naive()
        db.flush()
        return job
    ctx = JobContext(
        job_id=job.id,
        kind=job.kind,
        payload=dict(job.payload or {}),
        db=db,
        store=store,
        settings=settings,
        deadline_monotonic=time.monotonic() + kind.timeout_seconds,
    )
    try:
        result = kind.handler(ctx)
    except FatalJobError as exc:
        db.rollback()
        fresh = db.get(Job, job.id)
        assert fresh is not None
        fresh.status = "failed"
        fresh.error = str(exc)[:2000]
        fresh.finished_at = utcnow_naive()
        fresh.worker_id = None
        fresh.lease_expires_at = None
        db.flush()
        return fresh
    except RetryLater as exc:
        db.rollback()
        fresh = db.get(Job, job.id)
        assert fresh is not None
        retry_limit = _retry_limit(kind, settings)
        fresh.attempts += 1
        if fresh.attempts > retry_limit:
            fresh.status = "failed"
            fresh.error = f"throttled too many times: {exc}"
            fresh.finished_at = utcnow_naive()
        else:
            fresh.status = "queued"
            fresh.wait_reason = (
                f"provider throttled; retrying ({fresh.attempts}/{retry_limit})"
            )
            fresh.available_at = utcnow_naive() + timedelta(seconds=exc.delay_seconds)
        fresh.worker_id = None
        fresh.lease_expires_at = None
        db.flush()
        return fresh
    except (JobCancelled, JobTimedOut, KeyboardInterrupt) as exc:
        db.rollback()
        fresh = db.get(Job, job.id)
        assert fresh is not None
        fresh.status = "cancelled"
        fresh.error = f"{type(exc).__name__}: {exc}"
        fresh.finished_at = utcnow_naive()
        fresh.worker_id = None
        fresh.lease_expires_at = None
        db.flush()
        return fresh
    except Exception as exc:  # noqa: BLE001 - handler failures become job failures
        db.rollback()
        fresh = db.get(Job, job.id)
        assert fresh is not None
        limit = _retry_limit(kind, settings)
        fresh.attempts += 1
        if fresh.attempts > limit:
            fresh.status = "failed"
            fresh.error = f"{type(exc).__name__}: {exc}\n{traceback.format_exc(limit=3)}"[:2000]
            fresh.finished_at = utcnow_naive()
            fresh.worker_id = None
            fresh.lease_expires_at = None
        else:
            backoff = min(2**fresh.attempts, 300)
            fresh.status = "queued"
            fresh.wait_reason = f"retry {fresh.attempts}/{limit} after error: {exc}"[:500]
            fresh.available_at = utcnow_naive() + timedelta(seconds=backoff)
            fresh.worker_id = None
            fresh.lease_expires_at = None
        db.flush()
        return fresh
    job.status = "succeeded"
    job.result = dict(result or {})
    job.progress = 1.0
    job.wait_reason = None
    job.finished_at = utcnow_naive()
    job.worker_id = None
    job.lease_expires_at = None
    db.flush()
    return job


def request_cancel(db: Session, job_id: str) -> Job | None:
    job = db.get(Job, job_id)
    if job is None:
        return None
    if job.status == "queued":
        job.status = "cancelled"
        job.finished_at = utcnow_naive()
        job.wait_reason = None
    elif job.status == "running":
        job.cancel_requested = True
        job.wait_reason = "cancellation requested"
    db.flush()
    return job


def new_worker_id() -> str:
    return f"worker-{uuid.uuid4().hex[:12]}"
