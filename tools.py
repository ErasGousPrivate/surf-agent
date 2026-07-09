"""
Tool implementations available to the agent, and the JSON schemas Claude
uses to decide when/how to call them.

Data sources:
- Open-Meteo Marine API      -> wave height/period/direction (free, no key)
- Open-Meteo Weather API     -> wind speed/direction (free, no key)
- Stormglass.io              -> second opinion on swell/wind + tide extremes
                                 (free tier, key required)
- Google Calendar API        -> writes the chosen session(s) to your calendar
"""

import datetime
import requests

import config

OPEN_METEO_MARINE_URL = "https://marine-api.open-meteo.com/v1/marine"
OPEN_METEO_WEATHER_URL = "https://api.open-meteo.com/v1/forecast"
STORMGLASS_WEATHER_URL = "https://api.stormglass.io/v2/weather/point"
STORMGLASS_TIDE_URL = "https://api.stormglass.io/v2/tide/extremes/point"
GOOGLE_CALENDAR_TOKEN_URL = "https://oauth2.googleapis.com/token"
GOOGLE_CALENDAR_EVENTS_URL = (
    "https://www.googleapis.com/calendar/v3/calendars/{calendar_id}/events"
)


def _spot_lookup(spot_name: str):
    for s in config.SPOTS:
        if s["name"].lower() == spot_name.lower():
            return s
    raise ValueError(
        f"Unknown spot '{spot_name}'. Known spots: "
        f"{[s['name'] for s in config.SPOTS]}"
    )


# ---------------------------------------------------------------------------
# Open-Meteo: marine (wave) data
# ---------------------------------------------------------------------------
def fetch_marine_forecast(spot_name: str) -> dict:
    spot = _spot_lookup(spot_name)
    params = {
        "latitude": spot["lat"],
        "longitude": spot["lon"],
        "hourly": ",".join(
            [
                "wave_height",
                "wave_direction",
                "wave_period",
                "swell_wave_height",
                "swell_wave_direction",
                "swell_wave_period",
            ]
        ),
        "timezone": "Africa/Johannesburg",
        "forecast_days": config.FORECAST_DAYS,
    }
    resp = requests.get(OPEN_METEO_MARINE_URL, params=params, timeout=30)
    resp.raise_for_status()
    return resp.json()


# ---------------------------------------------------------------------------
# Open-Meteo: wind/weather data
# ---------------------------------------------------------------------------
def fetch_weather_forecast(spot_name: str) -> dict:
    spot = _spot_lookup(spot_name)
    params = {
        "latitude": spot["lat"],
        "longitude": spot["lon"],
        "hourly": "wind_speed_10m,wind_direction_10m,wind_gusts_10m",
        "wind_speed_unit": "kmh",
        "timezone": "Africa/Johannesburg",
        "forecast_days": config.FORECAST_DAYS,
    }
    resp = requests.get(OPEN_METEO_WEATHER_URL, params=params, timeout=30)
    resp.raise_for_status()
    return resp.json()


# ---------------------------------------------------------------------------
# Stormglass: second-opinion swell/wind + tide extremes
# ---------------------------------------------------------------------------
def _stormglass_window():
    start = datetime.datetime.utcnow()
    end = start + datetime.timedelta(days=config.FORECAST_DAYS)
    return start.isoformat() + "Z", end.isoformat() + "Z"


def fetch_stormglass_forecast(spot_name: str) -> dict:
    spot = _spot_lookup(spot_name)
    start, end = _stormglass_window()
    params = {
        "lat": spot["lat"],
        "lng": spot["lon"],
        "params": ",".join(
            ["swellHeight", "swellPeriod", "swellDirection", "windSpeed", "windDirection"]
        ),
        "start": start,
        "end": end,
    }
    headers = {"Authorization": config.STORMGLASS_API_KEY}
    resp = requests.get(
        STORMGLASS_WEATHER_URL, params=params, headers=headers, timeout=30
    )
    resp.raise_for_status()
    return resp.json()


def fetch_tide_extremes(spot_name: str) -> dict:
    spot = _spot_lookup(spot_name)
    start, end = _stormglass_window()
    params = {
        "lat": spot["lat"],
        "lng": spot["lon"],
        "start": start,
        "end": end,
    }
    headers = {"Authorization": config.STORMGLASS_API_KEY}
    resp = requests.get(
        STORMGLASS_TIDE_URL, params=params, headers=headers, timeout=30
    )
    resp.raise_for_status()
    return resp.json()


# ---------------------------------------------------------------------------
# Google Calendar: create the chosen session(s)
# ---------------------------------------------------------------------------
def _get_google_access_token() -> str:
    resp = requests.post(
        GOOGLE_CALENDAR_TOKEN_URL,
        data={
            "client_id": config.GOOGLE_CLIENT_ID,
            "client_secret": config.GOOGLE_CLIENT_SECRET,
            "refresh_token": config.GOOGLE_REFRESH_TOKEN,
            "grant_type": "refresh_token",
        },
        timeout=30,
    )
    resp.raise_for_status()
    return resp.json()["access_token"]


