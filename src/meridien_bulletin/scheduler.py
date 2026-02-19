from __future__ import annotations

import logging
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

from apscheduler.schedulers.blocking import BlockingScheduler

from .bulletin import BulletinService
from .config import Settings

logger = logging.getLogger(__name__)


class BulletinScheduler:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.service = BulletinService(settings)
        self.scheduler = BlockingScheduler(timezone=ZoneInfo(settings.timezone_name))

    def start(self) -> None:
        self.scheduler.add_job(
            self._run_daily,
            trigger="cron",
            hour=self.settings.daily_hour,
            minute=self.settings.daily_minute,
            id="daily-bulletin",
            replace_existing=True,
        )
        self.scheduler.add_job(
            self._run_weekly,
            trigger="cron",
            day_of_week=self.settings.weekly_day_of_week,
            hour=self.settings.weekly_hour,
            minute=self.settings.weekly_minute,
            id="weekly-bulletin",
            replace_existing=True,
        )
        self.scheduler.add_job(
            self._refresh_metrics,
            trigger="cron",
            hour="*/6",
            minute=5,
            id="refresh-reactions",
            replace_existing=True,
        )

        logger.info("Scheduler started with timezone=%s", self.settings.timezone_name)
        self.scheduler.start()

    def _run_daily(self) -> None:
        logger.info("Running daily bulletin at %s", datetime.now(tz=timezone.utc).isoformat())
        self.service.run(period="daily", dry_run=False)

    def _run_weekly(self) -> None:
        logger.info("Running weekly bulletin at %s", datetime.now(tz=timezone.utc).isoformat())
        self.service.run(period="weekly", dry_run=False)

    def _refresh_metrics(self) -> None:
        total, reacted, rate = self.service.refresh_reaction_metrics(days=14)
        logger.info("Reaction metrics refreshed: total=%s reacted=%s rate=%.2f", total, reacted, rate)
