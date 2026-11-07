"""Administration: provider status, isolated provider/processor tests,
processing-profile management, job oversight, and the audit trail.

Everything here requires admin. Test endpoints never mutate the library:
they return upstream results or validation diagnostics without storing
anything. Provider calls honor the same quotas and inbound limits as
production traffic.
"""

from typing import Any

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_db, get_settings, require_admin, verify_csrf
from app.api.v1.jobs import JobList, _job_out
from app.core.config import Settings
from app.jobs import online as online_module
from app.jobs.online import (
    _error_code_and_detail,
    parse_retry_after_seconds,
    provider_client,
)
from app.models import AuditEvent, Job, ProcessingProfile, User

router = APIRouter()

ADMIN_PROVIDERS = ("fake", "lrclib", "ultimate_guitar")


class ProviderStatus(BaseModel):
    provider: str
    reachable: bool
    configured: bool | None = None
    supports_search: bool = False
    supports_fetch: bool = False
    allows_storage: bool = False
    limiter: dict[str, Any] = Field(default_factory=dict)
    upstream_requests: int | None = None
    error: str | None = None


class ProviderTestSearch(BaseModel):
    provider: str
    query: str = Field(min_length=1, max_length=200)


class ProviderTestFetch(BaseModel):
    provider: str
    external_id: str = Field(min_length=1, max_length=512)


class ProfileCreate(BaseModel):
    name: str = Field(min_length=1, max_length=128)
    steps: list[dict[str, Any]] = Field(default_factory=list, max_length=16)
    outputs: list[str] = Field(default_factory=list, max_length=8)


class ProfileOut(BaseModel):
    id: str
    name: str
    version: int
    config: dict[str, Any]
    is_active: bool


class ProcessPreviewRequest(BaseModel):
    source_text: str = Field(min_length=1, max_length=200_000)
    profile: dict[str, Any]


def _audit(
    db: Session, admin: User, action: str, entity: str | None = None, entity_id: str | None = None
) -> None:
    db.add(
        AuditEvent(
            actor_user_id=admin.id, action=action, entity_type=entity, entity_id=entity_id
        )
    )
    db.flush()


def _provider_json(
    provider: str, settings: Settings, method: str, path: str, body: dict[str, Any] | None = None
) -> Any:
    """Call a provider service; map failures to admin-facing HTTP errors."""
    with provider_client(provider, settings) as client:
        try:
            response = (
                client.get(path)
                if method == "GET"
                else client.post(path, json=body or {})
            )
        except httpx.TimeoutException as exc:
            raise HTTPException(status_code=504, detail=f"{provider} timed out: {exc}") from exc
        except httpx.ConnectError as exc:
            raise HTTPException(status_code=502, detail=f"{provider} unreachable: {exc}") from exc
        except httpx.HTTPError as exc:
            raise HTTPException(status_code=502, detail=f"{provider} http error: {exc}") from exc
    if response.status_code == 429:
        retry_after = parse_retry_after_seconds(response.headers.get("retry-after"))
        raise HTTPException(
            status_code=429,
            detail=f"{provider} throttled; retry after {retry_after:.0f}s",
        )
    if response.status_code >= 400:
        code, detail = _error_code_and_detail(response)
        raise HTTPException(
            status_code=502 if response.status_code >= 500 else response.status_code,
            detail=f"{provider} error [{code or 'error'}]: {detail}",
        )
    try:
        return response.json()
    except ValueError as exc:
        raise HTTPException(status_code=502, detail=f"{provider} returned invalid JSON") from exc


