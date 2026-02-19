from datetime import datetime, timezone

from meridien_bulletin.models import SlackMessage
from meridien_bulletin.summarizer import BulletinSummarizer


def _msg(
    *,
    channel_name: str,
    text: str,
    ts: str,
    reply_count: int = 0,
    reaction_count: int = 0,
) -> SlackMessage:
    return SlackMessage(
        channel_id=f"C_{channel_name}",
        channel_name=channel_name,
        ts=ts,
        text=text,
        user_id="U1",
        user_display="Don",
        reply_count=reply_count,
        reaction_count=reaction_count,
    )


def test_fallback_summary_contains_expected_sections() -> None:
    summarizer = BulletinSummarizer(
        openai_api_key=None,
        openai_model="gpt-4o-mini",
        openai_base_url=None,
    )
    messages = [
        _msg(
            channel_name="#sales",
            text="Booked two enterprise meetings and one deal moved to procurement.",
            ts="1708330000.000100",
            reply_count=3,
            reaction_count=4,
        ),
        _msg(
            channel_name="#product",
            text="Finalized onboarding experiment copy and shipped variant B.",
            ts="1708331000.000100",
            reply_count=1,
            reaction_count=2,
        ),
    ]
    result = summarizer.summarize(
        period="daily",
        window_start=datetime(2026, 2, 18, 8, 0, tzinfo=timezone.utc),
        window_end=datetime(2026, 2, 19, 8, 0, tzinfo=timezone.utc),
        messages=messages,
        source_limit=4,
    )
    assert "*What happened*" in result.text
    assert "*Channel pulse*" in result.text
    assert "#sales" in result.text
    assert len(result.source_messages) >= 1
