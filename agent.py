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


SYSTEM_PROMPT = f"""You are a surf forecast agent. Your job is to decide the
single best surf session (or, if genuinely justified, a small number of
sessions) for the user over the next {config.FORECAST_DAYS} days, across a
fixed set of spots, and schedule it on their Google Calendar.

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
1. For each spot, pull wave/swell data (fetch_marine_forecast), wind data
   (fetch_weather_forecast), a second-opinion forecast (fetch_stormglass_forecast),
   and tide extremes (fetch_tide_extremes).
2. Where Open-Meteo and Stormglass disagree on swell height/period/direction
   or wind, don't just average them blindly -- reason about which is more
   plausible (e.g. do they roughly agree in trend even if not exact
   magnitude? does one look like an outlier?), and say so briefly in your
   reasoning.
3. Score windows (spot x day x rough time-of-day) against BOTH the surfer
   profile and the spot beta above -- each spot has different ideal swell
   direction, wind direction, and tide, so the same forecast can be great
   at one spot and poor at another. Don't apply one generic rule across
   all three.
4. Pick the best window in the next {config.FORECAST_DAYS} days. Prefer a
   single strong recommendation over hedging across many mediocre options.
   Only recommend more than one session if two days are both clearly good
   and meaningfully different in character.
5. Call create_calendar_event for your final pick(s). Put your reasoning
   (source reconciliation, why this spot/time, runner-up) in the event
   description so the user can see why you made this call, not just what
   you picked.
6. After scheduling, give a short plain-text summary of your decision and
   reasoning as your final response.

Do not schedule a session if conditions across all spots for the whole
window are genuinely poor for this surfer -- in that case, explain why in
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
        for block in response.content:
            if block.type == "text" and block.text.strip():
                print(f"\n--- agent (turn {turn}) ---\n{block.text}")

        if response.stop_reason != "tool_use":
            # Agent is done -- no more tool calls, final answer already printed
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


if __name__ == "__main__":
    main()
