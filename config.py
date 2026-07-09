"""
Config for the surf forecast agent.
Secrets are read from environment variables (set as GitHub Actions secrets
in production, or a local .env / exported vars when testing).
"""

import os

from dotenv import load_dotenv

load_dotenv()  # no-op if .env doesn't exist (e.g. in GitHub Actions)

# --- Surf spots (False Bay, Cape Peninsula) ---
SPOTS = [
    {
        "name": "Muizenberg",
        "lat": -34.108,
        "lon": 18.470,
        "notes": "Beach break, sheltered corner of the bay, classic longboard wave, "
                 "usually the most forgiving/gentlest of the three.",
    },
    {
        "name": "Glencairn",
        "lat": -34.161667,
        "lon": 18.432361,
        "notes": "Beach break on the western side of the bay, more exposed to "
                 "SW groundswell than Muizenberg.",
    },
    {
        "name": "Cemetery (Baden Powell)",
        "lat": -34.094361,
        "lon": 18.520389,
        "notes": "Beach break on the eastern side of the bay off Baden Powell Drive, "
                 "different wind/swell exposure to the other two.",
    },
]

# --- Surfer profile (used to steer the agent's judgment) ---
SURFER_PROFILE = """
Board: Longboard.
Strong preference for a SHORT, EASY PADDLE OUT — avoid spots/days where the
paddle out looks like it'll be a battle (large shorebreak, strong rips, big
close-out sets).
Prefers smaller, well-organised, longer-period swell over large or wind-chopped
short-period swell. Comfortable wave face height roughly 0.5m-1.2m; anything
consistently forecast above ~1.5m at these beach breaks should be treated as
marginal-to-skip for this rider.
Favours light wind or offshore wind (offshore for this stretch of False Bay
is roughly a NW-N-NE component, since the coast here faces generally SE/S) —
onshore wind above ~15-20km/h should count heavily against a session.
Mid-to-high tide is generally preferred over dead low, since these are beach
breaks that tend to go flat/close out harder at low tide, but this should be
weighed against each spot's known character, not applied as a rigid rule.
"""

# --- Forecast window ---
FORECAST_DAYS = 5

# --- API keys / secrets (from environment) ---
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY")
STORMGLASS_API_KEY = os.environ.get("STORMGLASS_API_KEY")

GOOGLE_CLIENT_ID = os.environ.get("GOOGLE_CLIENT_ID")
GOOGLE_CLIENT_SECRET = os.environ.get("GOOGLE_CLIENT_SECRET")
GOOGLE_REFRESH_TOKEN = os.environ.get("GOOGLE_REFRESH_TOKEN")

# Which calendar to write to. "primary" is your main Google Calendar.
GOOGLE_CALENDAR_ID = os.environ.get("GOOGLE_CALENDAR_ID", "primary")

# Model to use for the agent loop
MODEL = "claude-sonnet-4-6"

# --- Email reporting (always sent after each run, not agent-callable) ---
EMAIL_FROM = os.environ.get("EMAIL_FROM")
EMAIL_APP_PASSWORD = os.environ.get("EMAIL_APP_PASSWORD")
EMAIL_TO = os.environ.get("EMAIL_TO", EMAIL_FROM)
