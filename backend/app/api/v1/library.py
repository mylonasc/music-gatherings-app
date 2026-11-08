"""Track library: suggest/list/edit tracks, versions, votes, crew entries."""

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db, get_store, verify_csrf
from app.api.v1.schemas import (
    ArtifactOut,
    CrewTrackEntryOut,
    CrewTrackList,
    CrewTrackListItem,
    CrewTrackPatch,
    TrackDetail,
    TrackPatch,
    TrackSuggest,
    VersionCreate,
    VersionDetailOut,
    VersionOut,
    VoteIn,
)
from app.api.v1.visibility import (
    crew_or_404,
    my_vote,
    track_genre_names,
    upvote_count,
    user_crew_ids,
    version_artifact_kinds,
    version_count,
    visible_track,
    vote_score,
)
from app.models import (
    Artifact,
    AuditEvent,
    Crew,
    CrewTrack,
    Genre,
    Track,
    TrackGenre,
    TrackVersion,
    TrackVote,
    User,
)
from app.models.library import PIANO_VALUES
from app.search.index import reindex_track
from app.storage.local import LocalObjectStore

router = APIRouter()

MAX_PAGE = 100


def _get_or_create_genre(db: Session, name: str) -> Genre:
    cleaned = " ".join(name.split())
    if not cleaned:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="empty genre")
    existing = db.execute(
        select(Genre).where(func.lower(Genre.name) == cleaned.lower())
    ).scalar_one_or_none()
    if existing is not None:
        return existing
    genre = Genre(name=cleaned)
    db.add(genre)
    db.flush()
    return genre


def _check_piano(value: str) -> str:
    if value not in PIANO_VALUES:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="invalid piano_suitability"
        )
    return value


def _create_version(db: Session, track_id: str, body: VersionCreate) -> TrackVersion:
    version = TrackVersion(
        track_id=track_id,
        label=body.label,
        musical_key=body.musical_key,
        language=body.language,
        tuning=body.tuning,
        capo=body.capo,
        notes=body.notes,
    )
    db.add(version)
    db.flush()
    return version


def _requester_name(db: Session, user_id: str | None) -> str | None:
    if user_id is None:
        return None
    user = db.get(User, user_id)
    return user.username if user else None


def _list_item(
    db: Session,
    entry: CrewTrack,
    track: Track,
    user: User,
) -> CrewTrackListItem:
    return CrewTrackListItem(
        crew_track_id=entry.id,
        track_id=track.id,
        title=track.title,
        artist=track.artist,
        genres=track_genre_names(db, track.id),
        requester=_requester_name(db, entry.added_by_id),
        piano_suitability=entry.piano_suitability,
        vote_score=vote_score(db, entry.id),
        my_vote=my_vote(db, entry.id, user.id),
        version_count=version_count(db, track.id),
        artifact_kinds=version_artifact_kinds(db, track.id),
        can_remove=user.is_admin or entry.added_by_id == user.id,
        upvote_count=upvote_count(db, entry.id),
    )


@router.post(
    "/crews/{crew_id}/tracks",
    response_model=CrewTrackListItem,
    status_code=status.HTTP_201_CREATED,
)
def suggest_track(
    crew_id: str,
    body: TrackSuggest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    store: LocalObjectStore = Depends(get_store),
    _csrf: None = Depends(verify_csrf),
) -> CrewTrackListItem:
    crew = crew_or_404(db, user, crew_id)
    piano = _check_piano(body.piano_suitability)
    track = Track(
        title=body.title.strip() if body.title else None,
        artist=body.artist.strip() if body.artist else None,
        description=body.description,
        created_by_id=user.id,
    )
    db.add(track)
    db.flush()
    seen: set[str] = set()
    for raw_name in body.genres:
        key = raw_name.strip().lower()
        if not key or key in seen:
            continue
        seen.add(key)
        genre = _get_or_create_genre(db, raw_name)
        db.add(TrackGenre(track_id=track.id, genre_id=genre.id))
    for version_body in body.versions:
        _create_version(db, track.id, version_body)
    entry = CrewTrack(
        crew_id=crew.id,
        track_id=track.id,
        added_by_id=user.id,
        notes=body.notes,
        piano_suitability=piano,
    )
    db.add(entry)
    db.flush()
    db.add(
        AuditEvent(
            actor_user_id=user.id,
            action="track.suggested",
            entity_type="track",
            entity_id=track.id,
        )
    )
    reindex_track(db, store, track.id)
    return _list_item(db, entry, track, user)


