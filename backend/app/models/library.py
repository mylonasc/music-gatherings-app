"""Track library schema: identity, versions, genres, crew lists, votes."""

from sqlalchemy import CheckConstraint, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, CreatedOnly, Identified, Timestamped

PIANO_UNKNOWN = "unknown"
PIANO_SUGGESTED = "suggested"
PIANO_NOT_SUGGESTED = "not_suggested"
PIANO_VALUES = (PIANO_UNKNOWN, PIANO_SUGGESTED, PIANO_NOT_SUGGESTED)


class Track(Base, Identified, Timestamped):
    """A song identity. Title and artist are optional by design."""

    __tablename__ = "tracks"

    title: Mapped[str | None] = mapped_column(String(256), nullable=True)
    artist: Mapped[str | None] = mapped_column(String(256), nullable=True)
    description: Mapped[str | None] = mapped_column(String(2048), nullable=True)
    created_by_id: Mapped[str | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )


class TrackVersion(Base, Identified, Timestamped):
    """A musical arrangement/transcription/performance of a track."""

    __tablename__ = "track_versions"

    track_id: Mapped[str] = mapped_column(
        ForeignKey("tracks.id", ondelete="CASCADE"), nullable=False, index=True
    )
    label: Mapped[str | None] = mapped_column(String(128), nullable=True)
    musical_key: Mapped[str | None] = mapped_column(String(16), nullable=True)
    language: Mapped[str | None] = mapped_column(String(16), nullable=True)
    tuning: Mapped[str | None] = mapped_column(String(64), nullable=True)
    capo: Mapped[int | None] = mapped_column(Integer, nullable=True)
    notes: Mapped[str | None] = mapped_column(String(2048), nullable=True)
    created_by_id: Mapped[str | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )


class Genre(Base, Identified, CreatedOnly):
    __tablename__ = "genres"

    name: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)


class TrackGenre(Base, Identified, CreatedOnly):
    __tablename__ = "track_genres"
    __table_args__ = (UniqueConstraint("track_id", "genre_id", name="uq_track_genre"),)

    track_id: Mapped[str] = mapped_column(
        ForeignKey("tracks.id", ondelete="CASCADE"), nullable=False
    )
    genre_id: Mapped[str] = mapped_column(
        ForeignKey("genres.id", ondelete="CASCADE"), nullable=False
    )


class CrewTrack(Base, Identified, CreatedOnly):
    """A track added to a crew's shared list with crew-specific metadata."""

    __tablename__ = "crew_tracks"
    __table_args__ = (UniqueConstraint("crew_id", "track_id", name="uq_crew_track"),)

    crew_id: Mapped[str] = mapped_column(
        ForeignKey("crews.id", ondelete="CASCADE"), nullable=False
    )
    track_id: Mapped[str] = mapped_column(
        ForeignKey("tracks.id", ondelete="CASCADE"), nullable=False
    )
    added_by_id: Mapped[str | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    notes: Mapped[str | None] = mapped_column(String(2048), nullable=True)
    piano_suitability: Mapped[str] = mapped_column(
        String(16), nullable=False, default=PIANO_UNKNOWN
    )


class TrackVote(Base, Identified, CreatedOnly):
    __tablename__ = "track_votes"
    __table_args__ = (
        UniqueConstraint("crew_track_id", "user_id", name="uq_vote_crew_track_user"),
        CheckConstraint("value IN (-1, 1)", name="ck_vote_value"),
    )

    crew_track_id: Mapped[str] = mapped_column(
        ForeignKey("crew_tracks.id", ondelete="CASCADE"), nullable=False
    )
    user_id: Mapped[str] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    value: Mapped[int] = mapped_column(Integer, nullable=False)
