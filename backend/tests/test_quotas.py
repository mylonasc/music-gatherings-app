"""Per-user quota tracker: bounded sliding windows, no cross-user leakage."""

import pytest

from app.core.quotas import QuotaExceeded, UserQuotaTracker


class FakeClock:
    def __init__(self) -> None:
        self.now = 5000.0

    def clock(self) -> float:
        return self.now


def test_quota_allows_then_rejects() -> None:
    clock = FakeClock()
    tracker = UserQuotaTracker(clock=clock.clock)
    tracker.check(scope="online_search", user_id="u1", max_attempts=2, window_seconds=60.0)
    tracker.check(scope="online_search", user_id="u1", max_attempts=2, window_seconds=60.0)
    with pytest.raises(QuotaExceeded):
        tracker.check(scope="online_search", user_id="u1", max_attempts=2, window_seconds=60.0)


def test_quotas_are_per_user_and_per_scope() -> None:
    clock = FakeClock()
    tracker = UserQuotaTracker(clock=clock.clock)
    tracker.check(scope="online_search", user_id="u1", max_attempts=1, window_seconds=60.0)
    # Another user and another scope are unaffected.
    tracker.check(scope="online_search", user_id="u2", max_attempts=1, window_seconds=60.0)
    tracker.check(scope="online_import", user_id="u1", max_attempts=1, window_seconds=60.0)
    assert tracker.usage(scope="online_search", user_id="u1", window_seconds=60.0) == 1
    assert tracker.usage(scope="online_search", user_id="u2", window_seconds=60.0) == 1


def test_quota_window_slides() -> None:
    clock = FakeClock()
    tracker = UserQuotaTracker(clock=clock.clock)
    tracker.check(scope="s", user_id="u", max_attempts=1, window_seconds=60.0)
    with pytest.raises(QuotaExceeded):
        tracker.check(scope="s", user_id="u", max_attempts=1, window_seconds=60.0)
    clock.now += 61.0
    tracker.check(scope="s", user_id="u", max_attempts=1, window_seconds=60.0)
