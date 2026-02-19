from __future__ import annotations

from collections import defaultdict
from datetime import datetime

from openai import OpenAI

from .models import SlackMessage, SummaryResult


def _message_score(message: SlackMessage) -> float:
    engagement = (message.reaction_count * 3.0) + (message.reply_count * 2.0)
    text_weight = min(len(message.text), 320) / 120.0
    return engagement + text_weight


def _truncate(value: str, max_chars: int) -> str:
    if len(value) <= max_chars:
        return value
    return value[: max_chars - 1].rstrip() + "…"


class BulletinSummarizer:
    def __init__(
        self,
        *,
        openai_api_key: str | None,
        openai_model: str,
        openai_base_url: str | None = None,
    ) -> None:
        self.openai_model = openai_model
        self._client: OpenAI | None = None
        if openai_api_key:
            self._client = OpenAI(api_key=openai_api_key, base_url=openai_base_url)

    def summarize(
        self,
        *,
        period: str,
        window_start: datetime,
        window_end: datetime,
        messages: list[SlackMessage],
        source_limit: int,
    ) -> SummaryResult:
        if not messages:
            return SummaryResult(
                text=(
                    "*What happened*\n"
                    "• No meaningful updates were posted in the selected channels for this window.\n\n"
                    "*Channel pulse*\n"
                    "• Quiet period across tracked channels."
                ),
                source_messages=[],
            )

        source_messages = self.pick_source_messages(messages, limit=source_limit)
        if self._client is not None:
            try:
                text = self._summarize_with_openai(
                    period=period,
                    window_start=window_start,
                    window_end=window_end,
                    messages=messages,
                )
                if text.strip():
                    return SummaryResult(text=text.strip(), source_messages=source_messages)
            except Exception:
                # Fallback keeps delivery reliable when model/API is unavailable.
                pass

        return SummaryResult(
            text=self._summarize_fallback(period=period, messages=messages),
            source_messages=source_messages,
        )

    def pick_source_messages(self, messages: list[SlackMessage], *, limit: int) -> list[SlackMessage]:
        if limit <= 0:
            return []

        by_channel: dict[str, list[SlackMessage]] = defaultdict(list)
        for item in messages:
            by_channel[item.channel_id].append(item)

        selected: list[SlackMessage] = []
        for channel_messages in by_channel.values():
            top = max(channel_messages, key=_message_score)
            selected.append(top)

        selected.sort(key=lambda msg: (_message_score(msg), float(msg.ts)), reverse=True)
        dedup: list[SlackMessage] = []
        seen: set[tuple[str, str]] = set()
        for item in selected + sorted(messages, key=_message_score, reverse=True):
            key = (item.channel_id, item.ts)
            if key in seen:
                continue
            seen.add(key)
            dedup.append(item)
            if len(dedup) >= limit:
                break
        return dedup

    def _summarize_with_openai(
        self,
        *,
        period: str,
        window_start: datetime,
        window_end: datetime,
        messages: list[SlackMessage],
    ) -> str:
        assert self._client is not None
        max_words = 180 if period == "daily" else 260
        scored = sorted(messages, key=_message_score, reverse=True)
        curated = scored[:200]

        lines: list[str] = []
        for item in curated:
            line = (
                f"{item.channel_name} | {item.user_display} | "
                f"replies={item.reply_count} reactions={item.reaction_count} | "
                f"{_truncate(item.text, 280)}"
            )
            lines.append(line)

        payload = "\n".join(lines)
        system_prompt = (
            "You write concise internal company bulletins for founders. "
            "The user wants a 2-minute skim focused on what happened. "
            "Cut noise, avoid speculation, avoid fluff, and do not invent facts."
        )
        user_prompt = (
            f"Period: {period}\n"
            f"Window start (UTC): {window_start.isoformat()}\n"
            f"Window end (UTC): {window_end.isoformat()}\n\n"
            "Create Slack-formatted markdown using exactly these sections:\n"
            "*What happened*\n"
            "- Up to 8 bullets, ordered by importance.\n\n"
            "*Channel pulse*\n"
            "- One short line per channel with meaningful activity.\n\n"
            f"Hard limit: {max_words} words total.\n"
            "If activity is low, say so plainly.\n\n"
            "Messages:\n"
            f"{payload}"
        )

        completion = self._client.chat.completions.create(
            model=self.openai_model,
            temperature=0.2,
            max_tokens=550,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
        )
        result = completion.choices[0].message.content or ""
        return result.strip()

    def _summarize_fallback(self, *, period: str, messages: list[SlackMessage]) -> str:
        per_channel: dict[str, list[SlackMessage]] = defaultdict(list)
        for msg in messages:
            per_channel[msg.channel_name].append(msg)

        channel_sorted = sorted(
            per_channel.items(),
            key=lambda item: max((_message_score(msg) for msg in item[1]), default=0.0),
            reverse=True,
        )

        max_lines = 8 if period == "daily" else 12
        what_happened: list[str] = []
        for channel_name, channel_messages in channel_sorted:
            top = sorted(channel_messages, key=_message_score, reverse=True)[:1]
            for item in top:
                snippet = _truncate(item.text, 120)
                what_happened.append(
                    f"• {channel_name}: {snippet} "
                    f"(replies: {item.reply_count}, reactions: {item.reaction_count})"
                )
            if len(what_happened) >= max_lines:
                break

        pulse_lines: list[str] = []
        for channel_name, channel_messages in sorted(per_channel.items(), key=lambda it: it[0]):
            pulse_lines.append(f"• {channel_name}: {len(channel_messages)} message(s)")

        return (
            "*What happened*\n"
            + ("\n".join(what_happened) if what_happened else "• Low-signal period across channels.")
            + "\n\n*Channel pulse*\n"
            + ("\n".join(pulse_lines) if pulse_lines else "• No channel activity.")
        )
