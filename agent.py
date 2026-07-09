"""
Surf forecast agent.

Run on a schedule (see .github/workflows/surf-agent.yml). Each run:
  1. Gives Claude the spot list, surfer profile, and a set of tools for
     pulling wave/wind/tide data plus writing to Google Calendar.
  2. Claude decides which tools to call, for which spots, and how to
     reconcile disagreement between sources -- this is the actual agentic
     part, not scripted logic.
  3. Once Claude has committed to a decision, it calls create_calendar_event
     to schedule the session(s), then produces a short final summary.

Requires env vars (see config.py): ANTHROPIC_API_KEY, STORMGLASS_API_KEY,
GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET, GOOGLE_REFRESH_TOKEN.
"""

import datetime
import json

import anthropic

import config
import tools

with open("spot_beta.md", "r", encoding="utf-8") as f:
    SPOT_BETA = f.read()


SYSTEM_PROMPT = f"""You are a surf forecast agent. Your job is to
independently score each day in the next {config.FORECAST_DAYS} days on its
own merits, across a fixed set of spots, and schedule a session on the
user's Google Calendar for every day that genuinely qualifies against the
surfer profile and spot beta below -- that could be zero days, one day, or
several. There is no target number of sessions to hit; do not force a
"pick of the week."

Today's date is {datetime.date.today().isoformat()}. All times you reason
about and write to the calendar should be in the Africa/Johannesburg
timezone (UTC+2, no DST).

SPOTS (False Bay, Cape Peninsula):
{json.dumps(config.SPOTS, indent=2)}

SURFER PROFILE:
{config.SURFER_PROFILE}

SPOT BETA (compiled local knowledge for these exact spots -- what makes
each one actually fire, not generic beach-break reasoning. This is your
primary reference for what "good conditions" means at each spot):
{SPOT_BETA}

HOW TO WORK:
1. Call list_calendar_events FIRST, before doing anything else, to see what
   sessions (if any) a previous run has already booked in this window.
   Keep these in mind through the rest of your reasoning.
2. For each spot, pull wave/swell data (fetch_marine_forecast), wind data
   (fetch_weather_forecast), a second-opinion forecast (fetch_stormglass_forecast),
   and tide extremes (fetch_tide_extremes).
3. Where Open-Meteo and Stormglass disagree on swell height/period/direction
   or wind, don't just average them blindly -- reason about which is more
   plausible (e.g. do they roughly agree in trend even if not exact
   magnitude? does one look like an outlier?), and say so briefly in your
   reasoning.
4. Score each day independently against BOTH the surfer profile and the
   spot beta above. For each day, consider all spots and judge which spot
   (if any) is offering the best window that day -- each spot has
   different ideal swell direction, wind direction, and tide, so the same
   forecast can be great at one spot and poor at another on the same day.
   Different qualifying days are free to use different spots; you are not
   locked into one spot for the whole window.
5. A day "qualifies" if it genuinely meets the bar set by the surfer
   profile and spot beta at at least one spot -- not by comparing it
   against other days in the window. Schedule a session for every day
   that qualifies. Do not force a single best pick, and do not force a
   fixed number of sessions -- some weeks that's zero days, some weeks
   it's several.
6. Before scheduling a session for a given day/spot, check it against what
   list_calendar_events returned. If that day/spot is already booked from
   a previous run, don't create a duplicate. Only prefer a different pick
   for that day if conditions have clearly and meaningfully changed since
   the existing event's description suggests -- and if so, don't silently
   overwrite it (there is no delete/edit tool available to you); leave the
   existing event as-is, don't create the new one either, and clearly flag
   the conflict in your final text response so the user can resolve it
   manually.
7. Call create_calendar_event for each day/spot you decide to schedule.
   Put your reasoning (source reconciliation, why this spot/time, what
   pushed it over the bar) in the event description so the user can see
   why you made this call, not just what you picked.
8. After scheduling (or deciding not to schedule anything), give a short
   plain-text summary covering: which days/spots you booked and why, which
   days you considered but rejected and why, and any calendar conflicts
   you flagged instead of resolving automatically.

Do not schedule a session for a day if conditions at every spot that day
are genuinely poor for this surfer -- just skip that day. If every day in
the window is poor, it's fine to schedule nothing at all; explain why in
your final text response instead of forcing a pick onto the calendar.
"""


def run_tool(tool_name: str, tool_input: dict) -> dict:
    func = tools.TOOL_FUNCTIONS.get(tool_name)
    if func is None:
        return {"error": f"Unknown tool: {tool_name}"}
    try:
        return func(**tool_input)
    except Exception as e:  # noqa: BLE001 - surface any failure back to the agent
        return {"error": str(e)}


def main():
    client = anthropic.Anthropic(api_key=config.ANTHROPIC_API_KEY)

    messages = [
        {
            "role": "user",
            "content": (
                "Check current conditions and decide + schedule the best "
                "surf session for the coming days."
            ),
        }
    ]

    full_log_parts = []
    final_text = ""

    max_turns = 20  # safety cap so a stuck loop can't run forever in CI
    for turn in range(max_turns):
        response = client.messages.create(
            model=config.MODEL,
            max_tokens=4096,
            system=SYSTEM_PROMPT,
            tools=tools.TOOL_DEFINITIONS,
            messages=messages,
        )

        # Log any reasoning/text Claude produces along the way
        turn_texts = []
        for block in response.content:
            if block.type == "text" and block.text.strip():
                print(f"\n--- agent (turn {turn}) ---\n{block.text}")
                turn_texts.append(block.text)
        if turn_texts:
            full_log_parts.append("\n".join(turn_texts))

        if response.stop_reason != "tool_use":
            # Agent is done -- no more tool calls, final answer already printed
            final_text = "\n".join(turn_texts)
            break

        # Execute every tool_use block, feed results back
        messages.append({"role": "assistant", "content": response.content})
        tool_results = []
        for block in response.content:
            if block.type == "tool_use":
                print(f"\n[tool call] {block.name}({block.input})")
                result = run_tool(block.name, block.input)
                tool_results.append(
                    {
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": json.dumps(result, default=str)[:8000],
                        # cap payload size so huge hourly arrays don't blow the context
                    }
                )
        messages.append({"role": "user", "content": tool_results})
    else:
        print("\n[warning] Hit max_turns without the agent finishing on its own.")

    full_log = "\n\n".join(full_log_parts)
    email_body = (
        f"{final_text}\n"
        f"---\n"
        f"Full reasoning log:\n"
        f"{full_log}"
    )
    subject = f"Surf Forecast Briefing - {datetime.date.today().isoformat()}"
    tools.send_email(subject, email_body)


if __name__ == "__main__":
    main()
