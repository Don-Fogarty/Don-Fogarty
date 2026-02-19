# Meridien Madness

Daily and weekly Slack bulletins that summarize what happened across selected public channels.

## V1 Scope (locked from discovery)

- Recipient: **you only** (single-user DM)
- Channels:
  - `#sales`
  - `#product`
  - `#marketing-growth`
  - `#marketing-brand`
  - `#customer-success`
  - `#customer-support`
  - `#shipped`
- Private channels: **not included in V1**
- Delivery: **Slack DM**
- Schedule:
  - Daily at **08:00 GMT**, covering the previous 24 hours
  - Weekly at **16:00 GMT Friday**, covering the previous 7 days
- Summary style: concise **2-minute skim**, focused on **what happened**
- Success metric: emoji reaction rate on each DM bulletin

## How it works (plain language)

1. The app fetches messages from your selected channels.
2. It picks high-signal content (replies, reactions, useful text).
3. It generates a concise bulletin:
   - `What happened`
   - `Channel pulse`
   - source links
4. It sends the bulletin as a DM to your Slack user.
5. It records sent bulletins in SQLite and tracks emoji reaction rate.

If `OPENAI_API_KEY` is provided, summaries use AI for higher quality.
If not, it falls back to a deterministic summarizer so delivery still works.

## Required accounts/services

- A Slack workspace where you can install a Slack App
- Bot token (`xoxb-...`) for that app
- Optional: OpenAI API key for better summary quality
- A place to run the scheduler continuously (local machine, VM, Render, Railway, etc.)

## Slack app setup

Create a Slack app and add these bot scopes:

- `channels:history`
- `channels:read`
- `chat:write`
- `im:write`
- `reactions:read`
- `users:read`

Install/reinstall the app in the workspace, then copy the bot token.

## Local setup

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
cp .env.example .env
```

Fill in `.env`:

- `SLACK_BOT_TOKEN`
- `SLACK_TARGET_USER_ID` (your Slack user ID, e.g. `U...`)
- optional `OPENAI_API_KEY`

## Run commands

Validate setup:

```bash
meridien-bulletin doctor
```

Preview daily bulletin without sending:

```bash
meridien-bulletin send --period daily --dry-run
```

Send immediately:

```bash
meridien-bulletin send --period daily
```

Run scheduler (long-lived):

```bash
meridien-bulletin schedule
```

View reaction success metric:

```bash
meridien-bulletin metrics --days 14
```

## Data storage

The app stores bulletin history and reaction metadata in:

- `.data/bulletins.db`

This powers your reaction-rate KPI.

## Notes

- V1 only tracks public channels.
- Source links are included for fast drill-down.
- Summaries are intentionally short to keep noise low.

## Version 2 ideas

- Channel-specific weighting (e.g., prioritize `#shipped` and `#sales`)
- Personalized sections (e.g., “needs your attention”)
- Trend tracking over time (wins, risks, blockers)
- Support for private channels with additional scopes/approval
