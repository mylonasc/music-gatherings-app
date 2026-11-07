"""S04 library tests: suggest/list/edit tracks, versions, votes, artifacts."""

import io

from fastapi.testclient import TestClient

from tests.conftest import make_test_app
from tests.test_auth import login, seed_admin


def suggest(client, crew_id, csrf, body):  # type: ignore[no-untyped-def]
    response = client.post(
        f"/api/v1/crews/{crew_id}/tracks", json=body, headers={"X-CSRF-Token": csrf}
    )
    assert response.status_code == 201, response.text
    return response.json()


def setup_two_users(tmp_path, monkeypatch, **env):  # type: ignore[no-untyped-def]
    """Admin client + approved member client sharing one app."""
    app, admin_client = make_test_app(tmp_path, monkeypatch, **env)
    _admin_id, crew_id = seed_admin(app)
    csrf = login(admin_client, "admin", "admin-pass-1")
    created = admin_client.post(
        "/api/v1/access-requests", json={"username": "mem", "password": "s3cret-long"}
    )
    admin_client.post(
        f"/api/v1/access-requests/{created.json()['id']}/approve",
        headers={"X-CSRF-Token": csrf},
    )
    member_client = TestClient(app)
    member_csrf = login(member_client, "mem", "s3cret-long")
    return app, admin_client, csrf, member_client, member_csrf, crew_id


def test_suggest_list_and_detail(tmp_path, monkeypatch):  # type: ignore[no-untyped-def]
    app, admin_client, csrf, member_client, _mcsrf, crew_id = setup_two_users(
        tmp_path, monkeypatch
    )
    item = suggest(
        member_client,
        crew_id,
        login(member_client, "mem", "s3cret-long") or "",
        {
            "artist": "Alice Coltrane",
            "description": "spiritual jazz",
            "genres": ["Jazz", "spiritual jazz", "jazz"],
            "versions": [{"label": "Studio", "musical_key": "C"}],
            "notes": "for friday",
            "piano_suitability": "suggested",
        },
    )
    assert item["title"] is None
    assert item["artist"] == "Alice Coltrane"
    assert sorted(item["genres"]) == ["Jazz", "spiritual jazz"]
    assert item["requester"] == "mem"
    assert item["vote_score"] == 0
    assert item["my_vote"] is None
    assert item["version_count"] == 1

    listed = admin_client.get(f"/api/v1/crews/{crew_id}/tracks")
    assert listed.status_code == 200
    body = listed.json()
    assert body["total"] == 1
    assert body["items"][0]["crew_track_id"] == item["crew_track_id"]

    detail = member_client.get(f"/api/v1/tracks/{item['track_id']}")
    assert detail.status_code == 200
    detail_body = detail.json()
    assert detail_body["description"] == "spiritual jazz"
    assert len(detail_body["versions"]) == 1
    assert detail_body["versions"][0]["artifacts"] == []
    assert detail_body["crew_entries"][0]["piano_suitability"] == "suggested"


def test_genre_and_piano_filters_and_pagination(tmp_path, monkeypatch):  # type: ignore[no-untyped-def]
    _app, admin_client, csrf, _m, _mc, crew_id = setup_two_users(tmp_path, monkeypatch)
    for title, genres, piano in [
        ("A", ["Rock"], "unknown"),
        ("B", ["Rock"], "suggested"),
        ("C", ["Jazz"], "suggested"),
    ]:
        suggest(
            admin_client,
            crew_id,
            csrf,
            {"title": title, "genres": genres, "piano_suitability": piano},
        )
    rock = admin_client.get(f"/api/v1/crews/{crew_id}/tracks", params={"genre": "rock"})
    assert rock.json()["total"] == 2
    piano = admin_client.get(
        f"/api/v1/crews/{crew_id}/tracks", params={"piano_suggested": "true"}
    )
    assert piano.json()["total"] == 2
    page = admin_client.get(
        f"/api/v1/crews/{crew_id}/tracks", params={"limit": 2, "offset": 0}
    )
    assert page.json()["total"] == 3
    assert len(page.json()["items"]) == 2
    page2 = admin_client.get(
        f"/api/v1/crews/{crew_id}/tracks", params={"limit": 2, "offset": 2}
    )
    assert len(page2.json()["items"]) == 1


