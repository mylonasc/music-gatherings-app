"""Application-managed FTS5 index for track search.

One row per track (never per artifact, so results never duplicate). Indexed
text is track-level only (title/artist/description/genres/lyrics); per-crew
notes are deliberately excluded so snippets cannot leak across crews.
"""

from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.models import Artifact, Genre, Track, TrackGenre, TrackVersion
from app.storage.local import LocalObjectStore

FTS_TABLE = "track_search_fts"

FTS_DDL = f"""
CREATE VIRTUAL TABLE IF NOT EXISTS {FTS_TABLE} USING fts5(
    track_id UNINDEXED,
    title,
    artist,
    genres,
    lyrics,
    tokenize='unicode61'
)
""".strip()

MAX_LYRICS_CHARS = 200_000


def ensure_search_schema(db: Session) -> None:
    db.execute(text(FTS_DDL))
    db.flush()


def _lyrics_for_track(db: Session, store: LocalObjectStore, track_id: str) -> str:
    version_ids = [
        row[0]
        for row in db.execute(
            select(TrackVersion.id).where(TrackVersion.track_id == track_id)
        ).all()
    ]
    if not version_ids:
        return ""
    rows = (
        db.execute(
            select(Artifact.object_key).where(
                Artifact.track_version_id.in_(version_ids),
                Artifact.kind == "lyrics",
                Artifact.is_external.is_(False),
                Artifact.mime_type == "text/plain",
            )
        )
        .scalars()
        .all()
    )
    parts: list[str] = []
    total = 0
    for key in rows:
        if not key:
            continue
        try:
            raw = store.get(key)
        except Exception:
            continue
        try:
            decoded = raw.decode("utf-8", errors="ignore")
        except Exception:
            continue
        if total + len(decoded) > MAX_LYRICS_CHARS:
            decoded = decoded[: max(0, MAX_LYRICS_CHARS - total)]
        parts.append(decoded)
        total += len(decoded)
        if total >= MAX_LYRICS_CHARS:
            break
    return "\n".join(parts)


def reindex_track(db: Session, store: LocalObjectStore, track_id: str) -> None:
    """Rebuild the FTS row for a track (insert or replace)."""
    ensure_search_schema(db)
    track = db.get(Track, track_id)
    if track is None:
        remove_track(db, track_id)
        return
    genre_names = (
        db.execute(
            select(Genre.name)
            .join(TrackGenre, TrackGenre.genre_id == Genre.id)
            .where(TrackGenre.track_id == track_id)
        )
        .scalars()
        .all()
    )
    lyrics = _lyrics_for_track(db, store, track_id)
    db.execute(
        text(f"DELETE FROM {FTS_TABLE} WHERE track_id = :track_id"),
        {"track_id": track_id},
    )
    db.execute(
        text(
            f"INSERT INTO {FTS_TABLE} (track_id, title, artist, genres, lyrics)"
            " VALUES (:track_id, :title, :artist, :genres, :lyrics)"
        ),
        {
            "track_id": track_id,
            "title": track.title or "",
            "artist": track.artist or "",
            "genres": " ".join(genre_names),
            "lyrics": lyrics,
        },
    )
    db.flush()


def remove_track(db: Session, track_id: str) -> None:
    ensure_search_schema(db)
    db.execute(
        text(f"DELETE FROM {FTS_TABLE} WHERE track_id = :track_id"),
        {"track_id": track_id},
    )
    db.flush()
