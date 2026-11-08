from tests.test_library import setup_two_users, suggest


def test_positive_reactions_are_per_user_and_ignore_legacy_downvotes(tmp_path, monkeypatch):
    app, admin, csrf, member, mcsrf, crew_id = setup_two_users(tmp_path, monkeypatch)
    item = suggest(member, crew_id, mcsrf, {"title": "Thumbs fixture"})
    path = f"/api/v1/crews/{crew_id}/tracks/{item['crew_track_id']}/vote"
    assert item["upvote_count"] == 0
    admin.put(path, json={"value": -1}, headers={"X-CSRF-Token": csrf})
    one = member.put(path, json={"value": 1}, headers={"X-CSRF-Token": mcsrf}).json()
    assert one["upvote_count"] == 1 and one["vote_score"] == 0 and one["my_vote"] == 1
    again = member.put(path, json={"value": 1}, headers={"X-CSRF-Token": mcsrf}).json()
    assert again["upvote_count"] == 1
    two = admin.put(path, json={"value": 1}, headers={"X-CSRF-Token": csrf}).json()
    assert two["upvote_count"] == 2
    member.delete(path, headers={"X-CSRF-Token": mcsrf})
    listed = member.get(f"/api/v1/crews/{crew_id}/tracks").json()["items"][0]
    assert listed["upvote_count"] == 1 and listed["my_vote"] is None
    detail = admin.get(f"/api/v1/tracks/{item['track_id']}").json()["crew_entries"][0]
    assert detail["upvote_count"] == 1 and detail["my_vote"] == 1
