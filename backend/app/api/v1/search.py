"""Local library search (FTS5 + typo-tolerant fallback)."""

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
from app.models import User
from app.search.query import search_tracks

router = APIRouter()


class SearchHitOut(BaseModel):
    track_id: str
    title: str | None
    artist: str | None
    genres: list[str] = Field(default_factory=list)
    snippet: str = ""
    score: float = 0.0
    source: str = ""


class SearchResponse(BaseModel):
    items: list[SearchHitOut] = Field(default_factory=list)
    total: int = 0
    limit: int = 20
    offset: int = 0


@router.get("/search/local", response_model=SearchResponse)
def search_local(
    q: str = Query(min_length=1, max_length=200),
    genre: str | None = Query(default=None, max_length=64),
    piano_suggested: bool | None = Query(default=None),
    limit: int = Query(default=20, ge=1, le=50),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> SearchResponse:
    results = search_tracks(
        db, user, q, genre=genre, piano_suggested=piano_suggested, limit=limit, offset=offset
    )
    return SearchResponse(
        items=[
            SearchHitOut(
                track_id=hit.track_id,
                title=hit.title,
                artist=hit.artist,
                genres=hit.genres,
                snippet=hit.snippet,
                score=hit.score,
                source=hit.source,
            )
            for hit in results.hits
        ],
        total=results.total,
        limit=limit,
        offset=offset,
    )