def create_calendar_event(
    summary: str,
    description: str,
    start_iso: str,
    end_iso: str,
    location: str = "",
) -> dict:
    """
    start_iso / end_iso must be full ISO8601 datetimes with timezone offset,
    e.g. '2026-07-12T07:00:00+02:00'
    """
    access_token = _get_google_access_token()
    url = GOOGLE_CALENDAR_EVENTS_URL.format(calendar_id=config.GOOGLE_CALENDAR_ID)
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json",
    }
    body = {
        "summary": summary,
        "description": description,
        "location": location,
        "start": {"dateTime": start_iso, "timeZone": "Africa/Johannesburg"},
        "end": {"dateTime": end_iso, "timeZone": "Africa/Johannesburg"},
    }
    resp = requests.post(url, headers=headers, json=body, timeout=30)
    resp.raise_for_status()
    created = resp.json()
    return {"status": "created", "event_link": created.get("htmlLink")}


# ---------------------------------------------------------------------------
# Tool dispatch + schemas for Claude
# ---------------------------------------------------------------------------
TOOL_FUNCTIONS = {
    "fetch_marine_forecast": fetch_marine_forecast,
    "fetch_weather_forecast": fetch_weather_forecast,
    "fetch_stormglass_forecast": fetch_stormglass_forecast,
    "fetch_tide_extremes": fetch_tide_extremes,
    "create_calendar_event": create_calendar_event,
}

TOOL_DEFINITIONS = [
    {
        "name": "fetch_marine_forecast",
        "description": (
            "Get wave/swell forecast (height, period, direction, and separated "
            "swell component) for a named surf spot over the forecast window, "
            "from Open-Meteo Marine. Hourly resolution. Direction values are "
            "the direction the swell is coming FROM, in compass degrees "
            "(0=N, 90=E, 180=S, 270=W) -- matches the convention used in the "
            "spot beta reference doc."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "spot_name": {
                    "type": "string",
                    "description": "Exact name of one of the configured surf spots.",
                }
            },
            "required": ["spot_name"],
        },
    },
    {
        "name": "fetch_weather_forecast",
        "description": (
            "Get wind forecast (speed, direction, gusts) for a named surf spot "
            "over the forecast window, from Open-Meteo. Hourly resolution. "
            "Direction is the direction the wind is coming FROM, in compass "
            "degrees (0=N, 90=E, 180=S, 270=W) -- matches the convention used "
            "in the spot beta reference doc (e.g. 'NW offshore' means wind "
            "coming from the NW)."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "spot_name": {
                    "type": "string",
                    "description": "Exact name of one of the configured surf spots.",
                }
            },
            "required": ["spot_name"],
        },
    },
    {
        "name": "fetch_stormglass_forecast",
        "description": (
            "Get a second-opinion swell and wind forecast for a named surf spot "
            "from Stormglass, to cross-check against Open-Meteo. Use this to "
            "reconcile disagreements between sources before deciding, not as "
            "the only source. Direction values (swellDirection, windDirection) "
            "are the direction things are coming FROM, same convention as "
            "fetch_marine_forecast and fetch_weather_forecast -- directly "
            "comparable across sources without conversion."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "spot_name": {
                    "type": "string",
                    "description": "Exact name of one of the configured surf spots.",
                }
            },
            "required": ["spot_name"],
        },
    },
    {
        "name": "fetch_tide_extremes",
        "description": (
            "Get high/low tide times and heights for a named surf spot over "
            "the forecast window, from Stormglass."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "spot_name": {
                    "type": "string",
                    "description": "Exact name of one of the configured surf spots.",
                }
            },
            "required": ["spot_name"],
        },
    },
    {
        "name": "create_calendar_event",
        "description": (
            "Create an event on the user's Google Calendar for a chosen surf "
            "session. Only call this once you have committed to a final "
            "decision on spot, date, and time window. Call it once per "
            "session you decide to recommend (usually just one for the week, "
            "but you may create more than one if genuinely justified)."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "summary": {
                    "type": "string",
                    "description": "Short calendar event title, e.g. 'Surf: Muizenberg'.",
                },
                "description": {
                    "type": "string",
                    "description": (
                        "Reasoning for this pick: swell, wind, tide, and why it "
                        "suits a longboard/short paddle-out preference, plus a "
                        "one-line note on the runner-up option."
                    ),
                },
                "start_iso": {
                    "type": "string",
                    "description": "ISO8601 datetime with timezone offset, e.g. 2026-07-12T07:00:00+02:00",
                },
                "end_iso": {
                    "type": "string",
                    "description": "ISO8601 datetime with timezone offset.",
                },
                "location": {
                    "type": "string",
                    "description": "Spot name, used as the calendar event location.",
                },
            },
            "required": ["summary", "description", "start_iso", "end_iso"],
        },
    },
]
