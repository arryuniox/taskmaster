from pathlib import Path
import json
import re
from datetime import date, datetime, timezone, timedelta

CREDS_FILE = Path(__file__).parent / "credentials.json"
TOKEN_FILE  = Path(__file__).parent / "token.json"
SCOPES      = ["https://www.googleapis.com/auth/calendar"]

# ── class detection ──────────────────────────────────────────────────

def _get_course_labels() -> list[str]:
    """
    Pull user-defined course labels from the DB.
    Cached loosely — low frequency reads so no perf concern.
    """
    try:
        import db
        return [c["label"].lower() for c in db.get_courses()]
    except Exception:
        return []


def is_class_event(event: dict) -> tuple[bool, str | None]:
    """
    Check if a calendar event matches a user-defined course.
    Returns (is_match, matched_label | None).
    No fallback keywords — only matches what the user explicitly added.
    """
    title  = event.get("summary", "").lower()
    labels = _get_course_labels()
    for label in labels:
        if label in title:           # substring match, case-insensitive
            return True, label
    return False, None


def get_course_name(event: dict) -> str:
    """
    Return a clean, filesystem-safe course name.
    Tries to match user-defined label first, falls back to slugifying the title.
    """
    import db
    title   = event.get("summary", "Untitled")
    courses = db.get_courses()

    # find the first matching course and use its display_name
    for c in courses:
        if c["label"].lower() in title.lower():
            return re.sub(r'[^a-zA-Z0-9]', '_', c["display_name"]).strip('_')

    # fallback: slugify the raw title (no keywords guessed)
    return re.sub(r'[^a-zA-Z0-9]', '_', title).strip('_')


def get_upcoming_classes(days_ahead: int = 7) -> list:
    """Return upcoming events that match a user-defined course."""
    results = []
    for e in get_upcoming_events(days_ahead):
        matched, label = is_class_event(e)
        if matched:
            results.append({**e, "course": get_course_name(e), "matched_label": label})
    return results


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
                upcoming.append(e)   # course + matched_label already attached above
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
