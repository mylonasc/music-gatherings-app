"""Provenance and artifact schema: sources, stored objects, derivations."""

from typing import Any

from sqlalchemy import JSON, Boolean, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, CreatedOnly, Identified

STORAGE_PERMISSION_UNKNOWN = "unknown"
STORAGE_PERMISSION_LINK_ONLY = "link_only"
STORAGE_PERMISSION_ALLOWED = "allowed"
STORAGE_PERMISSIONS = (
    STORAGE_PERMISSION_UNKNOWN,
    STORAGE_PERMISSION_LINK_ONLY,
    STORAGE_PERMISSION_ALLOWED,
)

ARTIFACT_KINDS = (
    "lyrics",
    "chord_chart",
    "tablature",
    "sheet_music",
    "canonical_document",
    "rendered_lyrics",
    "rendered_chord_chart",
)


class SourceRecord(Base, Identified, CreatedOnly):
    """Where an artifact came from: provider reference and usage rights."""

    __tablename__ = "source_records"

    track_version_id: Mapped[str | None] = mapped_column(
        ForeignKey("track_versions.id", ondelete="SET NULL"), nullable=True
    )
    provider: Mapped[str] = mapped_column(String(64), nullable=False)
    external_id: Mapped[str | None] = mapped_column(String(256), nullable=True)
    source_url: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    attribution: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    storage_permission: Mapped[str] = mapped_column(
        String(16), nullable=False, default=STORAGE_PERMISSION_UNKNOWN
    )
    license_note: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    created_by_id: Mapped[str | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )


class Artifact(Base, Identified, CreatedOnly):
    """Lyrics, charts, tabs, scores, canonical docs, or rendered outputs.

    Stored bytes live in the object store under ``object_key``. Link-only
    references keep ``object_key`` NULL and point at ``external_url``.
    """

    __tablename__ = "artifacts"

    track_version_id: Mapped[str] = mapped_column(
        ForeignKey("track_versions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    source_record_id: Mapped[str | None] = mapped_column(
        ForeignKey("source_records.id", ondelete="SET NULL"), nullable=True
    )
    kind: Mapped[str] = mapped_column(String(32), nullable=False)
    mime_type: Mapped[str] = mapped_column(String(128), nullable=False)
    byte_size: Mapped[int | None] = mapped_column(Integer, nullable=True)
    sha256: Mapped[str | None] = mapped_column(String(64), nullable=True)
    object_key: Mapped[str | None] = mapped_column(
        String(256), nullable=True, unique=True
    )
    file_name: Mapped[str | None] = mapped_column(String(256), nullable=True)
    language: Mapped[str | None] = mapped_column(String(16), nullable=True)
    is_external: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    external_url: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    created_by_id: Mapped[str | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )


class ArtifactDerivation(Base, Identified, CreatedOnly):
    """Lineage for a derived artifact: inputs, profile, processor, diagnostics."""

    __tablename__ = "artifact_derivations"

    output_artifact_id: Mapped[str] = mapped_column(
        ForeignKey("artifacts.id", ondelete="CASCADE"), nullable=False, unique=True
    )
    processor_name: Mapped[str] = mapped_column(String(64), nullable=False)
    processor_version: Mapped[str] = mapped_column(String(32), nullable=False)
    profile: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    input_artifact_ids: Mapped[list[str]] = mapped_column(JSON, nullable=False)
    diagnostics: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)


class ProcessingProfile(Base, Identified, CreatedOnly):
    """Named, versioned transformation configuration (validated in S09)."""

    __tablename__ = "processing_profiles"
    __table_args__ = (UniqueConstraint("name", "version", name="uq_profile_name_version"),)

    name: Mapped[str] = mapped_column(String(128), nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    config: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_by_id: Mapped[str | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