@router.get("/crews/{crew_id}/tracks", response_model=CrewTrackList)
def list_crew_tracks(
    crew_id: str,
    genre: str | None = Query(default=None),
    piano_suggested: bool | None = Query(default=None),
    limit: int = Query(default=20, ge=1, le=MAX_PAGE),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> CrewTrackList:
    crew = crew_or_404(db, user, crew_id)
    stmt = (
        select(CrewTrack, Track)
        .join(Track, Track.id == CrewTrack.track_id)
        .where(CrewTrack.crew_id == crew.id)
        .order_by(CrewTrack.created_at.desc())
    )
    if piano_suggested is True:
        stmt = stmt.where(CrewTrack.piano_suitability == "suggested")
    elif piano_suggested is False:
        stmt = stmt.where(CrewTrack.piano_suitability != "suggested")
    rows = db.execute(stmt).all()
    items: list[CrewTrackListItem] = []
    for entry, track in rows:
        genres = track_genre_names(db, track.id)
        if genre and genre.strip().lower() not in {g.lower() for g in genres}:
            continue
        items.append(_list_item(db, entry, track, user))
    total = len(items)
    return CrewTrackList(
        items=items[offset : offset + limit], total=total, limit=limit, offset=offset
    )


@router.patch(
    "/crews/{crew_id}/tracks/{crew_track_id}", response_model=CrewTrackListItem
)
def update_crew_track(
    crew_id: str,
    crew_track_id: str,
    body: CrewTrackPatch,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    _csrf: None = Depends(verify_csrf),
) -> CrewTrackListItem:
    crew = crew_or_404(db, user, crew_id)
    entry = db.get(CrewTrack, crew_track_id)
    if entry is None or entry.crew_id != crew.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="not found")
    if entry.added_by_id != user.id and not user.is_admin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="not allowed")
    if body.notes is not None:
        entry.notes = body.notes
    if body.piano_suitability is not None:
        entry.piano_suitability = _check_piano(body.piano_suitability)
    db.flush()
    track = db.get(Track, entry.track_id)
    assert track is not None
    return _list_item(db, entry, track, user)


@router.delete(
    "/crews/{crew_id}/tracks/{crew_track_id}", status_code=status.HTTP_204_NO_CONTENT
)
def remove_crew_track(
    crew_id: str,
    crew_track_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    _csrf: None = Depends(verify_csrf),
) -> None:
    crew = crew_or_404(db, user, crew_id)
    entry = db.get(CrewTrack, crew_track_id)
    if entry is None or entry.crew_id != crew.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="not found")
    if entry.added_by_id != user.id and not user.is_admin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="not allowed")
    db.delete(entry)
    db.flush()
    db.add(
        AuditEvent(
            actor_user_id=user.id,
            action="track.unlisted",
            entity_type="crew_track",
            entity_id=crew_track_id,
        )
    )


@router.put(
    "/crews/{crew_id}/tracks/{crew_track_id}/vote", response_model=CrewTrackListItem
)
def put_vote(
    crew_id: str,
    crew_track_id: str,
    body: VoteIn,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    _csrf: None = Depends(verify_csrf),
) -> CrewTrackListItem:
    crew = crew_or_404(db, user, crew_id)
    entry = db.get(CrewTrack, crew_track_id)
    if entry is None or entry.crew_id != crew.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="not found")
    existing = db.execute(
        select(TrackVote).where(
            TrackVote.crew_track_id == entry.id, TrackVote.user_id == user.id
        )
    ).scalar_one_or_none()
    if existing is None:
        db.add(TrackVote(crew_track_id=entry.id, user_id=user.id, value=body.value))
    else:
        existing.value = body.value
    db.flush()
    track = db.get(Track, entry.track_id)
    assert track is not None
    return _list_item(db, entry, track, user)


@router.delete(
    "/crews/{crew_id}/tracks/{crew_track_id}/vote", status_code=status.HTTP_204_NO_CONTENT
)
def clear_vote(
    crew_id: str,
    crew_track_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    _csrf: None = Depends(verify_csrf),
) -> None:
    crew = crew_or_404(db, user, crew_id)
    entry = db.get(CrewTrack, crew_track_id)
    if entry is None or entry.crew_id != crew.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="not found")
    existing = db.execute(
        select(TrackVote).where(
            TrackVote.crew_track_id == entry.id, TrackVote.user_id == user.id
        )
    ).scalar_one_or_none()
    if existing is not None:
        db.delete(existing)
        db.flush()


