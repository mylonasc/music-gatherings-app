"""Local search: FTS5 matching with prefix support plus typo-tolerant fallback.

Strategy, in order:
1. FTS5 `MATCH` over title/artist/genres/lyrics with per-term prefix search
   (`"term"*`), ranked by bm25, with snippets.
2. Typo-tolerant re-rank: RapidFuzz candidates over the visible tracks' titles
   and artists fill in when FTS returns few rows (misspellings FTS cannot match).

Work is bounded: FTS candidates are capped, and fuzzy matching runs over at
most ``MAX_FUZZY_POOL`` visible tracks with a minimum score cutoff.
"""

from dataclasses import dataclass, field

from rapidfuzz import fuzz, process
from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.api.v1.visibility import user_crew_ids
from app.models import CrewTrack, Track, User
from app.search.index import FTS_TABLE, ensure_search_schema

MAX_FTS_CANDIDATES = 50
MAX_FUZZY_POOL = 2000
FUZZY_MIN_SCORE = 70.0


@dataclass
class SearchHit:
    track_id: str
    title: str | None
    artist: str | None
    genres: list[str]
    snippet: str
    score: float
    source: str


@dataclass
class SearchResults:
    hits: list[SearchHit] = field(default_factory=list)
    total: int = 0


def _sanitize_terms(query: str) -> list[str]:
    terms: list[str] = []
    for raw in query.split():
        cleaned = "".join(ch for ch in raw if ch.isalnum() or ch in ("-", "'"))
        cleaned = cleaned.strip("-'")
        if cleaned:
            terms.append(cleaned.lower())
    return terms


def _fts_expression(terms: list[str]) -> str:
    return " AND ".join(f'"{term}"*' for term in terms)


def _visible_track_ids(db: Session, user: User) -> set[str]:
    if user.is_admin:
        rows = db.execute(select(Track.id)).all()
        return {row[0] for row in rows}
    crew_ids = user_crew_ids(db, user)
    if not crew_ids:
        return set()
    rows = db.execute(
        select(CrewTrack.track_id).where(CrewTrack.crew_id.in_(crew_ids))
    ).all()
    return {row[0] for row in rows}


def _genre_names(db: Session, track_id: str) -> list[str]:
    from app.api.v1.visibility import track_genre_names

    return track_genre_names(db, track_id)


def _track_map(db: Session, track_ids: set[str]) -> dict[str, Track]:
    if not track_ids:
        return {}
    rows = (
        db.execute(select(Track).where(Track.id.in_(sorted(track_ids))))
        .scalars()
        .all()
    )
    return {track.id: track for track in rows}


def search_tracks(
    db: Session,
    user: User,
    query: str,
    *,
    genre: str | None = None,
    piano_suggested: bool | None = None,
    limit: int = 20,
    offset: int = 0,
) -> SearchResults:
    from app.models import CrewTrack as _CrewTrack

    ensure_search_schema(db)
    terms = _sanitize_terms(query)
    if not terms:
        return SearchResults()
    visible = _visible_track_ids(db, user)
    if not visible:
        return SearchResults()
    tracks = _track_map(db, visible)

    hits: list[SearchHit] = []
    seen: set[str] = set()

    # Stage 1: FTS5 with prefix matching.
    expression = _fts_expression(terms)
    fts_rows = db.execute(
        text(
            f"SELECT track_id, bm25({FTS_TABLE}),"
            f" snippet({FTS_TABLE}, 1, '<b>', '</b>', '…', 12),"
            f" snippet({FTS_TABLE}, 2, '<b>', '</b>', '…', 12),"
            f" snippet({FTS_TABLE}, 4, '<b>', '</b>', '…', 16)"
            f" FROM {FTS_TABLE} WHERE {FTS_TABLE} MATCH :match"
            " ORDER BY bm25(track_search_fts) LIMIT :limit"
        ),
        {"match": expression, "limit": MAX_FTS_CANDIDATES},
    ).all()
    for track_id, rank, title_snip, artist_snip, lyrics_snip in fts_rows:
        if track_id not in visible or track_id in seen:
            continue
        track = tracks.get(track_id)
        if track is None:
            continue
        seen.add(track_id)
        snippet = title_snip or artist_snip or lyrics_snip or ""
        hits.append(
            SearchHit(
                track_id=track_id,
                title=track.title,
                artist=track.artist,
                genres=_genre_names(db, track_id),
                snippet=snippet,
                score=float(-rank),
                source="fts",
            )
        )

    # Stage 2: typo-tolerant title/artist fallback.
    if len(hits) < limit + offset:
        pool = sorted(visible - seen)
        if len(pool) > MAX_FUZZY_POOL:
            pool = pool[:MAX_FUZZY_POOL]
        choices = {
            track_id: f"{(tracks[track_id].title or '')} {(tracks[track_id].artist or '')}".strip()
            for track_id in pool
            if track_id in tracks
        }
        matches = process.extract(
            query,
            choices,
            scorer=fuzz.WRatio,
            score_cutoff=FUZZY_MIN_SCORE,
            limit=(limit + offset) * 2,
        )
        for _matched, score, track_id in matches:
            if track_id in seen:
                continue
            seen.add(track_id)
            track = tracks[track_id]
            label = f"{track.title or 'Untitled'} — {track.artist or 'Unknown artist'}"
            hits.append(
                SearchHit(
                    track_id=track_id,
                    title=track.title,
                    artist=track.artist,
                    genres=_genre_names(db, track_id),
                    snippet=label[:160],
                    score=float(score) / 100.0,
                    source="fuzzy",
                )
            )

    # Stage 3: genre / piano filters over the user's visible crew entries.
    if genre is not None or piano_suggested is not None:
        wanted = genre.strip().lower() if genre else None
        crew_ids = user_crew_ids(db, user) if not user.is_admin else None
        filtered: list[SearchHit] = []
        for hit in hits:
            if wanted and wanted not in {g.lower() for g in hit.genres}:
                continue
            if piano_suggested is not None:
                stmt = select(_CrewTrack.piano_suitability).where(
                    _CrewTrack.track_id == hit.track_id
                )
                if crew_ids is not None:
                    stmt = stmt.where(_CrewTrack.crew_id.in_(crew_ids))
                flags = [row[0] for row in db.execute(stmt).all()]
                if piano_suggested and "suggested" not in flags:
                    continue
                if not piano_suggested and flags and all(
                    f == "suggested" for f in flags
                ):
                    continue
            filtered.append(hit)
        hits = filtered

    total = len(hits)
    return SearchResults(hits=hits[offset : offset + limit], total=total)
