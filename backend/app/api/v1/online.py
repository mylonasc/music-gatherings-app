"""Online discovery endpoints: provider search jobs, explicit imports,
context-specific representations. Search never mutates the library."""

from typing import Any, Literal

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db, get_settings, verify_csrf
from app.api.v1.jobs import JobOut, _job_out
from app.api.v1.schemas import ArtifactOut
from app.api.v1.visibility import crew_or_404, visible_track
from app.core.config import Settings
from app.core.quotas import QuotaExceeded
from app.jobs.online import provider_client
from app.jobs.service import create_job
from app.models import Artifact, ArtifactDerivation, SourceRecord, TrackVersion, User

router = APIRouter()

PROVIDER_NAMES = ("fake", "lrclib", "ultimate_guitar")
ARTIFACT_TYPES = ("lyrics", "chord_chart", "tablature", "sheet_music")


class ProviderOption(BaseModel):
    provider: str
    supports_search: bool = False
    supports_fetch: bool = False
    allows_storage: bool = False
    artifact_types: list[str] = Field(default_factory=list)
    storage_note: str = ""
    available: bool = False


@router.get("/providers", response_model=list[ProviderOption])
def discovery_providers(
    user: User = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
) -> list[ProviderOption]:
    """Read only private capability metadata; never initiate provider search/fetch."""
    options: list[ProviderOption] = []
    for name in PROVIDER_NAMES:
        option = ProviderOption(provider=name)
        if name not in settings.online_provider_urls:
            options.append(option)
            continue
        try:
            with provider_client(name, settings) as client:
                response = client.get("/v1/capabilities", timeout=2.0)
            response.raise_for_status()
            caps = response.json()
            if isinstance(caps, dict):
                option = ProviderOption(
                    provider=name, available=True,
                    supports_search=caps.get("supports_search") is True,
                    supports_fetch=caps.get("supports_fetch") is True,
                    allows_storage=caps.get("allows_storage") is True,
                    artifact_types=[
                        k for k in caps.get("artifact_types", []) if k in ARTIFACT_TYPES
                    ],
                    storage_note=str(caps.get("storage_note", ""))[:1000],
                )
        except (httpx.HTTPError, ValueError, TypeError):
            pass  # Do not expose internal service URLs or exception diagnostics.
        options.append(option)
    return options

CONTEXT_KINDS: dict[str, list[str]] = {
    "audience": ["lyrics", "rendered_lyrics"],
    "guitar": ["chord_chart", "rendered_chord_chart", "tablature"],
    "piano": ["sheet_music", "chord_chart", "rendered_chord_chart"],
}


class OnlineSearchRequest(BaseModel):
    query: str = Field(min_length=1, max_length=200)
    providers: list[str] = Field(default_factory=lambda: ["fake"], max_length=5)
    artifact_types: list[str] = Field(default_factory=list, max_length=4)
    crew_id: str


class ImportRequest(BaseModel):
    provider: str
    external_id: str = Field(min_length=1, max_length=512)
    crew_id: str
    track_id: str | None = None
    version_id: str | None = None
    version_label: str | None = Field(default=None, max_length=128)
    artifact_types: list[str] = Field(default_factory=list, max_length=4)
    profile: dict[str, Any] | None = None
    idempotency_key: str | None = Field(default=None, max_length=128)


class RepresentationItem(BaseModel):
    artifact: ArtifactOut
    source_provider: str | None = None
    attribution: str | None = None
    derived: bool = False
    warnings: list[str] = Field(default_factory=list)


class RepresentationResponse(BaseModel):
    context: str
    track_id: str
    items: list[RepresentationItem] = Field(default_factory=list)


def _enforce_quota(request: Request, scope: str, user: User, max_attempts: int) -> None:
    try:
        request.app.state.quota_tracker.check(
            scope=scope, user_id=user.id, max_attempts=max_attempts, window_seconds=3600.0
        )
    except QuotaExceeded as exc:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail=str(exc)
        ) from exc


def _validate_providers(providers: list[str]) -> list[str]:
    unknown = [p for p in providers if p not in PROVIDER_NAMES]
    if unknown:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"unknown providers: {', '.join(unknown)}",
        )
    return providers


def _validate_artifact_types(types: list[str]) -> list[str]:
    unknown = [t for t in types if t not in ARTIFACT_TYPES]
    if unknown:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"unknown artifact types: {', '.join(unknown)}",
        )
    return types