@router.get("/admin/providers", response_model=list[ProviderStatus])
def provider_status(
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
    settings: Settings = Depends(get_settings),
) -> list[ProviderStatus]:
    _ = db, admin
    statuses: list[ProviderStatus] = []
    for provider in ADMIN_PROVIDERS:
        try:
            caps = _provider_json(provider, settings, "GET", "/v1/capabilities")
            stats: Any = None
            try:
                stats = _provider_json(provider, settings, "GET", "/v1/stats")
            except HTTPException:
                stats = None
            statuses.append(
                ProviderStatus(
                    provider=provider,
                    reachable=True,
                    configured=caps.get("supports_search"),
                    supports_search=bool(caps.get("supports_search")),
                    supports_fetch=bool(caps.get("supports_fetch")),
                    allows_storage=bool(caps.get("allows_storage")),
                    limiter=(stats or {}).get("limiter", {}),
                    upstream_requests=(stats or {}).get("upstream_requests"),
                )
            )
        except HTTPException as exc:
            statuses.append(
                ProviderStatus(provider=provider, reachable=False, error=str(exc.detail))
            )
    return statuses


@router.post("/admin/tests/provider-search")
def test_provider_search(
    body: ProviderTestSearch,
    request: Request,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
    settings: Settings = Depends(get_settings),
    _csrf: None = Depends(verify_csrf),
) -> Any:
    _enforce_quota(request, admin, settings.online_search_per_user_per_hour)
    result = _provider_json(
        body.provider, settings, "POST", "/v1/search", {"query": body.query, "limit": 5}
    )
    _audit(db, admin, "admin.provider_test_search", "provider", body.provider)
    return result


@router.post("/admin/tests/provider-fetch")
def test_provider_fetch(
    body: ProviderTestFetch,
    request: Request,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
    settings: Settings = Depends(get_settings),
    _csrf: None = Depends(verify_csrf),
) -> Any:
    _enforce_quota(request, admin, settings.online_search_per_user_per_hour)
    result = _provider_json(
        body.provider, settings, "POST", "/v1/fetch", {"external_id": body.external_id}
    )
    _audit(db, admin, "admin.provider_test_fetch", "provider", body.provider)
    return result


def _enforce_quota(request: Request, admin: User, limit: int) -> None:
    from app.core.quotas import QuotaExceeded

    try:
        request.app.state.quota_tracker.check(
            scope="online_search", user_id=admin.id, max_attempts=limit, window_seconds=3600.0
        )
    except QuotaExceeded as exc:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail=str(exc)
        ) from exc


@router.get("/admin/processing-profiles", response_model=list[ProfileOut])
def list_profiles(
    active_only: bool = Query(default=False),
    db: Session = Depends(get_db),
    _admin: User = Depends(require_admin),
) -> list[ProfileOut]:
    stmt = select(ProcessingProfile).order_by(ProcessingProfile.name, ProcessingProfile.version)
    if active_only:
        stmt = stmt.where(ProcessingProfile.is_active.is_(True))
    return [
        ProfileOut(
            id=p.id, name=p.name, version=p.version, config=p.config, is_active=p.is_active
        )
        for p in db.execute(stmt).scalars().all()
    ]


@router.post(
    "/admin/processing-profiles", response_model=ProfileOut, status_code=status.HTTP_201_CREATED
)
def create_profile(
    body: ProfileCreate,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
    settings: Settings = Depends(get_settings),
    _csrf: None = Depends(verify_csrf),
) -> ProfileOut:
    profile = {"schema_version": 1, "steps": body.steps, "outputs": body.outputs}
    errors = _validate_profile_remote(settings, profile)
    if errors:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="; ".join(errors),
        )
    latest = db.execute(
        select(ProcessingProfile.version)
        .where(ProcessingProfile.name == body.name.strip())
        .order_by(ProcessingProfile.version.desc())
        .limit(1)
    ).scalar_one_or_none()
    row = ProcessingProfile(
        name=body.name.strip(),
        version=(latest or 0) + 1,
        config=profile,
        is_active=True,
        created_by_id=admin.id,
    )
    db.add(row)
    db.flush()
    _audit(db, admin, "admin.profile_created", "profile", row.id)
    return ProfileOut(
        id=row.id, name=row.name, version=row.version, config=row.config, is_active=row.is_active
    )


