"""One-time Gmail OAuth2 setup — run this once to authorise the app."""
from pathlib import Path
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials

SCOPES = [
    "https://www.googleapis.com/auth/gmail.send",
    "https://www.googleapis.com/auth/gmail.readonly",
]

CREDENTIALS_PATH = Path("data/gmail_credentials.json")
TOKEN_PATH = Path("data/gmail_token.json")


def main():
    if not CREDENTIALS_PATH.exists():
        print("""
SETUP STEPS:
1. Go to https://console.cloud.google.com/
2. Create a new project (e.g. "Job Automation")
3. APIs & Services → Enable APIs → search "Gmail API" → Enable
4. APIs & Services → Credentials → Create Credentials → OAuth client ID
5. Application type: Desktop app
6. Download the JSON → save it as:  data/gmail_credentials.json
7. Re-run this script
        """)
        return

    creds = None
    if TOKEN_PATH.exists():
        creds = Credentials.from_authorized_user_file(str(TOKEN_PATH), SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(str(CREDENTIALS_PATH), SCOPES)
            print("\n" + "="*60)
            print("Starting local auth server on port 8080...")
            print("1. The URL below will be printed — copy it into Chrome/Edge on Windows")
            print("2. Sign in and click Allow")
            print("3. Chrome will redirect to localhost:8080 — WSL2 will catch it automatically")
            print("="*60 + "\n")
            creds = flow.run_local_server(port=8080, open_browser=False)
        TOKEN_PATH.write_text(creds.to_json())

    print(f"✓ Gmail authorised. Token saved to {TOKEN_PATH}")
    print("  The app will auto-refresh this token — you won't need to run this again.")


if __name__ == "__main__":
    main()
