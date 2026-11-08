from sqlalchemy import select

from app.models import AuditEvent, CrewTrack, Track, TrackVote
from tests.test_library import setup_two_users, suggest


def test_removal_capabilities_and_authorization(tmp_path, monkeypatch):
    app, admin, csrf, member, mcsrf, crew_id = setup_two_users(tmp_path, monkeypatch)
    admin_item = suggest(admin, crew_id, csrf, {"title": "Admin song"})
    own = suggest(member, crew_id, mcsrf, {"title": "Member song"})
    assert admin_item["can_remove"] and own["can_remove"]
    listed = member.get(f"/api/v1/crews/{crew_id}/tracks").json()["items"]
    permissions = {i["track_id"]: i["can_remove"] for i in listed}
    assert not permissions[admin_item["track_id"]] and permissions[own["track_id"]]
    detail = member.get(f"/api/v1/tracks/{admin_item['track_id']}").json()
    assert not detail["crew_entries"][0]["can_remove"]
    base = f"/api/v1/crews/{crew_id}/tracks"
    assert member.delete(f"{base}/{admin_item['crew_track_id']}",
                         headers={"X-CSRF-Token": mcsrf}).status_code == 403
    assert member.delete(f"{base}/{own['crew_track_id']}").status_code == 403
    assert member.delete(f"{base}/guessed-id",
                         headers={"X-CSRF-Token": mcsrf}).status_code == 404
    other = admin.post("/api/v1/crews", json={"name": "Other"},
                       headers={"X-CSRF-Token": csrf}).json()["id"]
    assert member.delete(f"/api/v1/crews/{other}/tracks/{own['crew_track_id']}",
                         headers={"X-CSRF-Token": mcsrf}).status_code == 404
    # An admin can remove another user's listing; permissions aren't just cosmetic.
    assert admin.delete(f"{base}/{own['crew_track_id']}",
                        headers={"X-CSRF-Token": csrf}).status_code == 204


def test_removing_own_listing_preserves_shared_music_and_hides_it_from_removed_crew(
    tmp_path, monkeypatch,
):
    app, admin, csrf, member, mcsrf, crew_id = setup_two_users(tmp_path, monkeypatch)
    own = suggest(member, crew_id, mcsrf, {
        "title": "Shared music", "versions": [{"label": "Original"}],
    })
    track_id, entry_id = own["track_id"], own["crew_track_id"]
    version = member.get(f"/api/v1/tracks/{track_id}").json()["versions"][0]["id"]
    artifact = member.post(
        f"/api/v1/tracks/{track_id}/versions/{version}/artifacts/upload",
        files={"file": ("lyrics.txt", b"Original shared fixture lyric", "text/plain")},
        data={"kind": "lyrics"}, headers={"X-CSRF-Token": mcsrf},
    ).json()["id"]
    other = admin.post("/api/v1/crews", json={"name": "Private"},
                       headers={"X-CSRF-Token": csrf}).json()["id"]
    with app.state.session_factory() as db:
        db.add(CrewTrack(crew_id=other, track_id=track_id))
        db.commit()
    member.put(f"/api/v1/crews/{crew_id}/tracks/{entry_id}/vote", json={"value": 1},
               headers={"X-CSRF-Token": mcsrf})
    removed = member.delete(f"/api/v1/crews/{crew_id}/tracks/{entry_id}",
                            headers={"X-CSRF-Token": mcsrf})
    assert removed.status_code == 204
    assert member.get(f"/api/v1/tracks/{track_id}").status_code == 404
    assert member.get(f"/api/v1/artifacts/{artifact}/content").status_code == 404
    assert member.get("/api/v1/search/local", params={"q": "fixture lyric"}).json()["total"] == 0
    assert admin.get(f"/api/v1/artifacts/{artifact}/content").status_code == 200
    assert admin.get(f"/api/v1/crews/{other}/tracks").json()["total"] == 1
    with app.state.session_factory() as db:
        assert db.get(Track, track_id) is not None
        assert not db.scalars(select(TrackVote).where(TrackVote.crew_track_id == entry_id)).all()
        assert db.scalars(select(AuditEvent).where(AuditEvent.action == "track.unlisted")).one()