@router.post("/search/online", response_model=JobOut, status_code=status.HTTP_202_ACCEPTED)
def start_online_search(
    body: OnlineSearchRequest,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
    _csrf: None = Depends(verify_csrf),
) -> JobOut:
    crew_or_404(db, user, body.crew_id)
    _enforce_quota(
        request, "online_search", user, settings.online_search_per_user_per_hour
    )
    providers = _validate_providers(list(dict.fromkeys(body.providers)))
    if not providers:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="no providers requested"
        )
    job, _created = create_job(
        db,
        kind="online.search",
        payload={
            "query": body.query.strip(),
            "providers": providers,
            "artifact_types": _validate_artifact_types(body.artifact_types),
            "crew_id": body.crew_id,
            "created_by_id": user.id,
        },
        crew_id=body.crew_id,
        created_by_id=user.id,
    )
    return _job_out(job)


@router.post("/imports", response_model=JobOut, status_code=status.HTTP_202_ACCEPTED)
def start_import(
    body: ImportRequest,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
    _csrf: None = Depends(verify_csrf),
) -> JobOut:
    crew_or_404(db, user, body.crew_id)
    _enforce_quota(
        request, "online_import", user, settings.online_import_per_user_per_hour
    )
    _validate_providers([body.provider])
    artifact_types = _validate_artifact_types(body.artifact_types)
    if body.track_id is not None:
        visible_track(db, user, body.track_id)
    if body.version_id is not None:
        version = db.get(TrackVersion, body.version_id)
        if version is None or (body.track_id and version.track_id != body.track_id):
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="not found")
    job, _created = create_job(
        db,
        kind="online.import",
        payload={
            "provider": body.provider,
            "external_id": body.external_id,
            "crew_id": body.crew_id,
            "track_id": body.track_id,
            "version_id": body.version_id,
            "version_label": body.version_label,
            "artifact_types": artifact_types,
            "profile": body.profile,
            "created_by_id": user.id,
        },
        crew_id=body.crew_id,
        created_by_id=user.id,
        idempotency_key=body.idempotency_key,
    )
    return _job_out(job)


@router.get("/tracks/{track_id}/representations", response_model=RepresentationResponse)
def get_representations(
    track_id: str,
    context: Literal["audience", "guitar", "piano"] = Query(default="audience"),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> RepresentationResponse:
    track = visible_track(db, user, track_id)
    wanted = CONTEXT_KINDS[context]
    versions = (
        db.execute(
            select(TrackVersion)
            .where(TrackVersion.track_id == track.id)
            .order_by(TrackVersion.created_at)
        )
        .scalars()
        .all()
    )
    items: list[RepresentationItem] = []
    for version in versions:
        artifacts = (
            db.execute(
                select(Artifact).where(Artifact.track_version_id == version.id)
            )
            .scalars()
            .all()
        )
        ranked = sorted(
            [a for a in artifacts if a.kind in wanted],
            key=lambda a: (wanted.index(a.kind), a.is_external),
        )
        for artifact in ranked:
            source = (
                db.get(SourceRecord, artifact.source_record_id)
                if artifact.source_record_id
                else None
            )
            derivation = (
                db.execute(
                    select(ArtifactDerivation).where(
                        ArtifactDerivation.output_artifact_id == artifact.id
                    )
                ).scalar_one_or_none()
            )
            diagnostics = derivation.diagnostics if derivation else None
            warnings: list[str] = []
            if isinstance(diagnostics, dict):
                raw_warnings = diagnostics.get("warnings", [])
                if isinstance(raw_warnings, list):
                    warnings = [str(w) for w in raw_warnings]
            items.append(
                RepresentationItem(
                    artifact=ArtifactOut(
                        id=artifact.id,
                        track_version_id=artifact.track_version_id,
                        kind=artifact.kind,
                        mime_type=artifact.mime_type,
                        byte_size=artifact.byte_size,
                        sha256=artifact.sha256,
                        is_external=artifact.is_external,
                        external_url=artifact.external_url,
                        file_name=artifact.file_name,
                        language=artifact.language,
                    ),
                    source_provider=source.provider if source else None,
                    attribution=source.attribution if source else None,
                    derived=derivation is not None,
                    warnings=warnings,
                )
            )
    return RepresentationResponse(context=context, track_id=track.id, items=items)
