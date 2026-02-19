# Render Runbook (Meridien Madness)

This runbook gets your Slack bulletin live on Render and keeps it healthy.

## 1) Prerequisites

- Slack bot app installed in your workspace with scopes:
  - `channels:history`
  - `channels:read`
  - `chat:write`
  - `im:write`
  - `reactions:read`
  - `users:read`
- Slack bot token (`SLACK_BOT_TOKEN`)
- Your Slack user ID (`SLACK_TARGET_USER_ID`, format `U...`)
- OpenAI key (`OPENAI_API_KEY`) for high-quality summaries

## 2) Deploy with Blueprint

1. In Render, click **New +** → **Blueprint**.
2. Select this GitHub repo and branch.
3. Render detects `render.yaml` and creates one worker service:
   - `meridien-madness-bulletin`
4. Add secret env vars in Render:
   - `SLACK_BOT_TOKEN`
   - `SLACK_TARGET_USER_ID`
   - `OPENAI_API_KEY`
5. Click **Apply** and let deployment finish.

## 3) Verify boot logs

Open service logs and confirm:

- `Startup validation passed. Tracking channels: ...`
- `Scheduler started with timezone=Etc/GMT`

If you see channel resolution errors, verify channel names and bot access.

## 4) Smoke test (manual)

Use Render Shell and run:

```bash
python -m meridien_bulletin send --period daily
```

Expected result:

- You receive a DM bulletin in Slack.
- A row is inserted in `/var/data/bulletins.db`.

## 5) KPI check

After reacting to a bulletin, run:

```bash
python -m meridien_bulletin metrics --days 14
```

Track this metric:

- **Reaction rate = bulletins with >=1 emoji / total bulletins sent**

## 6) Operating notes

- Database path on Render is `/var/data/bulletins.db` (persistent disk).
- Deploys and restarts do not lose KPI history when disk is mounted.
- Daily digest runs at 08:00 GMT.
- Weekly digest runs at 16:00 GMT Friday.
- Reaction refresh runs every 6 hours.

## 7) Incident guide

If no bulletin arrives:

1. Check worker logs for Slack API errors (`invalid_auth`, `not_in_channel`, `missing_scope`).
2. Run doctor check in Render Shell:
   ```bash
   python -m meridien_bulletin doctor
   ```
3. Confirm Slack app still has required scopes and is installed.
4. Confirm target user ID is valid and unchanged.

If summaries degrade:

1. Check OpenAI key validity.
2. Verify `OPENAI_MODEL` is set and available.
3. Fallback summarizer will keep delivery running even if OpenAI fails.
