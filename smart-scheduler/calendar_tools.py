import datetime
import os
from typing import List, Optional, Dict, Any
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow

# If modifying these scopes, delete the file token.json.
SCOPES = ["https://www.googleapis.com/auth/calendar"]

def get_calendar_service():
    """Authenticate and return a Google Calendar API service instance."""
    creds = None
    # Get the directory where this file is located
    current_dir = os.path.dirname(os.path.abspath(__file__))
    token_path = os.path.join(current_dir, "token.json")
    credentials_path = os.path.join(current_dir, "credentials.json")
    
    if os.path.exists(token_path):
        creds = Credentials.from_authorized_user_file(token_path, SCOPES)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(
                credentials_path, SCOPES
            )
            creds = flow.run_local_server(port=0)
        with open(token_path, "w") as token:
            token.write(creds.to_json())
    service = build("calendar", "v3", credentials=creds)
    return service

def find_available_slots(
    duration_minutes: int,
    day: Optional[str] = None,
    time_pref: Optional[str] = None,
    timezone: str = "Asia/Kolkata",
    window_start_iso: Optional[str] = None,
    window_end_iso: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """
    Find available time slots in the user's primary Google Calendar.

    Args:
        duration_minutes: Length of the meeting in minutes.
        day: Optional day string (e.g., "Tuesday").
        time_pref: Optional time preference (e.g., "afternoon").
        timezone: Timezone string.
        window_start_iso: Optional ISO format string for search window start.
        window_end_iso: Optional ISO format string for search window end.

    Returns:
        List of dicts with 'start' and 'end' ISO strings.
    """
    service = get_calendar_service()
    now = datetime.datetime.now().astimezone()
    
    # Parse window start and end from ISO strings if provided
    window_start = datetime.datetime.fromisoformat(window_start_iso) if window_start_iso else None
    window_end = datetime.datetime.fromisoformat(window_end_iso) if window_end_iso else None
    
    if not window_start:
        # Default: today 8am to 8pm
        window_start = now.replace(hour=8, minute=0, second=0, microsecond=0)
    if not window_end:
        window_end = now.replace(hour=20, minute=0, second=0, microsecond=0) + datetime.timedelta(days=7)

    # If day is specified, adjust window to that day
    if day:
        # Map day string to weekday index
        weekdays = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]
        day = day.lower()
        today_idx = now.weekday()
        if day in weekdays:
            target_idx = weekdays.index(day)
            days_ahead = (target_idx - today_idx) % 7
            target_date = now + datetime.timedelta(days=days_ahead)
            window_start = target_date.replace(hour=8, minute=0, second=0, microsecond=0)
            window_end = target_date.replace(hour=20, minute=0, second=0, microsecond=0)

    # If time_pref is specified, adjust window hours
    if time_pref:
        if "morning" in time_pref:
            window_start = window_start.replace(hour=8)
            window_end = window_start.replace(hour=12)
        elif "afternoon" in time_pref:
            window_start = window_start.replace(hour=12)
            window_end = window_start.replace(hour=17)
        elif "evening" in time_pref:
            window_start = window_start.replace(hour=17)
            window_end = window_start.replace(hour=20)

    # Get all events in the window
    events_result = (
        service.events()
        .list(
            calendarId="primary",
            timeMin=window_start.isoformat(),
            timeMax=window_end.isoformat(),
            singleEvents=True,
            orderBy="startTime",
        )
        .execute()
    )
    events = events_result.get("items", [])

    # Build a list of busy intervals
    busy = []
    for event in events:
        start = event["start"].get("dateTime", event["start"].get("date"))
        end = event["end"].get("dateTime", event["end"].get("date"))
        busy.append(
            (
                datetime.datetime.fromisoformat(start),
                datetime.datetime.fromisoformat(end),
            )
        )

    # Find free slots
    slots = []
    search_start = window_start
    search_end = window_end
    min_slot = datetime.timedelta(minutes=duration_minutes)
    busy = sorted(busy, key=lambda x: x[0])
    for b_start, b_end in busy:
        if b_start > search_start and (b_start - search_start) >= min_slot:
            slots.append({"start": search_start.isoformat(), "end": b_start.isoformat()})
        search_start = max(search_start, b_end)
    # Check for slot after last event
    if search_end > search_start and (search_end - search_start) >= min_slot:
        slots.append({"start": search_start.isoformat(), "end": search_end.isoformat()})
    return slots

def create_calendar_event(
    start_iso: str,
    end_iso: str,
    summary: str = "Scheduled Meeting",
    description: str = "",
    attendees: Optional[List[str]] = None,
    timezone: str = "Asia/Kolkata",
) -> Dict[str, Any]:
    """
    Create a new event in the user's primary Google Calendar.

    Args:
        start_iso: ISO string for event start.
        end_iso: ISO string for event end.
        summary: Event title.
        description: Event description.
        attendees: List of attendee emails.

    Returns:
        The created event resource.
    """
    service = get_calendar_service()
    event = {
        "summary": summary,
        "description": description,
        "start": {"dateTime": start_iso, "timeZone": timezone},
        "end": {"dateTime": end_iso, "timeZone": timezone},
    }
    if attendees:
        event["attendees"] = [{"email": email} for email in attendees]
    created_event = service.events().insert(calendarId="primary", body=event).execute()
    return created_event
