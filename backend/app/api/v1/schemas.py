"""Pydantic schemas for S03 identity/crew endpoints."""

from typing import Literal

from pydantic import BaseModel, Field


class UserOut(BaseModel):
    id: str
    username: str
    display_name: str | None = None
    is_admin: bool


class LoginRequest(BaseModel):
    username: str = Field(min_length=1, max_length=64)
    password: str = Field(min_length=1, max_length=256)


class LoginResponse(BaseModel):
    csrf_token: str
    user: UserOut


class AccessRequestCreate(BaseModel):
    username: str = Field(min_length=1, max_length=64)
    password: str = Field(min_length=8, max_length=256)
    message: str | None = Field(default=None, max_length=1024)


class AccessRequestOut(BaseModel):
    id: str
    username: str
    status: str


class CrewOut(BaseModel):
    id: str
    name: str
    description: str | None = None


class CrewCreate(BaseModel):
    name: str = Field(min_length=1, max_length=128)
    description: str | None = Field(default=None, max_length=1024)


class MemberOut(BaseModel):
    user_id: str
    username: str
    role: str


class MemberAdd(BaseModel):
    user_id: str
    role: str = "member"


# --- S04 library schemas -------------------------------------------------


class VersionCreate(BaseModel):
    label: str | None = Field(default=None, max_length=128)
    musical_key: str | None = Field(default=None, max_length=16)
    language: str | None = Field(default=None, max_length=16)
    tuning: str | None = Field(default=None, max_length=64)
    capo: int | None = Field(default=None, ge=0, le=12)
    notes: str | None = Field(default=None, max_length=2048)


class VersionOut(VersionCreate):
    id: str
    track_id: str


class ArtifactOut(BaseModel):
    id: str
    track_version_id: str
    kind: str
    mime_type: str
    byte_size: int | None
    sha256: str | None
    is_external: bool
    external_url: str | None
    file_name: str | None
    language: str | None


class VersionDetailOut(VersionOut):
    artifacts: list[ArtifactOut] = Field(default_factory=list)

class TrackSuggest(BaseModel):
    title: str | None = Field(default=None, max_length=256)
    artist: str | None = Field(default=None, max_length=256)
    description: str | None = Field(default=None, max_length=2048)
    genres: list[str] = Field(default_factory=list, max_length=10)
    versions: list[VersionCreate] = Field(default_factory=list, max_length=10)
    notes: str | None = Field(default=None, max_length=2048)
    piano_suitability: str = "unknown"


class CrewTrackListItem(BaseModel):
    crew_track_id: str
    track_id: str
    title: str | None
    artist: str | None
    genres: list[str]
    requester: str | None
    piano_suitability: str
    vote_score: int
    my_vote: int | None
    version_count: int
    artifact_kinds: list[str]
    can_remove: bool = False


class CrewTrackList(BaseModel):
    items: list[CrewTrackListItem]
    total: int
    limit: int
    offset: int


class CrewTrackEntryOut(BaseModel):
    crew_track_id: str
    crew_id: str
    crew_name: str
    requester: str | None
    notes: str | None
    piano_suitability: str
    vote_score: int
    my_vote: int | None
    can_remove: bool = False


class CrewTrackPatch(BaseModel):
    notes: str | None = Field(default=None, max_length=2048)
    piano_suitability: str | None = None


class TrackDetail(BaseModel):
    id: str
    title: str | None
    artist: str | None
    description: str | None
    genres: list[str]
    versions: list[VersionDetailOut]
    crew_entries: list[CrewTrackEntryOut]


class TrackPatch(BaseModel):
    title: str | None = Field(default=None, max_length=256)
    artist: str | None = Field(default=None, max_length=256)
    description: str | None = Field(default=None, max_length=2048)
    genres: list[str] | None = None


class ArtifactReferenceIn(BaseModel):
    kind: str = Field(max_length=32)
    external_url: str = Field(max_length=1024)
    attribution: str | None = Field(default=None, max_length=1024)
    language: str | None = Field(default=None, max_length=16)
    file_name: str | None = Field(default=None, max_length=256)


class VoteIn(BaseModel):
    value: Literal[1, -1]
