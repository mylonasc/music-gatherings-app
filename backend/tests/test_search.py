"""S05 search tests: FTS prefix/matching, fuzzy fallback, scoping, consistency."""

import io
import time

from app.search.index import remove_track
from tests.test_library import setup_two_users, suggest


def search(client, q, **params):  # type: ignore[no-untyped-def]
    response = client.get("/api/v1/search/local", params={"q": q, **params})
    assert response.status_code == 200, response.text
    return response.json()


def test_prefix_and_lyrics_search(tmp_path, monkeypatch):  # type: ignore[no-untyped-def]
    _app, admin_client, csrf, _m, _mc, crew_id = setup_two_users(tmp_path, monkeypatch)
    item = suggest(
        admin_client,
        crew_id,
        csrf,
        {"title": "Blue Train", "artist": "John Coltrane", "genres": ["Jazz"]},
    )
    # Prefix matching on title and artist.
    assert search(admin_client, "blue")["total"] == 1
    assert search(admin_client, "coltr")["total"] == 1
    assert search(admin_client, "blue train")["total"] == 1
    assert search(admin_client, "miles davis")["total"] == 0

    # Lyrics become searchable after a lyrics upload.
    version_id = admin_client.post(
        f"/api/v1/tracks/{item['track_id']}/versions",
        json={"label": "Studio"},
        headers={"X-CSRF-Token": csrf},
    ).json()["id"]
    admin_client.post(
        f"/api/v1/tracks/{item['track_id']}/versions/{version_id}/artifacts/upload",
        files={"file": ("l.txt", io.BytesIO(b"row row row your boat"), "text/plain")},
        data={"kind": "lyrics"},
        headers={"X-CSRF-Token": csrf},
    )
    lyrics_hit = search(admin_client, "row your boat")
    assert lyrics_hit["total"] == 1
    assert lyrics_hit["items"][0]["track_id"] == item["track_id"]


def test_misspelled_queries_find_tracks(tmp_path, monkeypatch):  # type: ignore[no-untyped-def]
    _app, admin_client, csrf, _m, _mc, crew_id = setup_two_users(tmp_path, monkeypatch)
    item = suggest(
        admin_client, crew_id, csrf, {"title": "Blue Train", "artist": "John Coltrane"}
    )
    # FTS alone cannot match these; the fuzzy stage must.
    assert search(admin_client, "Blue Tran")["total"] == 1
    found = search(admin_client, "Coltrene")
    assert found["total"] == 1
    assert found["items"][0]["track_id"] == item["track_id"]
    assert found["items"][0]["source"] == "fuzzy"


def test_unauthorized_tracks_and_snippets_never_leak(tmp_path, monkeypatch):  # type: ignore[no-untyped-def]
    _app, admin_client, csrf, member_client, _mc, _crew = setup_two_users(
        tmp_path, monkeypatch
    )
    other_crew_id = admin_client.post(
        "/api/v1/crews", json={"name": "Other"}, headers={"X-CSRF-Token": csrf}
    ).json()["id"]
    hidden = suggest(
        admin_client,
        other_crew_id,
        csrf,
        {"title": "Secret Song", "artist": "Hidden Band"},
    )
    # Member of the default crew must not see it via any query form.
    for query in ("secret", "hidden band", "Secreet Song"):
        assert search(member_client, query)["total"] == 0
    # Admin sees it.
    assert search(admin_client, "secret")["total"] == 1
    assert hidden["track_id"]


def test_edit_updates_index_without_duplicates(tmp_path, monkeypatch):  # type: ignore[no-untyped-def]
    _app, admin_client, csrf, _m, _mc, crew_id = setup_two_users(tmp_path, monkeypatch)
    item = suggest(admin_client, crew_id, csrf, {"title": "Old Title"})
    assert search(admin_client, "old title")["total"] == 1
    admin_client.patch(
        f"/api/v1/tracks/{item['track_id']}",
        json={"title": "New Title"},
        headers={"X-CSRF-Token": csrf},
    )
    assert search(admin_client, "new title")["total"] == 1
    assert search(admin_client, "old title")["total"] == 0


def test_unlisted_track_invisible_to_former_member(tmp_path, monkeypatch):  # type: ignore[no-untyped-def]
    _app, admin_client, csrf, member_client, mcsrf, crew_id = setup_two_users(
        tmp_path, monkeypatch
    )
    item = suggest(member_client, crew_id, mcsrf, {"title": "Friday Jam"})
    assert search(admin_client, "friday jam")["total"] == 1
    removed = member_client.delete(
        f"/api/v1/crews/{crew_id}/tracks/{item['crew_track_id']}",
        headers={"X-CSRF-Token": mcsrf},
    )
    assert removed.status_code == 204
    assert search(member_client, "friday jam")["total"] == 0
    # Admin (sees all crews) still finds the orphaned track row.
    assert search(admin_client, "friday jam")["total"] == 1


def test_remove_track_clears_index(tmp_path, monkeypatch):  # type: ignore[no-untyped-def]
    from app.models import Track

    app, admin_client, csrf, _m, _mc, crew_id = setup_two_users(tmp_path, monkeypatch)
    item = suggest(admin_client, crew_id, csrf, {"title": "Ephemeral"})
    assert search(admin_client, "ephemeral")["total"] == 1
    factory = app.state.session_factory
    with factory() as db:
        track = db.get(Track, item["track_id"])
        assert track is not None
        db.delete(track)
        db.flush()
        remove_track(db, item["track_id"])
        db.commit()
    assert search(admin_client, "ephemeral")["total"] == 0


def test_genre_and_piano_filters(tmp_path, monkeypatch):  # type: ignore[no-untyped-def]
    _app, admin_client, csrf, _m, _mc, crew_id = setup_two_users(tmp_path, monkeypatch)
    suggest(
        admin_client,
        crew_id,
        csrf,
        {"title": "Rock Anthem", "genres": ["Rock"], "piano_suitability": "unknown"},
    )
    suggest(
        admin_client,
        crew_id,
        csrf,
        {"title": "Rock Ballad", "genres": ["Rock"], "piano_suitability": "suggested"},
    )
    assert search(admin_client, "rock", genre="rock")["total"] == 2
    assert search(admin_client, "rock", genre="jazz")["total"] == 0
    piano = search(admin_client, "rock", piano_suggested="true")
    assert piano["total"] == 1
    assert piano["items"][0]["title"] == "Rock Ballad"


def test_representative_query_performance(tmp_path, monkeypatch):  # type: ignore[no-untyped-def]
    _app, admin_client, csrf, _m, _mc, crew_id = setup_two_users(tmp_path, monkeypatch)
    for index in range(300):
        suggest(
            admin_client,
            crew_id,
            csrf,
            {"title": f"Rehearsal Song {index:03d}", "artist": f"Band {index % 17}"},
        )
    suggest(
        admin_client, crew_id, csrf, {"title": "Blue Train", "artist": "John Coltrane"}
    )
    started = time.monotonic()
    found = search(admin_client, "Coltrene")
    elapsed = time.monotonic() - started
    assert found["total"] == 1
    assert elapsed < 5.0


def test_fts_special_characters_do_not_break_search(tmp_path, monkeypatch):  # type: ignore[no-untyped-def]
    _app, admin_client, csrf, _m, _mc, crew_id = setup_two_users(tmp_path, monkeypatch)
    suggest(admin_client, crew_id, csrf, {"title": "Blue Train"})
    # Quotes, parens, colons, and stars are stripped, never executed as FTS syntax.
    assert search(admin_client, '"blue" (train):*')["total"] == 1
    assert search(admin_client, "!!!")["total"] == 0
