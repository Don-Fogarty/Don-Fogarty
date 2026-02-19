from __future__ import annotations

from datetime import datetime, timezone
from zoneinfo import ZoneInfo

from .config import Settings
from .models import SummaryResult
from .slack_client import SlackDataClient
from .storage import BulletinStore
from .summarizer import BulletinSummarizer
from .time_windows import compute_window


def _truncate(value: str, max_chars: int) -> str:
    if len(value) <= max_chars:
        return value
    return value[: max_chars - 1].rstrip() + "…"


class BulletinService:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.local_tz = ZoneInfo(settings.timezone_name)
        self.slack = SlackDataClient(token=settings.slack_bot_token)
        self.store = BulletinStore(db_path=settings.db_path)
        self.summarizer = BulletinSummarizer(
            openai_api_key=settings.openai_api_key,
            openai_model=settings.openai_model,
            openai_base_url=settings.openai_base_url,
        )

    def run(self, *, period: str, dry_run: bool = False, now: datetime | None = None) -> str:
        period = period.lower().strip()
        if period not in {"daily", "weekly"}:
            raise ValueError("period must be either 'daily' or 'weekly'.")

        window_end = (now or datetime.now(tz=timezone.utc)).astimezone(timezone.utc)
        window_start, window_end = compute_window(period, window_end)

        channels = self.slack.resolve_public_channels(self.settings.slack_channels)
        messages = self.slack.fetch_messages(
            channels,
            oldest=window_start,
            latest=window_end,
            max_messages_per_channel=self.settings.max_messages_per_channel,
        )
        summary = self.summarizer.summarize(
            period=period,
            window_start=window_start,
            window_end=window_end,
            messages=messages,
            source_limit=self.settings.max_source_links,
        )
        bulletin_text = self._format_message(
            period=period,
            window_start=window_start,
            window_end=window_end,
            summary=summary,
        )

        if dry_run:
            return bulletin_text

        dm_channel_id, message_ts = self.slack.open_dm_and_send(
            user_id=self.settings.slack_target_user_id,
            text=bulletin_text,
        )
        self.store.record_bulletin(
            period=period,
            window_start=window_start,
            window_end=window_end,
            dm_channel_id=dm_channel_id,
            message_ts=message_ts,
        )
        return f"Sent {period} bulletin to {self.settings.slack_target_user_id} at ts={message_ts}"

    def refresh_reaction_metrics(self, *, days: int = 14) -> tuple[int, int, float]:
        records = self.store.recent_records(days=days)
        for record in records:
            count, names = self.slack.get_message_reactions(
                channel_id=record.dm_channel_id,
                message_ts=record.message_ts,
            )
            self.store.update_reactions(
                dm_channel_id=record.dm_channel_id,
                message_ts=record.message_ts,
                reaction_count=count,
                reaction_names=names,
            )

        total, reacted = self.store.reaction_metrics(days=days)
        rate = (reacted / total) if total else 0.0
        return total, reacted, rate

    def _format_message(
        self,
        *,
        period: str,
        window_start: datetime,
        window_end: datetime,
        summary: SummaryResult,
    ) -> str:
        title = ":newspaper: *Daily bulletin*" if period == "daily" else ":newspaper: *Weekly bulletin*"
        start_local = window_start.astimezone(self.local_tz)
        end_local = window_end.astimezone(self.local_tz)
        coverage = (
            f"_Coverage: {start_local.strftime('%a %d %b %H:%M')} → "
            f"{end_local.strftime('%a %d %b %H:%M')} {self.settings.timezone_name}_"
        )
        sources = self._format_sources(summary)
        return (
            f"{title}\n"
            f"{coverage}\n\n"
            f"{summary.text.strip()}\n\n"
            f"{sources}\n\n"
            "React with :white_check_mark: if this was useful."
        )

    def _format_sources(self, summary: SummaryResult) -> str:
        if not summary.source_messages:
            return "*Sources*\n• No source links available."

        lines: list[str] = []
        for msg in summary.source_messages:
            permalink = self.slack.get_message_permalink(channel_id=msg.channel_id, message_ts=msg.ts)
            if not permalink:
                continue
            snippet = _truncate(msg.text, 80)
            lines.append(f"• <{permalink}|{msg.channel_name}> — {snippet}")

        if not lines:
            return "*Sources*\n• No source links available."
        return "*Sources*\n" + "\n".join(lines)
