"""
Run this ONCE, locally, in VS Code's terminal -- not in GitHub Actions.

It walks you through the Google consent screen in your browser, then prints
out a GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET, and GOOGLE_REFRESH_TOKEN.
Copy those three values into your GitHub repo's Actions secrets
(Settings -> Secrets and variables -> Actions -> New repository secret).
After this, calendar_auth.py and the client_secret_*.json file are no
longer needed by the running agent -- only the three values above are.

Usage:
    python calendar_auth.py /path/to/your/client_secret_XXXX.json
"""

import sys

from google_auth_oauthlib.flow import InstalledAppFlow

SCOPES = ["https://www.googleapis.com/auth/calendar.events"]


def main():
    if len(sys.argv) != 2:
        print("Usage: python calendar_auth.py /path/to/client_secret_XXXX.json")
        sys.exit(1)

    client_secret_path = sys.argv[1]

    flow = InstalledAppFlow.from_client_secrets_file(client_secret_path, SCOPES)
    # Opens your default browser, you log in and click Allow.
    # If you see an "unverified app" warning, click "Advanced" -> "Go to
    # surf-agent-desktop (unsafe)" -- expected for a personal script.
    creds = flow.run_local_server(port=0)

    print("\n" + "=" * 70)
    print("SUCCESS. Copy these into your GitHub repo's Actions secrets:")
    print("=" * 70)
    print(f"GOOGLE_CLIENT_ID={creds.client_id}")
    print(f"GOOGLE_CLIENT_SECRET={creds.client_secret}")
    print(f"GOOGLE_REFRESH_TOKEN={creds.refresh_token}")
    print("=" * 70)

    if not creds.refresh_token:
        print(
            "\n[warning] No refresh_token returned. This usually means you've "
            "authorized this app before and Google didn't re-issue one. Go to "
            "https://myaccount.google.com/permissions, remove access for this "
            "app, and run this script again."
        )


if __name__ == "__main__":
    main()
