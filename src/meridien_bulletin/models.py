from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone


@dataclass(slots=True)
class SlackMessage:
    channel_id: str
    channel_name: str
    ts: str
    text: str
    user_id: str
    user_display: str
    reply_count: int = 0
    reaction_count: int = 0
    permalink: str | None = None

    @property
    def ts_datetime(self) -> datetime:
        return datetime.fromtimestamp(float(self.ts), tz=timezone.utc)


@dataclass(slots=True)
class BulletinRecord:
    period: str
    window_start: datetime
    window_end: datetime
    dm_channel_id: str
    message_ts: str
    sent_at: datetime
    reaction_count: int | None = None
    reaction_names_csv: str | None = None


@dataclass(slots=True)
class SummaryResult:
    text: str
    source_messages: list[SlackMessage]
