from __future__ import annotations

import re
from collections.abc import Iterable
from datetime import datetime

from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError

from .models import SlackMessage

_CHANNEL_ID_RE = re.compile(r"^[CG][A-Z0-9]+$")
_WS_RE = re.compile(r"\s+")
_SKIP_SUBTYPES = {"channel_join", "channel_leave", "channel_topic", "channel_purpose"}


class SlackDataClient:
    def __init__(self, token: str) -> None:
        self.client = WebClient(token=token)
        self._user_name_cache: dict[str, str] = {}
        self._channel_name_cache: dict[str, str] = {}

    def resolve_public_channels(self, requested_channels: list[str]) -> list[tuple[str, str]]:
        name_to_id: dict[str, str] = {}
        cursor: str | None = None

        while True:
            try:
                response = self.client.conversations_list(
                    types="public_channel",
                    exclude_archived=True,
                    limit=1000,
                    cursor=cursor,
                )
            except SlackApiError as exc:
                raise RuntimeError(f"Failed to list channels: {exc.response['error']}") from exc

            for channel in response.get("channels", []):
                channel_name = str(channel.get("name", "")).strip().lower()
                channel_id = str(channel.get("id", "")).strip()
                if channel_name and channel_id:
                    name_to_id[channel_name] = channel_id
                    self._channel_name_cache[channel_id] = channel_name

            cursor = response.get("response_metadata", {}).get("next_cursor") or None
            if not cursor:
                break

        resolved: list[tuple[str, str]] = []
        seen: set[str] = set()
        missing: list[str] = []

        for requested in requested_channels:
            raw = requested.strip()
            if not raw:
                continue

            channel_id: str | None = None
            channel_name: str | None = None

            if _CHANNEL_ID_RE.match(raw):
                channel_id = raw
                channel_name = self._lookup_channel_name(raw)
            else:
                normalized = raw.removeprefix("#").lower()
                channel_id = name_to_id.get(normalized)
                channel_name = normalized

            if not channel_id:
                missing.append(raw)
                continue

            if channel_id in seen:
                continue
            seen.add(channel_id)
            resolved.append((f"#{channel_name}" if channel_name else raw, channel_id))

        if missing:
            raise ValueError(
                "Could not resolve these public channels: "
                + ", ".join(missing)
                + ". Use #channel-name or channel IDs."
            )

        if not resolved:
            raise ValueError("No valid Slack channels configured.")

        return resolved

    def fetch_messages(
        self,
        channels: Iterable[tuple[str, str]],
        *,
        oldest: datetime,
        latest: datetime,
        max_messages_per_channel: int,
    ) -> list[SlackMessage]:
        all_messages: list[SlackMessage] = []
        oldest_ts = str(oldest.timestamp())
        latest_ts = str(latest.timestamp())

        for channel_name, channel_id in channels:
            messages = self._fetch_channel_messages(
                channel_id=channel_id,
                channel_name=channel_name,
                oldest_ts=oldest_ts,
                latest_ts=latest_ts,
                limit=max_messages_per_channel,
            )
            all_messages.extend(messages)

        all_messages.sort(key=lambda item: float(item.ts))
        return all_messages

    def _fetch_channel_messages(
        self,
        *,
        channel_id: str,
        channel_name: str,
        oldest_ts: str,
        latest_ts: str,
        limit: int,
    ) -> list[SlackMessage]:
        messages: list[SlackMessage] = []
        cursor: str | None = None

        while len(messages) < limit:
            try:
                response = self.client.conversations_history(
                    channel=channel_id,
                    oldest=oldest_ts,
                    latest=latest_ts,
                    inclusive=False,
                    limit=min(200, limit),
                    cursor=cursor,
                )
            except SlackApiError as exc:
                raise RuntimeError(
                    f"Failed to fetch messages for {channel_name}: {exc.response['error']}"
                ) from exc

            for raw in response.get("messages", []):
                if len(messages) >= limit:
                    break
                if self._skip_message(raw):
                    continue

                text = self._sanitize_text(str(raw.get("text", "")))
                if not text:
                    continue

                user_id = str(raw.get("user") or raw.get("bot_id") or "unknown")
                user_display = self._lookup_user_display(user_id) if raw.get("user") else "Bot"
                reaction_count = sum(int(item.get("count", 0)) for item in raw.get("reactions", []))
                reply_count = int(raw.get("reply_count", 0))
                ts = str(raw.get("ts"))

                if not ts:
                    continue

                messages.append(
                    SlackMessage(
                        channel_id=channel_id,
                        channel_name=channel_name,
                        ts=ts,
                        text=text,
                        user_id=user_id,
                        user_display=user_display,
                        reply_count=reply_count,
                        reaction_count=reaction_count,
                    )
                )

            cursor = response.get("response_metadata", {}).get("next_cursor") or None
            if not cursor:
                break

        return messages

    def open_dm_and_send(self, *, user_id: str, text: str) -> tuple[str, str]:
        try:
            dm_response = self.client.conversations_open(users=user_id)
            dm_channel_id = str(dm_response["channel"]["id"])
            message_response = self.client.chat_postMessage(
                channel=dm_channel_id,
                text=text,
                mrkdwn=True,
                unfurl_links=False,
                unfurl_media=False,
            )
            return dm_channel_id, str(message_response["ts"])
        except SlackApiError as exc:
            raise RuntimeError(f"Failed to send DM bulletin: {exc.response['error']}") from exc

    def get_message_permalink(self, *, channel_id: str, message_ts: str) -> str | None:
        try:
            response = self.client.chat_getPermalink(channel=channel_id, message_ts=message_ts)
            return str(response.get("permalink", "")) or None
        except SlackApiError:
            return None

    def get_message_reactions(self, *, channel_id: str, message_ts: str) -> tuple[int, list[str]]:
        try:
            response = self.client.reactions_get(channel=channel_id, timestamp=message_ts, full=False)
        except SlackApiError as exc:
            raise RuntimeError(f"Failed to fetch reactions: {exc.response['error']}") from exc

        reactions = response.get("message", {}).get("reactions", [])
        total = sum(int(item.get("count", 0)) for item in reactions)
        names = [str(item.get("name", "")).strip() for item in reactions if item.get("name")]
        return total, names

    def _lookup_user_display(self, user_id: str) -> str:
        if user_id in self._user_name_cache:
            return self._user_name_cache[user_id]
        try:
            response = self.client.users_info(user=user_id)
            profile = response.get("user", {}).get("profile", {})
            display_name = str(profile.get("display_name") or "").strip()
            real_name = str(profile.get("real_name") or "").strip()
            value = display_name or real_name or user_id
            self._user_name_cache[user_id] = value
            return value
        except SlackApiError:
            return user_id

    def _lookup_channel_name(self, channel_id: str) -> str:
        cached = self._channel_name_cache.get(channel_id)
        if cached:
            return cached
        try:
            response = self.client.conversations_info(channel=channel_id)
            name = str(response.get("channel", {}).get("name", "")).strip()
            if name:
                self._channel_name_cache[channel_id] = name
                return name
        except SlackApiError:
            pass
        return channel_id.lower()

    @staticmethod
    def _skip_message(raw: dict) -> bool:
        subtype = str(raw.get("subtype", "")).strip()
        if subtype in _SKIP_SUBTYPES:
            return True
        return bool(raw.get("hidden"))

    @staticmethod
    def _sanitize_text(text: str) -> str:
        text = _WS_RE.sub(" ", text.strip())
        return text
