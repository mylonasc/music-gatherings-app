"""Model persistence: optional metadata, multi-genre, versions, votes, lineage."""

import pytest
from sqlalchemy.exc import IntegrityError

from app.models import (
    AccessRequest,
    Artifact,
    ArtifactDerivation,
    AuditEvent,
    Crew,
    CrewMembership,
    CrewTrack,
    Genre,
    Job,
    ProcessingProfile,
    SourceRecord,
    Track,
    TrackGenre,
    TrackVersion,
    TrackVote,
    User,
)


def make_user(db_session, username="ada", **kwargs):  # type: ignore[no-untyped-def]
    user = User(username=username, password_hash="hash-" + username, **kwargs)
    db_session.add(user)
    db_session.flush()
    return user


def test_track_allows_missing_title_and_artist(db_session):  # type: ignore[no-untyped-def]
    track = Track(description="mystery song")
    db_session.add(track)
    db_session.flush()
    assert track.id
    assert track.title is None
    assert track.artist is None


def test_track_supports_multiple_genres_and_versions(db_session):  # type: ignore[no-untyped-def]
    track = Track(title="Blue Train", artist="John Coltrane")
    db_session.add(track)
    db_session.flush()
    for name in ("jazz", "hard bop"):
        genre = Genre(name=name)
        db_session.add(genre)
        db_session.flush()
        db_session.add(TrackGenre(track_id=track.id, genre_id=genre.id))
    db_session.add(TrackVersion(track_id=track.id, label="Studio", musical_key="Bbm"))
    db_session.add(TrackVersion(track_id=track.id, label="Live", capo=2))
    db_session.flush()
    assert db_session.query(TrackGenre).filter_by(track_id=track.id).count() == 2
    assert db_session.query(TrackVersion).filter_by(track_id=track.id).count() == 2


def test_username_and_vote_uniqueness(db_session):  # type: ignore[no-untyped-def]
    user = make_user(db_session)
    crew = Crew(name="Friday crew")
    db_session.add(crew)
    db_session.flush()
    db_session.add(CrewMembership(crew_id=crew.id, user_id=user.id))
    track = Track(title="Song")
    db_session.add(track)
    db_session.flush()
    crew_track = CrewTrack(crew_id=crew.id, track_id=track.id, added_by_id=user.id)
    db_session.add(crew_track)
    db_session.flush()
    db_session.add(TrackVote(crew_track_id=crew_track.id, user_id=user.id, value=1))
    db_session.flush()

    db_session.add(User(username="ada", password_hash="other"))
    with pytest.raises(IntegrityError):
        db_session.flush()
    db_session.rollback()

    db_session.add(TrackVote(crew_track_id=crew_track.id, user_id=user.id, value=-1))
    with pytest.raises(IntegrityError):
        db_session.flush()
    db_session.rollback()

    db_session.add(
        CrewTrack(crew_id=crew.id, track_id=track.id, added_by_id=user.id)
    )
    with pytest.raises(IntegrityError):
        db_session.flush()
    db_session.rollback()


def test_vote_value_check_constraint(db_session):  # type: ignore[no-untyped-def]
    user = make_user(db_session)
    crew = Crew(name="Crew")
    db_session.add(crew)
    db_session.flush()
    track = Track(title="Song")
    db_session.add(track)
    db_session.flush()
    crew_track = CrewTrack(crew_id=crew.id, track_id=track.id)
    db_session.add(crew_track)
    db_session.flush()
    db_session.add(TrackVote(crew_track_id=crew_track.id, user_id=user.id, value=0))
    with pytest.raises(IntegrityError):
        db_session.flush()
    db_session.rollback()


def test_piano_suitability_defaults_to_unknown(db_session):  # type: ignore[no-untyped-def]
    crew = Crew(name="Crew")
    track = Track(title="Song")
    db_session.add_all([crew, track])
    db_session.flush()
    crew_track = CrewTrack(crew_id=crew.id, track_id=track.id)
    db_session.add(crew_track)
    db_session.flush()
    assert crew_track.piano_suitability == "unknown"


def test_artifact_derivation_lineage(db_session):  # type: ignore[no-untyped-def]
    track = Track(title="Song")
    db_session.add(track)
    db_session.flush()
    version = TrackVersion(track_id=track.id, label="Studio")
    db_session.add(version)
    db_session.flush()
    source = SourceRecord(
        track_version_id=version.id,
        provider="genius",
        external_id="123",
        storage_permission="allowed",
    )
    db_session.add(source)
    db_session.flush()
    raw = Artifact(
        track_version_id=version.id,
        source_record_id=source.id,
        kind="lyrics",
        mime_type="text/plain",
        byte_size=42,
        sha256="ab" * 32,
        object_key="ab/" + "cd" * 16,
    )
    derived = Artifact(
        track_version_id=version.id,
        kind="rendered_lyrics",
        mime_type="text/html",
    )
    db_session.add_all([raw, derived])
    db_session.flush()
    derivation = ArtifactDerivation(
        output_artifact_id=derived.id,
        processor_name="processor",
        processor_version="0.1.0",
        profile={"schema_version": 1, "steps": []},
        input_artifact_ids=[raw.id],
        diagnostics={"warnings": []},
    )
    db_session.add(derivation)
    db_session.flush()
    assert derivation.input_artifact_ids == [raw.id]


def test_job_idempotency_and_profiles(db_session):  # type: ignore[no-untyped-def]
    db_session.add(Job(kind="online_search", payload={"q": "x"}))
    db_session.add(
        Job(kind="online_search", payload={"q": "y"}, idempotency_key="abc")
    )
    db_session.flush()
    db_session.add(
        Job(kind="online_search", payload={"q": "z"}, idempotency_key="abc")
    )
    with pytest.raises(IntegrityError):
        db_session.flush()
    db_session.rollback()
    db_session.add(ProcessingProfile(name="lyrics", version=1, config={"steps": []}))
    db_session.add(ProcessingProfile(name="lyrics", version=1, config={"steps": []}))
    with pytest.raises(IntegrityError):
        db_session.flush()
    db_session.rollback()


def test_access_request_and_audit_persist(db_session):  # type: ignore[no-untyped-def]
    admin = make_user(db_session, username="admin", is_admin=True)
    db_session.add(AccessRequest(username="newbie", message="let me in"))
    db_session.add(
        AuditEvent(actor_user_id=admin.id, action="access.approved", entity_type="user")
    )
    db_session.flush()
