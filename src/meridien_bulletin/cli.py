from __future__ import annotations

import logging

import typer

from .bulletin import BulletinService
from .config import Settings
from .scheduler import BulletinScheduler

app = typer.Typer(help="Meridien bulletin CLI.")


def _settings_or_exit() -> Settings:
    try:
        return Settings.from_env()
    except Exception as exc:
        typer.secho(f"Configuration error: {exc}", fg=typer.colors.RED, err=True)
        raise typer.Exit(code=1) from exc


@app.command("send")
def send_command(
    period: str = typer.Option("daily", help="daily or weekly"),
    dry_run: bool = typer.Option(False, help="Generate bulletin text without sending to Slack."),
) -> None:
    """Generate and optionally send a bulletin."""
    settings = _settings_or_exit()
    service = BulletinService(settings)
    result = service.run(period=period, dry_run=dry_run)
    typer.echo(result)


@app.command("schedule")
def schedule_command() -> None:
    """Run the long-lived scheduler."""
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    settings = _settings_or_exit()
    scheduler = BulletinScheduler(settings)
    scheduler.start()


@app.command("metrics")
def metrics_command(
    days: int = typer.Option(14, min=1, help="Lookback window in days."),
    refresh: bool = typer.Option(True, help="Refresh reaction counts before reporting."),
) -> None:
    """Show emoji reaction success metrics."""
    settings = _settings_or_exit()
    service = BulletinService(settings)
    if refresh:
        total, reacted, rate = service.refresh_reaction_metrics(days=days)
    else:
        total, reacted = service.store.reaction_metrics(days=days)
        rate = (reacted / total) if total else 0.0
    typer.echo(f"Bulletins in window: {total}")
    typer.echo(f"Bulletins with emoji reaction: {reacted}")
    typer.echo(f"Reaction rate: {rate:.0%}")


@app.command("doctor")
def doctor_command() -> None:
    """Validate configuration and Slack access."""
    settings = _settings_or_exit()
    service = BulletinService(settings)
    channels = service.slack.resolve_public_channels(settings.slack_channels)
    channel_names = ", ".join(name for name, _ in channels)
    mode = "AI summarization enabled" if settings.openai_api_key else "fallback summarization only"
    typer.secho("Configuration looks good.", fg=typer.colors.GREEN)
    typer.echo(f"Channels: {channel_names}")
    typer.echo(f"Summary mode: {mode}")


def main() -> None:
    app()


if __name__ == "__main__":
    main()