@router.post("/admin/processing-profiles/{profile_id}/deactivate", response_model=ProfileOut)
def deactivate_profile(
    profile_id: str,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
    _csrf: None = Depends(verify_csrf),
) -> ProfileOut:
    row = db.get(ProcessingProfile, profile_id)
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="not found")
    row.is_active = False
    db.flush()
    _audit(db, admin, "admin.profile_deactivated", "profile", row.id)
    return ProfileOut(
        id=row.id, name=row.name, version=row.version, config=row.config, is_active=row.is_active
    )


@router.post("/admin/tests/process")
def preview_process(
    body: ProcessPreviewRequest,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
    settings: Settings = Depends(get_settings),
    _csrf: None = Depends(verify_csrf),
) -> Any:
    import httpx as _httpx

    client = _httpx.Client(
        base_url=settings.processor_url,
        transport=online_module.PROCESSOR_TRANSPORT,
        timeout=settings.processor_timeout_seconds,
        follow_redirects=False,
    )
    with client:
        try:
            response = client.post(
                "/v1/process",
                json={"source_text": body.source_text, "profile": body.profile},
            )
        except _httpx.TimeoutException as exc:
            raise HTTPException(status_code=504, detail=f"processor timed out: {exc}") from exc
        except _httpx.ConnectError as exc:
            raise HTTPException(status_code=502, detail=f"processor unreachable: {exc}") from exc
        except _httpx.HTTPError as exc:
            raise HTTPException(status_code=502, detail=f"processor http error: {exc}") from exc
    if response.status_code >= 400:
        raise HTTPException(status_code=502, detail=f"processor failed ({response.status_code})")
    _audit(db, admin, "admin.processor_preview", "processor", None)
    try:
        return response.json()
    except ValueError as exc:
        raise HTTPException(status_code=502, detail="processor returned invalid JSON") from exc


def _validate_profile_remote(settings: Settings, profile: dict[str, Any]) -> list[str]:
    import httpx as _httpx

    client = _httpx.Client(
        base_url=settings.processor_url,
        transport=online_module.PROCESSOR_TRANSPORT,
        timeout=settings.processor_timeout_seconds,
        follow_redirects=False,
    )
    with client:
        try:
            response = client.post("/v1/validate-profile", json=profile)
        except _httpx.HTTPError:
            return ["processor unreachable for validation"]
    if response.status_code != 200:
        return [f"processor validation failed ({response.status_code})"]
    try:
        body = response.json()
    except ValueError:
        return ["processor returned invalid JSON"]
    if not isinstance(body, dict) or body.get("valid"):
        return []
    errors = body.get("errors", [])
    return [str(e) for e in errors] if isinstance(errors, list) else ["invalid profile"]


@router.get("/admin/jobs", response_model=JobList)
def admin_list_jobs(
    job_status: str | None = Query(default=None, alias="status"),
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
    _admin: User = Depends(require_admin),
) -> JobList:
    stmt = select(Job).order_by(Job.created_at.desc())
    if job_status is not None:
        stmt = stmt.where(Job.status == job_status)
    rows = db.execute(stmt).scalars().all()
    items = [_job_out(job) for job in rows]
    total = len(items)
    return JobList(items=items[offset : offset + limit], total=total, limit=limit, offset=offset)


@router.get("/admin/audit")
def admin_audit(
    action: str | None = Query(default=None, max_length=128),
    limit: int = Query(default=50, ge=1, le=200),
    db: Session = Depends(get_db),
    _admin: User = Depends(require_admin),
) -> Any:
    stmt = select(AuditEvent).order_by(AuditEvent.created_at.desc()).limit(limit)
    if action:
        stmt = stmt.where(AuditEvent.action == action)
    return [
        {
            "id": event.id,
            "actor_user_id": event.actor_user_id,
            "action": event.action,
            "entity_type": event.entity_type,
            "entity_id": event.entity_id,
            "created_at": event.created_at.isoformat() if event.created_at else None,
        }
        for event in db.execute(stmt).scalars().all()
    ]