def test_votes_upsert_and_clear(tmp_path, monkeypatch):  # type: ignore[no-untyped-def]
    _app, admin_client, csrf, member_client, mcsrf, crew_id = setup_two_users(
        tmp_path, monkeypatch
    )
    item = suggest(admin_client, crew_id, csrf, {"title": "Vote me"})
    ct_id = item["crew_track_id"]

    up = member_client.put(
        f"/api/v1/crews/{crew_id}/tracks/{ct_id}/vote",
        json={"value": 1},
        headers={"X-CSRF-Token": mcsrf},
    )
    assert up.json()["vote_score"] == 1
    assert up.json()["my_vote"] == 1
    # voting again with the same value keeps a single row
    again = member_client.put(
        f"/api/v1/crews/{crew_id}/tracks/{ct_id}/vote",
        json={"value": 1},
        headers={"X-CSRF-Token": mcsrf},
    )
    assert again.json()["vote_score"] == 1
    down = member_client.put(
        f"/api/v1/crews/{crew_id}/tracks/{ct_id}/vote",
        json={"value": -1},
        headers={"X-CSRF-Token": mcsrf},
    )
    assert down.json()["vote_score"] == -1
    bad = member_client.put(
        f"/api/v1/crews/{crew_id}/tracks/{ct_id}/vote",
        json={"value": 5},
        headers={"X-CSRF-Token": mcsrf},
    )
    assert bad.status_code == 422
    cleared = member_client.delete(
        f"/api/v1/crews/{crew_id}/tracks/{ct_id}/vote",
        headers={"X-CSRF-Token": mcsrf},
    )
    assert cleared.status_code == 204
    detail = member_client.get(f"/api/v1/tracks/{item['track_id']}")
    assert detail.json()["crew_entries"][0]["vote_score"] == 0


def test_cross_crew_denied(tmp_path, monkeypatch):  # type: ignore[no-untyped-def]
    from fastapi.testclient import TestClient

    app, admin_client, csrf, member_client, mcsrf, crew_id = setup_two_users(
        tmp_path, monkeypatch
    )
    # A second crew; 'mem' belongs only to the default crew.
    other_crew = admin_client.post(
        "/api/v1/crews", json={"name": "Other"}, headers={"X-CSRF-Token": csrf}
    ).json()
    other_crew_id = other_crew["id"]
    item = suggest(admin_client, other_crew_id, csrf, {"title": "Private"})

    # Member of the default crew shares no crew with the track: all 404, never leaks.
    assert member_client.get(f"/api/v1/tracks/{item['track_id']}").status_code == 404
    assert member_client.get(f"/api/v1/crews/{other_crew_id}/tracks").status_code == 404
    assert (
        member_client.put(
            f"/api/v1/crews/{other_crew_id}/tracks/{item['crew_track_id']}/vote",
            json={"value": 1},
            headers={"X-CSRF-Token": mcsrf},
        ).status_code
        == 404
    )
    assert (
        member_client.post(
            f"/api/v1/tracks/{item['track_id']}/versions",
            json={"label": "X"},
            headers={"X-CSRF-Token": mcsrf},
        ).status_code
        == 404
    )
    # Unauthenticated is 401.
    anon = TestClient(app)
    assert anon.get(f"/api/v1/tracks/{item['track_id']}").status_code == 401


def test_track_edit_and_version_add(tmp_path, monkeypatch):  # type: ignore[no-untyped-def]
    _app, admin_client, csrf, _m, _mc, crew_id = setup_two_users(tmp_path, monkeypatch)
    item = suggest(admin_client, crew_id, csrf, {"title": "Old", "genres": ["Rock"]})
    patched = admin_client.patch(
        f"/api/v1/tracks/{item['track_id']}",
        json={"title": "New", "genres": ["Jazz"]},
        headers={"X-CSRF-Token": csrf},
    )
    assert patched.status_code == 200, patched.text
    assert patched.json()["title"] == "New"
    assert patched.json()["genres"] == ["Jazz"]
    version = admin_client.post(
        f"/api/v1/tracks/{item['track_id']}/versions",
        json={"label": "Live", "capo": 2},
        headers={"X-CSRF-Token": csrf},
    )
    assert version.status_code == 201
    versions = admin_client.get(f"/api/v1/tracks/{item['track_id']}/versions")
    assert len(versions.json()) == 1

    entry_patch = admin_client.patch(
        f"/api/v1/crews/{crew_id}/tracks/{item['crew_track_id']}",
        json={"notes": "updated", "piano_suitability": "not_suggested"},
        headers={"X-CSRF-Token": csrf},
    )
    assert entry_patch.status_code == 200
    bad_piano = admin_client.patch(
        f"/api/v1/crews/{crew_id}/tracks/{item['crew_track_id']}",
        json={"piano_suitability": "maybe"},
        headers={"X-CSRF-Token": csrf},
    )
    assert bad_piano.status_code == 422


