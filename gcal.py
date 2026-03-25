from pathlib import Path
import json
import re
from datetime import date, datetime, timezone, timedelta

CREDS_FILE = Path(__file__).parent / "credentials.json"
TOKEN_FILE  = Path(__file__).parent / "token.json"
SCOPES      = ["https://www.googleapis.com/auth/calendar"]

# ── class detection patterns ─────────────────────────────────────────

# matches: CSC108, MAT137H1, PHYA21, BIO 120, etc.
COURSE_CODE_RE = re.compile(r'\b[A-Z]{2,4}\s?\d{2,4}[A-Z0-9]*\b')

# fallback keyword check if no course code found
CLASS_KEYWORDS = {
    "lecture", "lec", "lab", "tutorial", "tut",
    "seminar", "class", "workshop", "recitation"
}


def is_class_event(event: dict) -> bool:
    """Heuristic: does this calendar event look like a university class?"""
    title = event.get("summary", "")
    if COURSE_CODE_RE.search(title):          # course code found (e.g. CSC108)
        return True
    return any(kw in title.lower() for kw in CLASS_KEYWORDS)


def get_course_name(event: dict) -> str:
    """
    Extract a clean, filesystem-safe course name from an event title.
    Prefers the course code (CSC108) over a slugified full title.
    """
    title = event.get("summary", "Untitled")
    match = COURSE_CODE_RE.search(title)
    if match:
        return match.group(0).replace(" ", "").upper()   # e.g. "CSC108"
    return re.sub(r'[^a-zA-Z0-9]', '_', title).strip('_')


def get_upcoming_classes(days_ahead: int = 7) -> list:
    """Return upcoming events that look like classes."""
    return [e for e in get_upcoming_events(days_ahead) if is_class_event(e)]


def get_classes_starting_soon(window_minutes: int = 15) -> list:
    """
    Return class events whose start time falls within the next window_minutes.
    Skips all-day events (no 'T' in start string).
    """
    now    = datetime.now(timezone.utc)
    cutoff = now + timedelta(minutes=window_minutes)

    upcoming = []
    for e in get_upcoming_classes(days_ahead=1):
        start_str = e.get("start", "")
        if "T" not in start_str:
            continue
        try:
            start_dt = datetime.fromisoformat(start_str.replace("Z", "+00:00"))
            if now <= start_dt <= cutoff:
                upcoming.append({**e, "course": get_course_name(e)})
        except ValueError:
            continue

    return upcoming


def trigger_class_notes(window_minutes: int = 15) -> list:
    """
    Called periodically (or on agenda load) to auto-create note files
    for any class starting within window_minutes.

    Returns a list of note metadata dicts for created notes.
    Stubs out the actual file creation — wire up once notes.py exists.
    """
    created = []
    for cls in get_classes_starting_soon(window_minutes):
        course  = cls["course"]
        start   = cls.get("start", "")
        summary = cls.get("summary", course)

        # TODO (Subtask 1): replace stub with real call once notes.py is ready
        # from notes import create_class_note
        # note = create_class_note(course=course, event_title=summary, start=start)
        # created.append(note)

        # stub — just log for now so you can verify detection is working
        print(f"[gcal] class starting soon → course={course}, event='{summary}', start={start}")
        created.append({"course": course, "event": summary, "start": start, "note": None})

    return created


# ── auth + service ───────────────────────────────────────────────────

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


# ── events ───────────────────────────────────────────────────────────

def get_upcoming_events(days_ahead: int = 7) -> list:
    import db

    if not is_available():
        cached = db.cache_get("gcal_events")
        return json.loads(cached) if cached else []

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

        db.cache_set("gcal_events", json.dumps(events))
        return events

    except Exception:
        cached = db.cache_get("gcal_events")
        if cached:
            print("[gcal] offline — serving cached events")
            return json.loads(cached)
        return []


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
                "end":   {"date": date_str},
            }
        ).execute()
        return True
    except Exception:
        return False


# ── deadline resolver ────────────────────────────────────────────────

def resolve_deadline(text: str, today) -> "date | None":
    if not text:
        return None

    text = text.lower().strip()

    try:
        return date.fromisoformat(text[:10])
    except ValueError:
        pass

    weekdays = ["monday","tuesday","wednesday","thursday","friday","saturday","sunday"]

    if text == "tomorrow": return today + timedelta(days=1)
    if text == "today":    return today

    for i, name in enumerate(weekdays):
        if name in text:
            days_ahead = (i - today.weekday()) % 7
            if days_ahead == 0:
                days_ahead = 7
            if "next" in text:
                days_ahead += 7
            return today + timedelta(days=days_ahead)

    return None