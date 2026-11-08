"""Crew-scoped visibility helpers shared by library and artifact endpoints."""

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import Artifact, Crew, CrewMembership, CrewTrack, Track, TrackVote, User


def user_crew_ids(db: Session, user: User) -> set[str]:
    if user.is_admin:
        return {row.id for row in db.execute(select(Crew)).scalars().all()}
    rows = db.execute(
        select(CrewMembership.crew_id).where(CrewMembership.user_id == user.id)
    ).all()
    return {row[0] for row in rows}


def crew_or_404(db: Session, user: User, crew_id: str) -> Crew:
    crew = db.get(Crew, crew_id)
    if crew is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="not found")
    if not user.is_admin:
        member = db.execute(
            select(CrewMembership).where(
                CrewMembership.crew_id == crew.id, CrewMembership.user_id == user.id
            )
        ).scalar_one_or_none()
        if member is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="not found")
    return crew


def visible_track(db: Session, user: User, track_id: str) -> Track:
    track = db.get(Track, track_id)
    if track is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="not found")
    if not user.is_admin:
        crew_ids = user_crew_ids(db, user)
        if not crew_ids:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="not found")
        listed = db.execute(
            select(CrewTrack.id).where(
                CrewTrack.track_id == track.id, CrewTrack.crew_id.in_(crew_ids)
            )
        ).first()
        if listed is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="not found")
    return track


def vote_score(db: Session, crew_track_id: str) -> int:
    total = db.execute(
        select(func.coalesce(func.sum(TrackVote.value), 0)).where(
            TrackVote.crew_track_id == crew_track_id
        )
    ).scalar_one()
    return int(total)


def my_vote(db: Session, crew_track_id: str, user_id: str) -> int | None:
    row = db.execute(
        select(TrackVote.value).where(
            TrackVote.crew_track_id == crew_track_id, TrackVote.user_id == user_id
        )
    ).scalar_one_or_none()
    return row


def upvote_count(db: Session, crew_track_id: str) -> int:
    """Positive reactions only; historical negative votes are not likes."""
    return int(db.execute(select(func.count()).select_from(TrackVote).where(
        TrackVote.crew_track_id == crew_track_id, TrackVote.value == 1,
    )).scalar_one())


def track_genre_names(db: Session, track_id: str) -> list[str]:
    from app.models import Genre, TrackGenre

    rows = (
        db.execute(
            select(Genre.name)
            .join(TrackGenre, TrackGenre.genre_id == Genre.id)
            .where(TrackGenre.track_id == track_id)
            .order_by(Genre.name)
        )
        .scalars()
        .all()
    )
    return list(rows)


def version_artifact_kinds(db: Session, track_id: str) -> list[str]:
    from app.models import TrackVersion

    rows = (
        db.execute(
            select(func.distinct(Artifact.kind))
            .join(TrackVersion, TrackVersion.id == Artifact.track_version_id)
            .where(TrackVersion.track_id == track_id)
            .order_by(Artifact.kind)
        )
        .scalars()
        .all()
    )
    return [row for row in rows if row is not None]


def version_count(db: Session, track_id: str) -> int:
    from app.models import TrackVersion

    return int(
        db.execute(
            select(func.count()).where(TrackVersion.track_id == track_id)
        ).scalar_one()
    )