def _version_out(db: Session, version: TrackVersion) -> VersionDetailOut:
    artifacts = (
        db.execute(select(Artifact).where(Artifact.track_version_id == version.id))
        .scalars()
        .all()
    )
    return VersionDetailOut(
        id=version.id,
        track_id=version.track_id,
        label=version.label,
        musical_key=version.musical_key,
        language=version.language,
        tuning=version.tuning,
        capo=version.capo,
        notes=version.notes,
        artifacts=[
            ArtifactOut(
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
            for a in artifacts
        ],
    )


def _entry_out(db: Session, entry: CrewTrack, crew_name: str, user: User) -> CrewTrackEntryOut:
    return CrewTrackEntryOut(
        crew_track_id=entry.id,
        crew_id=entry.crew_id,
        crew_name=crew_name,
        upvote_count=upvote_count(db, entry.id),
        can_remove=user.is_admin or entry.added_by_id == user.id,
        requester=_requester_name(db, entry.added_by_id),
        notes=entry.notes,
        piano_suitability=entry.piano_suitability,
        vote_score=vote_score(db, entry.id),
        my_vote=my_vote(db, entry.id, user.id),
    )


@router.get("/tracks/{track_id}", response_model=TrackDetail)
def get_track(
    track_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> TrackDetail:
    track = visible_track(db, user, track_id)
    versions = (
        db.execute(
            select(TrackVersion)
            .where(TrackVersion.track_id == track.id)
            .order_by(TrackVersion.created_at)
        )
        .scalars()
        .all()
    )
    crew_ids = (
        {
            e.crew_id
            for e in db.execute(select(CrewTrack).where(CrewTrack.track_id == track.id))
            .scalars()
            .all()
        }
        if user.is_admin
        else user_crew_ids(db, user)
    )
    entries: list[CrewTrackEntryOut] = []
    for entry in (
        db.execute(select(CrewTrack).where(CrewTrack.track_id == track.id)).scalars().all()
    ):
        if entry.crew_id not in crew_ids:
            continue
        crew = db.get(Crew, entry.crew_id)
        entries.append(_entry_out(db, entry, crew.name if crew else "?", user))
    return TrackDetail(
        id=track.id,
        title=track.title,
        artist=track.artist,
        description=track.description,
        genres=track_genre_names(db, track.id),
        versions=[_version_out(db, v) for v in versions],
        crew_entries=entries,
    )


@router.patch("/tracks/{track_id}", response_model=TrackDetail)
def update_track(
    track_id: str,
    body: TrackPatch,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    store: LocalObjectStore = Depends(get_store),
    _csrf: None = Depends(verify_csrf),
) -> TrackDetail:
    track = visible_track(db, user, track_id)
    if body.title is not None:
        track.title = body.title.strip() or None
    if body.artist is not None:
        track.artist = body.artist.strip() or None
    if body.description is not None:
        track.description = body.description
    if body.genres is not None:
        for link in (
            db.execute(select(TrackGenre).where(TrackGenre.track_id == track.id))
            .scalars()
            .all()
        ):
            db.delete(link)
        seen: set[str] = set()
        for raw_name in body.genres[:10]:
            key = raw_name.strip().lower()
            if not key or key in seen:
                continue
            seen.add(key)
            genre = _get_or_create_genre(db, raw_name)
            db.add(TrackGenre(track_id=track.id, genre_id=genre.id))
    db.flush()
    db.add(
        AuditEvent(
            actor_user_id=user.id,
            action="track.updated",
            entity_type="track",
            entity_id=track.id,
        )
    )
    reindex_track(db, store, track.id)
    return get_track(track_id, db, user)


@router.get("/tracks/{track_id}/versions", response_model=list[VersionOut])
def list_versions(
    track_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> list[VersionOut]:
    track = visible_track(db, user, track_id)
    versions = (
        db.execute(
            select(TrackVersion)
            .where(TrackVersion.track_id == track.id)
            .order_by(TrackVersion.created_at)
        )
        .scalars()
        .all()
    )
    return [
        VersionOut(
            id=v.id,
            track_id=v.track_id,
            label=v.label,
            musical_key=v.musical_key,
            language=v.language,
            tuning=v.tuning,
            capo=v.capo,
            notes=v.notes,
        )
        for v in versions
    ]


@router.post(
    "/tracks/{track_id}/versions",
    response_model=VersionOut,
    status_code=status.HTTP_201_CREATED,
)
def add_version(
    track_id: str,
    body: VersionCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    _csrf: None = Depends(verify_csrf),
) -> VersionOut:
    track = visible_track(db, user, track_id)
    version = _create_version(db, track.id, body)
    db.add(
        AuditEvent(
            actor_user_id=user.id,
            action="track.version_added",
            entity_type="track_version",
            entity_id=version.id,
        )
    )
    return VersionOut(
        id=version.id,
        track_id=version.track_id,
        label=version.label,
        musical_key=version.musical_key,
        language=version.language,
        tuning=version.tuning,
        capo=version.capo,
        notes=version.notes,
    )
