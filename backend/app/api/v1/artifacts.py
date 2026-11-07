"""Artifact upload, external references, metadata, and protected serving."""

import os

from fastapi import APIRouter, Depends, Form, HTTPException, Response, UploadFile, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db, get_settings, get_store, verify_csrf
from app.api.v1.schemas import ArtifactOut, ArtifactReferenceIn
from app.api.v1.visibility import visible_track
from app.core.config import Settings
from app.models import Artifact, AuditEvent, SourceRecord, TrackVersion, User
from app.models.provenance import ARTIFACT_KINDS
from app.search.index import reindex_track
from app.storage.local import LocalObjectStore, ObjectTooLargeError

router = APIRouter()

EXTENSION_MIME = {
    ".txt": "text/plain",
    ".md": "text/plain",
    ".pdf": "application/pdf",
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
}


def _artifact_out(a: Artifact) -> ArtifactOut:
    return ArtifactOut(
        id=a.id,
        track_version_id=a.track_version_id,
        kind=a.kind,
        mime_type=a.mime_type,
        byte_size=a.byte_size,
        sha256=a.sha256,
        is_external=a.is_external,
        external_url=a.external_url,
        file_name=a.file_name,
        language=a.language,
    )


def _check_kind(kind: str) -> str:
    if kind not in ARTIFACT_KINDS:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="invalid artifact kind"
        )
    return kind


def _get_version(db: Session, user: User, track_id: str, version_id: str) -> TrackVersion:
    track = visible_track(db, user, track_id)
    version = db.get(TrackVersion, version_id)
    if version is None or version.track_id != track.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="not found")
    return version


def _safe_file_name(name: str | None) -> str | None:
    if not name:
        return None
    base = os.path.basename(name.strip())
    return base[:255] or None


@router.post(
    "/tracks/{track_id}/versions/{version_id}/artifacts/upload",
    response_model=ArtifactOut,
    status_code=status.HTTP_201_CREATED,
)
def upload_artifact(
    track_id: str,
    version_id: str,
    file: UploadFile,
    kind: str = Form(...),
    language: str | None = Form(default=None),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
    store: LocalObjectStore = Depends(get_store),
    _csrf: None = Depends(verify_csrf),
) -> ArtifactOut:
    version = _get_version(db, user, track_id, version_id)
    _check_kind(kind)
    original = file.filename or ""
    ext = os.path.splitext(original)[1].lower()
    mime_type = EXTENSION_MIME.get(ext)
    if mime_type is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="unsupported file type"
        )
    data = file.file.read()
    if len(data) > settings.max_object_bytes:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, detail="file too large"
        )
    if not data:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="empty file"
        )
    try:
        stored = store.put(data)
    except ObjectTooLargeError as exc:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, detail=str(exc)
        ) from exc
    source = SourceRecord(
        track_version_id=version.id,
        provider="manual-upload",
        storage_permission="allowed",
        created_by_id=user.id,
    )
    db.add(source)
    db.flush()
    artifact = Artifact(
        track_version_id=version.id,
        source_record_id=source.id,
        kind=kind,
        mime_type=mime_type,
        byte_size=stored.size,
        sha256=stored.sha256,
        object_key=stored.key,
        file_name=_safe_file_name(original),
        language=language,
        is_external=False,
        created_by_id=user.id,
    )
    db.add(artifact)
    db.flush()
    db.add(
        AuditEvent(
            actor_user_id=user.id,
            action="artifact.uploaded",
            entity_type="artifact",
            entity_id=artifact.id,
        )
    )
    reindex_track(db, store, version.track_id)
    return _artifact_out(artifact)


@router.post(
    "/tracks/{track_id}/versions/{version_id}/artifacts/reference",
    response_model=ArtifactOut,
    status_code=status.HTTP_201_CREATED,
)
def reference_artifact(
    track_id: str,
    version_id: str,
    body: ArtifactReferenceIn,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    _csrf: None = Depends(verify_csrf),
) -> ArtifactOut:
    version = _get_version(db, user, track_id, version_id)
    _check_kind(body.kind)
    if not body.external_url.startswith(("https://", "http://")):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="invalid external URL"
        )
    source = SourceRecord(
        track_version_id=version.id,
        provider="external",
        source_url=body.external_url,
        attribution=body.attribution,
        storage_permission="link_only",
        created_by_id=user.id,
    )
    db.add(source)
    db.flush()
    artifact = Artifact(
        track_version_id=version.id,
        source_record_id=source.id,
        kind=body.kind,
        mime_type="text/uri-list",
        is_external=True,
        external_url=body.external_url,
        file_name=_safe_file_name(body.file_name),
        language=body.language,
        created_by_id=user.id,
    )
    db.add(artifact)
    db.flush()
    return _artifact_out(artifact)


def _visible_artifact(db: Session, user: User, artifact_id: str) -> Artifact:
    artifact = db.get(Artifact, artifact_id)
    if artifact is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="not found")
    version = db.get(TrackVersion, artifact.track_version_id)
    if version is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="not found")
    visible_track(db, user, version.track_id)
    return artifact


@router.get("/artifacts/{artifact_id}", response_model=ArtifactOut)
def get_artifact(
    artifact_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> ArtifactOut:
    return _artifact_out(_visible_artifact(db, user, artifact_id))


@router.get("/artifacts/{artifact_id}/content")
def get_artifact_content(
    artifact_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    store: LocalObjectStore = Depends(get_store),
) -> Response:
    artifact = _visible_artifact(db, user, artifact_id)
    if artifact.is_external or not artifact.object_key:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="no stored content")
    try:
        data = store.get(artifact.object_key)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="stored object missing"
        ) from exc
    filename = artifact.file_name or f"{artifact.id}.bin"
    return Response(
        content=data,
        media_type=artifact.mime_type,
        headers={
            # Never serve user uploads inline: prevents stored HTML/SVG/JS execution.
            "Content-Disposition": f'attachment; filename="{filename}"',
            "X-Content-Type-Options": "nosniff",
        },
    )
