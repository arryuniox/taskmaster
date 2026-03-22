from pathlib import Path
import json
from datetime import datetime, timezone, timedelta

CREDS_FILE = Path(__file__).parent / "credentials.json"
TOKEN_FILE = Path(__file__).parent / "token.json"
SCOPES = ["https://www.googleapis.com/auth/calendar"]


def is_available() -> bool:
    return CREDS_FILE.exists()


def get_service():
    from google.oauth2.credentials import Credentials
    from google_auth_oauthlib.flow import InstalledAppFlow
    from google.auth.transport.requests import Request
    from googleapiclient.discovery import build

    creds = None
    if TOKEN_FILE.exists():
        creds = Credentials.from_authorized_user_file(TOKEN_FILE, SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(CREDS_FILE, SCOPES)
            creds = flow.run_local_server(port=0)
        TOKEN_FILE.write_text(creds.to_json())

    return build("calendar", "v3", credentials=creds)


def get_upcoming_events(days_ahead: int = 7) -> list:
    """Fetch events for the next N days. Returns [] if offline or unconfigured."""
    if not is_available():
        return []
    try:
        svc = get_service()
        now = datetime.now(timezone.utc)
        end = now + timedelta(days=days_ahead)
        result = svc.events().list(
            calendarId="primary",
            timeMin=now.isoformat(),
            timeMax=end.isoformat(),
            singleEvents=True,
            orderBy="startTime",
            maxResults=20,
        ).execute()
        events = []
        for e in result.get("items", []):
            start = e["start"].get("dateTime") or e["start"].get("date")
            events.append({"summary": e.get("summary", "Untitled"), "start": start})
        return events
    except Exception:
        return []  # silent fail — offline or auth issue


def create_event(title: str, date_str: str, description: str = "") -> bool:
    """Push a task to Google Calendar as an all-day event."""
    if not is_available():
        return False
    try:
        svc = get_service()
        svc.events().insert(
            calendarId="primary",
            body={
                "summary": title,
                "description": description,
                "start": {"date": date_str},
                "end": {"date": date_str},
            }
        ).execute()
        return True
    except Exception:
        return False