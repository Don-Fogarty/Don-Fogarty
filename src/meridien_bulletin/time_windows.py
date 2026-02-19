from __future__ import annotations

from datetime import datetime, timedelta


def compute_window(period: str, window_end: datetime) -> tuple[datetime, datetime]:
    if window_end.tzinfo is None:
        raise ValueError("window_end must be timezone aware")

    period_lower = period.lower().strip()
    if period_lower == "daily":
        return window_end - timedelta(hours=24), window_end
    if period_lower == "weekly":
        return window_end - timedelta(days=7), window_end
    raise ValueError(f"Unsupported period '{period}'. Expected 'daily' or 'weekly'.")
