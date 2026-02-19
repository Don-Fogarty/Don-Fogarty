from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv


def _env_int(name: str, default: int) -> int:
    raw = os.getenv(name)
    if raw is None:
        return default
    return int(raw.strip())


def _env_channels(name: str, default: str) -> list[str]:
    raw = os.getenv(name, default)
    return [item.strip() for item in raw.split(",") if item.strip()]


@dataclass(slots=True)
class Settings:
    slack_bot_token: str
    slack_target_user_id: str
    slack_channels: list[str]
    timezone_name: str
    daily_hour: int
    daily_minute: int
    weekly_day_of_week: str
    weekly_hour: int
    weekly_minute: int
    max_messages_per_channel: int
    max_source_links: int
    openai_api_key: str | None
    openai_model: str
    openai_base_url: str | None
    db_path: Path

    @classmethod
    def from_env(cls) -> "Settings":
        load_dotenv()
        bot_token = os.getenv("SLACK_BOT_TOKEN", "").strip()
        target_user_id = os.getenv("SLACK_TARGET_USER_ID", "").strip()
        if not bot_token:
            raise ValueError("Missing required env var SLACK_BOT_TOKEN")
        if not target_user_id:
            raise ValueError("Missing required env var SLACK_TARGET_USER_ID")

        channels = _env_channels(
            "SLACK_CHANNELS",
            "#sales,#product,#marketing-growth,#marketing-brand,#customer-success,#customer-support,#shipped",
        )
        if not channels:
            raise ValueError("SLACK_CHANNELS must include at least one channel.")

        db_path = Path(os.getenv("DATABASE_PATH", ".data/bulletins.db")).expanduser()

        return cls(
            slack_bot_token=bot_token,
            slack_target_user_id=target_user_id,
            slack_channels=channels,
            timezone_name=os.getenv("TIMEZONE", "Etc/GMT").strip(),
            daily_hour=_env_int("DAILY_HOUR_GMT", 8),
            daily_minute=_env_int("DAILY_MINUTE_GMT", 0),
            weekly_day_of_week=os.getenv("WEEKLY_DAY_OF_WEEK", "fri").strip().lower(),
            weekly_hour=_env_int("WEEKLY_HOUR_GMT", 16),
            weekly_minute=_env_int("WEEKLY_MINUTE_GMT", 0),
            max_messages_per_channel=_env_int("MAX_MESSAGES_PER_CHANNEL", 80),
            max_source_links=_env_int("MAX_SOURCE_LINKS", 8),
            openai_api_key=os.getenv("OPENAI_API_KEY", "").strip() or None,
            openai_model=os.getenv("OPENAI_MODEL", "gpt-4o-mini").strip(),
            openai_base_url=os.getenv("OPENAI_BASE_URL", "").strip() or None,
            db_path=db_path,
        )
