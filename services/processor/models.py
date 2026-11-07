"""Canonical document, profile, and process request/response schemas (v1)."""

from typing import Any, Literal

from pydantic import BaseModel, Field

SectionKind = Literal[
    "intro", "verse", "pre_chorus", "chorus", "bridge", "solo",
    "interlude", "outro", "custom",
]

OutputName = Literal["canonical_json", "lyrics_text", "lyrics_html", "chord_chart_html"]


class ChordPlacement(BaseModel):
    position: int = Field(ge=0)
    chord: str = Field(min_length=1, max_length=32)


class LyricLine(BaseModel):
    lyrics: str = Field(max_length=2000)
    chords: list[ChordPlacement] = Field(default_factory=list)


class Section(BaseModel):
    id: str = Field(min_length=1, max_length=64)
    kind: SectionKind = "custom"
    label: str = Field(min_length=1, max_length=128)
    lines: list[LyricLine] = Field(default_factory=list)
    tablature: list[str] = Field(default_factory=list)
    repeat_of: str | None = None
    repeat_count: int = Field(default=1, ge=1, le=16)


class CanonicalDocument(BaseModel):
    schema_version: Literal[1] = 1
    title: str | None = None
    artist: str | None = None
    musical_key: str | None = None
    sections: list[Section] = Field(default_factory=list)


class ProfileStep(BaseModel):
    type: str = Field(min_length=1, max_length=64)
    config: dict[str, Any] = Field(default_factory=dict)


class ProcessingProfile(BaseModel):
    schema_version: Literal[1] = 1
    steps: list[ProfileStep] = Field(default_factory=list, max_length=16)
    outputs: list[OutputName] = Field(default_factory=list, max_length=8)


class ProcessRequest(BaseModel):
    source_text: str = Field(min_length=1, max_length=1_000_000)
    profile: ProcessingProfile
    title: str | None = Field(default=None, max_length=256)
    artist: str | None = Field(default=None, max_length=256)


class ProcessResponse(BaseModel):
    canonical: CanonicalDocument
    outputs: dict[str, str] = Field(default_factory=dict)
    warnings: list[str] = Field(default_factory=list)
    processor_version: str = "0.1.0"


class DiagnosticResponse(BaseModel):
    valid: bool
    errors: list[str] = Field(default_factory=list)


CONTRACT_MODELS: dict[str, type[BaseModel]] = {
    "canonical": CanonicalDocument,
    "profile": ProcessingProfile,
    "process_request": ProcessRequest,
    "process_response": ProcessResponse,
}