def test_upload_reference_and_serving(tmp_path, monkeypatch):  # type: ignore[no-untyped-def]
    _app, admin_client, csrf, _m, _mc, crew_id = setup_two_users(tmp_path, monkeypatch)
    item = suggest(admin_client, crew_id, csrf, {"title": "Sheets"})
    version_id = admin_client.post(
        f"/api/v1/tracks/{item['track_id']}/versions",
        json={"label": "Studio"},
        headers={"X-CSRF-Token": csrf},
    ).json()["id"]

    lyrics = b"row row row your boat\n"
    uploaded = admin_client.post(
        f"/api/v1/tracks/{item['track_id']}/versions/{version_id}/artifacts/upload",
        files={"file": ("lyrics.txt", io.BytesIO(lyrics), "text/plain")},
        data={"kind": "lyrics"},
        headers={"X-CSRF-Token": csrf},
    )
    assert uploaded.status_code == 201, uploaded.text
    meta = uploaded.json()
    assert meta["mime_type"] == "text/plain"
    assert meta["byte_size"] == len(lyrics)
    assert meta["is_external"] is False

    fetched = admin_client.get(f"/api/v1/artifacts/{meta['id']}")
    assert fetched.status_code == 200
    content = admin_client.get(f"/api/v1/artifacts/{meta['id']}/content")
    assert content.status_code == 200
    assert content.content == lyrics
    assert content.headers["content-disposition"].startswith("attachment")
    assert content.headers["x-content-type-options"] == "nosniff"

    bad_kind = admin_client.post(
        f"/api/v1/tracks/{item['track_id']}/versions/{version_id}/artifacts/upload",
        files={"file": ("run.exe", io.BytesIO(b"MZ"), "application/octet-stream")},
        data={"kind": "lyrics"},
        headers={"X-CSRF-Token": csrf},
    )
    assert bad_kind.status_code == 422

    ref = admin_client.post(
        f"/api/v1/tracks/{item['track_id']}/versions/{version_id}/artifacts/reference",
        json={"kind": "sheet_music", "external_url": "https://example.com/score.pdf"},
        headers={"X-CSRF-Token": csrf},
    )
    assert ref.status_code == 201
    assert ref.json()["is_external"] is True
    no_content = admin_client.get(f"/api/v1/artifacts/{ref.json()['id']}/content")
    assert no_content.status_code == 404

    detail = admin_client.get(f"/api/v1/tracks/{item['track_id']}")
    kinds = {
        a["kind"]
        for v in detail.json()["versions"]
        for a in v["artifacts"]
    }
    assert kinds == {"lyrics", "sheet_music"}


def test_artifact_cross_crew_hidden(tmp_path, monkeypatch):  # type: ignore[no-untyped-def]
    _app, admin_client, csrf, member_client, _mcsrf, crew_id = setup_two_users(
        tmp_path, monkeypatch
    )
    # Track lives only in a second crew that 'mem' does not belong to.
    other_crew_id = admin_client.post(
        "/api/v1/crews", json={"name": "Other"}, headers={"X-CSRF-Token": csrf}
    ).json()["id"]
    item = suggest(admin_client, other_crew_id, csrf, {"title": "Hidden sheets"})
    version_id = admin_client.post(
        f"/api/v1/tracks/{item['track_id']}/versions",
        json={"label": "Studio"},
        headers={"X-CSRF-Token": csrf},
    ).json()["id"]
    uploaded = admin_client.post(
        f"/api/v1/tracks/{item['track_id']}/versions/{version_id}/artifacts/upload",
        files={"file": ("a.txt", io.BytesIO(b"secret"), "text/plain")},
        data={"kind": "lyrics"},
        headers={"X-CSRF-Token": csrf},
    )
    artifact_id = uploaded.json()["id"]

    assert member_client.get(f"/api/v1/artifacts/{artifact_id}").status_code == 404
    assert member_client.get(f"/api/v1/artifacts/{artifact_id}/content").status_code == 404


def test_upload_size_limit(tmp_path, monkeypatch):  # type: ignore[no-untyped-def]
    _app, admin_client, csrf, _m, _mc, crew_id = setup_two_users(
        tmp_path,
        monkeypatch,
        MUSIC_GATHERINGS_MAX_OBJECT_BYTES="10",
    )
    item = suggest(admin_client, crew_id, csrf, {"title": "Big"})
    version_id = admin_client.post(
        f"/api/v1/tracks/{item['track_id']}/versions",
        json={"label": "Studio"},
        headers={"X-CSRF-Token": csrf},
    ).json()["id"]
    too_big = admin_client.post(
        f"/api/v1/tracks/{item['track_id']}/versions/{version_id}/artifacts/upload",
        files={"file": ("a.txt", io.BytesIO(b"x" * 11), "text/plain")},
        data={"kind": "lyrics"},
        headers={"X-CSRF-Token": csrf},
    )
    assert too_big.status_code == 413
