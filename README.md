# Surf Forecast Agent

Checks conditions daily across three False Bay longboard spots (Muizenberg,
Glencairn, Cemetery/Baden Powell), reconciles multiple forecast sources,
and schedules the best surf session in the next 5 days onto your Google
Calendar. Runs unattended on GitHub Actions.

## How it works

`agent.py` gives Claude a set of tools (`tools.py`) — wave/swell data,
wind data, a second forecast source, tide extremes, and calendar write
access — and lets it decide which to call, for which spots, and how to
weigh disagreement between sources, before committing to a decision and
writing it to your calendar. This is a real tool-use agent loop, not a
fixed pipeline: the reconciliation and spot-selection logic lives in
Claude's reasoning at runtime, not in scripted rules.

`spot_beta.md` is compiled local knowledge for these exact spots — ideal
swell direction/size, offshore wind direction, tide preference, and
season for each of the three, since generic beach-break reasoning can't
tell them apart. It's loaded into the system prompt on every run
(`agent.py` reads it at startup), not fetched dynamically — it's small
and always relevant, so there's no need for retrieval logic. Edit this
file directly to correct or expand the local knowledge; no code changes
needed.

## One-time setup

### 1. Install dependencies locally (for the auth step only)

```
pip install -r requirements.txt
```

### 2. Get your Google Calendar refresh token

You should already have:
- A Google Cloud project with the Calendar API enabled
- An OAuth Client ID (Desktop app type), downloaded as `client_secret_XXXX.json`
- Yourself added as a test user on the OAuth consent screen

Run:

```
python calendar_auth.py /path/to/client_secret_XXXX.json
```

This opens your browser, you log in and click Allow (click through the
"unverified app" warning — expected for a personal script), and the script
prints:

```
GOOGLE_CLIENT_ID=...
GOOGLE_CLIENT_SECRET=...
GOOGLE_REFRESH_TOKEN=...
```

### 3. Get a Stormglass API key

Sign up free at https://stormglass.io — free tier is enough for this
(3 spots x 2 calls/day is well under the daily limit).

### 4. Get an Anthropic API key

From https://console.anthropic.com if you don't already have one.

### 5. Add all five values as GitHub Actions secrets

In your repo: **Settings → Secrets and variables → Actions → New repository
secret**. Add:

- `ANTHROPIC_API_KEY`
- `STORMGLASS_API_KEY`
- `GOOGLE_CLIENT_ID`
- `GOOGLE_CLIENT_SECRET`
- `GOOGLE_REFRESH_TOKEN`

### 6. Push this repo to GitHub

Make sure `client_secret_*.json` never gets committed — it's in
`.gitignore` already, but double check with `git status` before your first
commit.

## Running it

- **Automatically**: every day at 06:00 SAST, via the schedule in
  `.github/workflows/surf-agent.yml`.
- **Manually**: go to the **Actions** tab on GitHub → **Surf Forecast
  Agent** → **Run workflow**.
- **Locally** (for testing/debugging): export the five env vars above in
  your shell, then run `python agent.py` directly — you'll see the agent's
  full reasoning and tool calls printed to the terminal.

## Adjusting the agent

- **Spots**: edit `SPOTS` in `config.py`.
- **Surf preferences**: edit `SURFER_PROFILE` in `config.py` — this is
  plain English, no need to touch code logic to change what the agent
  optimizes for.
- **Schedule time**: edit the cron line in
  `.github/workflows/surf-agent.yml`.
- **Forecast window**: `FORECAST_DAYS` in `config.py`.

## Notes / known limitations

- Stormglass free tier is rate-limited — if you add more spots or run the
  agent more than once a day, you may hit the ceiling. The agent will
  surface the error in tool output rather than crash silently.
- Open-Meteo's marine model has no local buoy ground-truth for False Bay
  (unlike, say, the US coastline with NDBC), so it's a modeled forecast,
  not a direct measurement — this is exactly why Stormglass is included as
  a second, independent estimate for the agent to reconcile against.
- The agent writes its reasoning into the calendar event's description
  field, so you can check after the fact why it picked what it picked.
