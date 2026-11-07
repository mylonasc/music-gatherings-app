"""Job queue API: create, inspect, list, and cancel durable jobs."""

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db, verify_csrf
from app.api.v1.visibility import crew_or_404, user_crew_ids
from app.jobs.service import create_job, get_kind, request_cancel
from app.models import Job, User

router = APIRouter()


class JobCreate(BaseModel):
    kind: str = Field(max_length=64)
    payload: dict[str, Any] = Field(default_factory=dict)
    crew_id: str | None = None
    idempotency_key: str | None = Field(default=None, max_length=128)


class JobOut(BaseModel):
    id: str
    kind: str
    status: str
    crew_id: str | None
    created_by_id: str | None
    progress: float
    wait_reason: str | None
    attempts: int
    result: dict[str, Any] | None
    error: str | None


class JobList(BaseModel):
    items: list[JobOut]
    total: int
    limit: int
    offset: int


def _job_out(job: Job) -> JobOut:
    return JobOut(
        id=job.id,
        kind=job.kind,
        status=job.status,
        crew_id=job.crew_id,
        created_by_id=job.created_by_id,
        progress=job.progress,
        wait_reason=job.wait_reason,
        attempts=job.attempts,
        result=job.result,
        error=job.error,
    )


def _visible_job(db: Session, user: User, job_id: str) -> Job:
    job = db.get(Job, job_id)
    if job is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="not found")
    if job.crew_id is None:
        if not user.is_admin:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="not found")
        return job
    crew_ids = user_crew_ids(db, user)
    if job.crew_id not in crew_ids:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="not found")
    return job


@router.post("/jobs", response_model=JobOut, status_code=status.HTTP_201_CREATED)
def create_job_endpoint(
    body: JobCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    _csrf: None = Depends(verify_csrf),
) -> JobOut:
    kind = get_kind(body.kind)
    if kind is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="unknown job kind"
        )
    if kind.admin_only and not user.is_admin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="admin required")
    crew_id = body.crew_id
    if crew_id is not None:
        crew_or_404(db, user, crew_id)
    elif not user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="crew_id required for non-admin jobs",
        )
    job, _created = create_job(
        db,
        kind=body.kind,
        payload=body.payload,
        crew_id=crew_id,
        created_by_id=user.id,
        idempotency_key=body.idempotency_key,
    )
    return _job_out(job)


@router.get("/jobs/{job_id}", response_model=JobOut)
def get_job(
    job_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> JobOut:
    return _job_out(_visible_job(db, user, job_id))


@router.get("/jobs", response_model=JobList)
def list_jobs(
    crew_id: str | None = Query(default=None),
    job_status: str | None = Query(default=None, alias="status"),
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> JobList:
    stmt = select(Job).order_by(Job.created_at.desc())
    if crew_id is not None:
        crew_or_404(db, user, crew_id)
        stmt = stmt.where(Job.crew_id == crew_id)
    elif not user.is_admin:
        crew_ids = user_crew_ids(db, user)
        if not crew_ids:
            return JobList(items=[], total=0, limit=limit, offset=offset)
        stmt = stmt.where(Job.crew_id.in_(crew_ids))
    if job_status is not None:
        stmt = stmt.where(Job.status == job_status)
    rows = db.execute(stmt).scalars().all()
    # Crew-less (maintenance) jobs are visible to admins only.
    items = [
        _job_out(job)
        for job in rows
        if job.crew_id is not None or user.is_admin
    ]
    total = len(items)
    return JobList(items=items[offset : offset + limit], total=total, limit=limit, offset=offset)


@router.post("/jobs/{job_id}/cancel", response_model=JobOut)
def cancel_job(
    job_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    _csrf: None = Depends(verify_csrf),
) -> JobOut:
    job = _visible_job(db, user, job_id)
    if job.status not in ("queued", "running"):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="job already finished"
        )
    updated = request_cancel(db, job.id)
    assert updated is not None
    return _job_out(updated)
