from datetime import datetime, timezone

import pytest

from meridien_bulletin.time_windows import compute_window


def test_daily_window_is_last_24_hours() -> None:
    end = datetime(2026, 2, 19, 8, 0, tzinfo=timezone.utc)
    start, returned_end = compute_window("daily", end)
    assert returned_end == end
    assert (returned_end - start).total_seconds() == 24 * 60 * 60


def test_weekly_window_is_last_7_days() -> None:
    end = datetime(2026, 2, 20, 16, 0, tzinfo=timezone.utc)
    start, returned_end = compute_window("weekly", end)
    assert returned_end == end
    assert (returned_end - start).days == 7


def test_period_validation() -> None:
    end = datetime(2026, 2, 20, 16, 0, tzinfo=timezone.utc)
    with pytest.raises(ValueError):
        compute_window("monthly", end)
