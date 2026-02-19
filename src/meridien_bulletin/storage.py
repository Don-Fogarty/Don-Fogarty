from __future__ import annotations

import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path

from .models import BulletinRecord


def _iso(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).isoformat()


def _parse_iso(value: str) -> datetime:
    return datetime.fromisoformat(value)


class BulletinStore:
    def __init__(self, db_path: Path) -> None:
        self.db_path = db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS bulletins (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    period TEXT NOT NULL,
                    window_start TEXT NOT NULL,
                    window_end TEXT NOT NULL,
                    sent_at TEXT NOT NULL,
                    dm_channel_id TEXT NOT NULL,
                    message_ts TEXT NOT NULL,
                    reaction_count INTEGER,
                    reaction_names_csv TEXT,
                    UNIQUE(dm_channel_id, message_ts)
                );
                """
            )
            conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_bulletins_sent_at
                ON bulletins(sent_at);
                """
            )

    def record_bulletin(
        self,
        *,
        period: str,
        window_start: datetime,
        window_end: datetime,
        dm_channel_id: str,
        message_ts: str,
        sent_at: datetime | None = None,
    ) -> None:
        sent_at = sent_at or datetime.now(tz=timezone.utc)
        with self._connect() as conn:
            conn.execute(
                """
                INSERT OR IGNORE INTO bulletins (
                    period, window_start, window_end, sent_at, dm_channel_id, message_ts
                ) VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    period,
                    _iso(window_start),
                    _iso(window_end),
                    _iso(sent_at),
                    dm_channel_id,
                    message_ts,
                ),
            )

    def recent_records(self, *, days: int = 30) -> list[BulletinRecord]:
        since = datetime.now(tz=timezone.utc) - timedelta(days=days)
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT period, window_start, window_end, sent_at, dm_channel_id, message_ts,
                       reaction_count, reaction_names_csv
                FROM bulletins
                WHERE sent_at >= ?
                ORDER BY sent_at DESC
                """,
                (_iso(since),),
            ).fetchall()

        return [
            BulletinRecord(
                period=row["period"],
                window_start=_parse_iso(row["window_start"]),
                window_end=_parse_iso(row["window_end"]),
                sent_at=_parse_iso(row["sent_at"]),
                dm_channel_id=row["dm_channel_id"],
                message_ts=row["message_ts"],
                reaction_count=row["reaction_count"],
                reaction_names_csv=row["reaction_names_csv"],
            )
            for row in rows
        ]

    def update_reactions(
        self,
        *,
        dm_channel_id: str,
        message_ts: str,
        reaction_count: int,
        reaction_names: list[str],
    ) -> None:
        names_csv = ",".join(sorted(reaction_names))
        with self._connect() as conn:
            conn.execute(
                """
                UPDATE bulletins
                SET reaction_count = ?, reaction_names_csv = ?
                WHERE dm_channel_id = ? AND message_ts = ?
                """,
                (reaction_count, names_csv, dm_channel_id, message_ts),
            )

    def reaction_metrics(self, *, days: int = 14) -> tuple[int, int]:
        since = datetime.now(tz=timezone.utc) - timedelta(days=days)
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT
                    COUNT(*) AS total,
                    COUNT(CASE WHEN reaction_count IS NOT NULL AND reaction_count > 0 THEN 1 END) AS reacted
                FROM bulletins
                WHERE sent_at >= ?
                """,
                (_iso(since),),
            ).fetchone()
        if row is None:
            return 0, 0
        return int(row["total"]), int(row["reacted"])
