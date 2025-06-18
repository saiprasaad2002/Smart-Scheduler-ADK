import datetime
import os
import time
import re
from typing import List, Optional, Dict, Any
from googleapiclient.discovery import build
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
import pytz

SCOPES = ["https://www.googleapis.com/auth/calendar"]

def is_voice_confirmation(user_input: str) -> bool:
    """
    Check if user input is a voice confirmation.
    
    Args:
        user_input (str): User's voice input or text
        
    Returns:
        bool: True if input is a confirmation, False otherwise
    """
    if not user_input:
        return False
    
    # Convert to lowercase for case-insensitive matching
    input_lower = user_input.lower().strip()
    
    # List of confirmation keywords and phrases
    confirmation_keywords = [
        'yes', 'confirm', 'correct', 'okay', 'sure', 'go ahead', 'do it', 
        'proceed', 'create it', 'update it', 'delete it', 'absolutely', 
        'definitely', "that's right", 'sounds good', 'perfect', 'alright', 
        'fine', 'proceed', 'execute', 'go for it', 'yep', 'yeah', 'yup',
        'ok', 'right', 'exactly', 'indeed', 'certainly', 'of course',
        'by all means', 'sure thing', 'no problem', 'absolutely yes',
        'yes please', 'yes go ahead', 'yes do it', 'yes proceed'
    ]
    
    # Check for exact matches
    if input_lower in confirmation_keywords:
        return True
    
    # Check for partial matches (e.g., "yes that's correct")
    for keyword in confirmation_keywords:
        if keyword in input_lower:
            return True
    
    # Check for patterns like "yes, please" or "yes go ahead"
    confirmation_patterns = [
        r'^yes\s+.*',
        r'^confirm\s+.*',
        r'^correct\s+.*',
        r'^okay\s+.*',
        r'^sure\s+.*',
        r'^proceed\s+.*',
        r'^go\s+ahead\s+.*',
        r'^do\s+it\s+.*',
        r'^create\s+it\s+.*',
        r'^update\s+it\s+.*',
        r'^delete\s+it\s+.*'
    ]
    
    for pattern in confirmation_patterns:
        if re.match(pattern, input_lower):
            return True
    
    return False

def get_calendar_service():
    """Authenticate and return a Google Calendar API service instance."""
    creds = None
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

def make_timezone_aware(dt, timezone_str="Asia/Kolkata"):
    """Convert datetime to timezone-aware if it isn't already."""
    if dt.tzinfo is None:
        tz = pytz.timezone(timezone_str)
        return tz.localize(dt)
    return dt

def safe_api_call(func, max_retries=3, delay=1.0):
    """Wrapper to safely execute API calls with retry logic."""
    for attempt in range(max_retries):
        try:
            return func()
        except Exception as e:
            error_msg = str(e).lower()
            if "extra_headers" in error_msg or "websocket" in error_msg:
                if attempt < max_retries - 1:
                    time.sleep(delay * (attempt + 1))
                    continue
                else:
                    return {
                        "error": "Connection issue occurred. Please try again in a moment.",
                        "status": "connection_error",
                        "suggestion": "You can try the action again or ask me to list your events to verify the operation."
                    }
            else:
                raise e
    return None

def find_available_slots(
    duration_minutes: int,
    day: Optional[str] = None,
    time_pref: Optional[str] = None,
    window_start_iso: Optional[str] = None,
    window_end_iso: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """
    Find available time slots in the user's primary Google Calendar.
    
    This tool searches for free time slots in the user's calendar within a specified time window.
    It considers existing events as busy times and returns available slots that can accommodate
    the requested meeting duration.
    
    Args:
        duration_minutes (int): Length of the meeting in minutes (e.g., 30, 60, 90)
        day (str, optional): Specific day to search (e.g., "Monday", "Tuesday", "tomorrow", "next Friday")
        time_pref (str, optional): Time preference like "morning", "afternoon", "evening", "9 AM", "2 PM"
        window_start_iso (str, optional): ISO format start time for search window (e.g., "2024-01-15T08:00:00")
        window_end_iso (str, optional): ISO format end time for search window (e.g., "2024-01-15T18:00:00")
    
    Returns:
        List[Dict[str, Any]]: List of available time slots, each containing:
            - "start": ISO format start time
            - "end": ISO format end time
            - "duration_minutes": Duration of the slot
    
    Examples:
        - Find 30-minute slots on Tuesday: duration_minutes=30, day="Tuesday"
        - Find 1-hour slots in the morning: duration_minutes=60, time_pref="morning"
        - Find 90-minute slots next week: duration_minutes=90, window_start_iso="2024-01-15T08:00:00"
    
    Note:
        All times are in Asia/Kolkata timezone. If no slots are found, returns an empty list.
    """
    def _find_slots():
        service = get_calendar_service()
        now = datetime.datetime.now().astimezone()
        
        window_start = datetime.datetime.fromisoformat(window_start_iso) if window_start_iso else None
        window_end = datetime.datetime.fromisoformat(window_end_iso) if window_end_iso else None
        
        if not window_start:
            window_start = now.replace(hour=8, minute=0, second=0, microsecond=0)
        else:
            window_start = make_timezone_aware(window_start, "Asia/Kolkata")
            
        if not window_end:
            window_end = now.replace(hour=20, minute=0, second=0, microsecond=0) + datetime.timedelta(days=7)
        else:
            window_end = make_timezone_aware(window_end, "Asia/Kolkata")

        # Handle day parameter if provided
        if day is not None:
            weekdays = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]
            day_lower = day.lower()
            today_idx = now.weekday()
            if day_lower in weekdays:
                target_idx = weekdays.index(day_lower)
                days_ahead = (target_idx - today_idx) % 7
                target_date = now + datetime.timedelta(days=days_ahead)
                window_start = target_date.replace(hour=8, minute=0, second=0, microsecond=0)
                window_end = target_date.replace(hour=20, minute=0, second=0, microsecond=0)

        # Handle time preference if provided
        if time_pref is not None:
            if "morning" in time_pref.lower():
                window_start = window_start.replace(hour=8)
                window_end = window_start.replace(hour=12)
            elif "afternoon" in time_pref.lower():
                window_start = window_start.replace(hour=12)
                window_end = window_start.replace(hour=17)
            elif "evening" in time_pref.lower():
                window_start = window_start.replace(hour=17)
                window_end = window_start.replace(hour=20)

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

        busy = []
        for event in events:
            start = event["start"].get("dateTime", event["start"].get("date"))
            end = event["end"].get("dateTime", event["end"].get("date"))
            
            if "T" not in start: 
                start_dt = datetime.datetime.fromisoformat(start + "T00:00:00")
                end_dt = datetime.datetime.fromisoformat(end + "T23:59:59")
                start_dt = make_timezone_aware(start_dt, "Asia/Kolkata")
                end_dt = make_timezone_aware(end_dt, "Asia/Kolkata")
            else:
                start_dt = datetime.datetime.fromisoformat(start)
                end_dt = datetime.datetime.fromisoformat(end)
                if start_dt.tzinfo is None:
                    start_dt = make_timezone_aware(start_dt, "Asia/Kolkata")
                if end_dt.tzinfo is None:
                    end_dt = make_timezone_aware(end_dt, "Asia/Kolkata")
            
            busy.append((start_dt, end_dt))

        slots = []
        search_start = window_start
        search_end = window_end
        min_slot = datetime.timedelta(minutes=duration_minutes)
        busy = sorted(busy, key=lambda x: x[0])
        
        for b_start, b_end in busy:
            if b_start > search_start and (b_start - search_start) >= min_slot:
                slots.append({
                    "start": search_start.isoformat(), 
                    "end": b_start.isoformat(),
                    "duration_minutes": duration_minutes
                })
            search_start = max(search_start, b_end)
        
        if search_end > search_start and (search_end - search_start) >= min_slot:
            slots.append({
                "start": search_start.isoformat(), 
                "end": search_end.isoformat(),
                "duration_minutes": duration_minutes
            })
        
        return slots

    result = safe_api_call(_find_slots)
    if isinstance(result, dict) and "error" in result:
        return result
    return result or []

def create_calendar_event(
    start_iso: str,
    end_iso: str,
    summary: str = "Scheduled Meeting",
    description: str = "",
    attendees: Optional[List[str]] = None,
    confirmed: bool = False,
    skip_conflict_check: bool = False,
) -> Dict[str, Any]:
    """
    Create a new event in the user's primary Google Calendar.
    
    This tool creates a calendar event with the specified details. The event will be created
    in the user's primary calendar and can include attendees, description, and other details.
    By default, it checks for conflicts before creating the event to prevent overlapping events.
    
    Args:
        start_iso (str): ISO format start time (e.g., "2024-01-15T10:00:00")
        end_iso (str): ISO format end time (e.g., "2024-01-15T11:00:00")
        summary (str): Event title/name (e.g., "Team Meeting", "Client Call")
        description (str, optional): Event description or agenda
        attendees (List[str], optional): List of attendee email addresses
        confirmed (bool): Must be True to actually create the event (prevents accidental creation)
        skip_conflict_check (bool): If True, skips conflict checking (use with caution)
    
    Returns:
        Dict[str, Any]: The created event details including:
            - "id": Unique event ID
            - "summary": Event title
            - "start": Start time
            - "end": End time
            - "attendees": List of attendees
            - "htmlLink": Link to view the event
    
    Examples:
        - Create a 1-hour meeting: start_iso="2024-01-15T10:00:00", end_iso="2024-01-15T11:00:00"
        - Create meeting with attendees: attendees=["john@example.com", "jane@example.com"]
        - Book a 30-minute call titled 'Project Review'
    
    Note:
        All times are in Asia/Kolkata timezone. Attendees will receive email invitations.
        The 'confirmed' parameter must be set to True to actually create the event.
        By default, this function checks for conflicts and will not create overlapping events.
    """
    if not confirmed:
        # Check for conflicts before showing confirmation
        if not skip_conflict_check:
            conflict_check = check_time_slot_availability(start_iso, end_iso)
            if not conflict_check.get("available", True):
                conflicting_events = conflict_check.get("conflicting_events", [])
                conflict_list = "\n".join([f"- {event['summary']} ({event['start']} to {event['end']})" for event in conflicting_events])
                return {
                    "message": f"Cannot create event: Time slot conflicts with existing events",
                    "conflicts": conflicting_events,
                    "conflict_details": conflict_list,
                    "status": "conflict_detected",
                    "suggestion": "Please choose a different time or use 'find_available_slots' to see available times."
                }
        
        return {
            "message": "Event creation not confirmed. Please set confirmed=True to create the event.",
            "event_details": {
                "summary": summary,
                "start": start_iso,
                "end": end_iso,
                "description": description,
                "attendees": attendees
            },
            "status": "pending_confirmation",
            "confirmation_prompt": f"Should I create a meeting titled '{summary}' from {start_iso} to {end_iso}? Say 'yes', 'confirm', or 'go ahead' to proceed."
        }
    
    def _create_event():
        service = get_calendar_service()
        
        event = {
            "summary": summary,
            "description": description,
            "start": {"dateTime": start_iso, "timeZone": "Asia/Kolkata"},
            "end": {"dateTime": end_iso, "timeZone": "Asia/Kolkata"},
        }
        if attendees:
            event["attendees"] = [{"email": email} for email in attendees]
        created_event = service.events().insert(calendarId="primary", body=event).execute()
        return created_event

    result = safe_api_call(_create_event)
    if isinstance(result, dict) and "error" in result:
        return result
    return result

def update_calendar_event(
    event_id: str,
    start_iso: Optional[str] = None,
    end_iso: Optional[str] = None,
    summary: Optional[str] = None,
    description: Optional[str] = None,
    attendees: Optional[List[str]] = None,
    confirmed: bool = False,
) -> Dict[str, Any]:
    """
    Update an existing calendar event with new details.
    
    This tool allows you to modify an existing calendar event. You can update the time,
    title, description, or attendees. Only provide the fields you want to change.
    
    Args:
        event_id (str): The unique ID of the event to update
        start_iso (str, optional): New ISO format start time (e.g., "2024-01-15T11:00:00")
        end_iso (str, optional): New ISO format end time (e.g., "2024-01-15T12:00:00")
        summary (str, optional): New event title
        description (str, optional): New event description
        attendees (List[str], optional): New list of attendee email addresses
        confirmed (bool): Must be True to actually update the event (prevents accidental changes)
    
    Returns:
        Dict[str, Any]: The updated event details
    
    Examples:
        - Change meeting time: start_iso="2024-01-15T11:00:00", end_iso="2024-01-15T12:00:00"
        - Update title: summary="Updated Team Meeting"
        - Add attendees: attendees=["newmember@example.com"]
        - Update description: description="Updated agenda for the meeting"
    
    Note:
        All times are in Asia/Kolkata timezone. Attendees will receive updated invitations.
        The 'confirmed' parameter must be set to True to actually update the event.
    """
    if not confirmed:
        changes = []
        if start_iso is not None:
            changes.append(f"start time to {start_iso}")
        if end_iso is not None:
            changes.append(f"end time to {end_iso}")
        if summary is not None:
            changes.append(f"title to '{summary}'")
        if description is not None:
            changes.append(f"description to '{description}'")
        if attendees is not None:
            changes.append(f"attendees to {attendees}")
        
        change_text = ", ".join(changes) if changes else "the event"
        
        return {
            "message": "Event update not confirmed. Please set confirmed=True to update the event.",
            "event_id": event_id,
            "proposed_changes": {
                "start_iso": start_iso,
                "end_iso": end_iso,
                "summary": summary,
                "description": description,
                "attendees": attendees
            },
            "status": "pending_confirmation",
            "confirmation_prompt": f"Should I update {change_text}? Say 'yes', 'confirm', or 'go ahead' to proceed."
        }
    
    def _update_event():
        service = get_calendar_service()
        
        # First, get the current event
        event = service.events().get(calendarId="primary", eventId=event_id).execute()
        
        # Update only the provided fields
        if start_iso is not None:
            event["start"]["dateTime"] = start_iso
        if end_iso is not None:
            event["end"]["dateTime"] = end_iso
        if summary is not None:
            event["summary"] = summary
        if description is not None:
            event["description"] = description
        if attendees is not None:
            event["attendees"] = [{"email": email} for email in attendees]
        
        # Update the event
        updated_event = service.events().update(
            calendarId="primary", 
            eventId=event_id, 
            body=event
        ).execute()
        
        return updated_event

    result = safe_api_call(_update_event)
    if isinstance(result, dict) and "error" in result:
        return result
    return result

def delete_calendar_event(event_id: str, confirmed: bool = False) -> Dict[str, Any]:
    """
    Delete a calendar event from the user's primary calendar.
    
    This tool permanently removes an event from the calendar. This action cannot be undone.
    All attendees will be notified that the event has been cancelled.
    
    Args:
        event_id (str): The unique ID of the event to delete
        confirmed (bool): Must be True to actually delete the event (prevents accidental deletion)
    
    Returns:
        Dict[str, Any]: Confirmation message indicating successful deletion
    
    Examples:
        - Delete event: event_id="abc123def456"
    
    Note:
        This action is permanent and will notify all attendees of the cancellation.
        The 'confirmed' parameter must be set to True to actually delete the event.
    """
    if not confirmed:
        return {
            "message": "Event deletion not confirmed. Please set confirmed=True to delete the event.",
            "event_id": event_id,
            "warning": "This action is permanent and cannot be undone.",
            "status": "pending_confirmation",
            "confirmation_prompt": f"Should I delete event {event_id}? This action is permanent and cannot be undone. Say 'yes', 'confirm', or 'delete it' to proceed."
        }
    
    def _delete_event():
        service = get_calendar_service()
        
        # Delete the event
        service.events().delete(calendarId="primary", eventId=event_id).execute()
        
        return {
            "message": f"Event {event_id} has been successfully deleted",
            "event_id": event_id,
            "status": "deleted"
        }

    result = safe_api_call(_delete_event)
    if isinstance(result, dict) and "error" in result:
        return result
    return result

def list_calendar_events(
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """
    List calendar events from the user's primary calendar.
    
    This tool retrieves events from the user's calendar within a specified date range.
    It's useful for viewing upcoming events or checking the calendar schedule.
    
    Args:
        start_date (str, optional): Start date in ISO format (e.g., "2024-01-15T00:00:00") or date string (e.g., "January 15", "tomorrow")
        end_date (str, optional): End date in ISO format (e.g., "2024-01-31T23:59:59") or date string (e.g., "January 31", "next week")
    
    Returns:
        List[Dict[str, Any]]: List of events, each containing:
            - "id": Event ID
            - "summary": Event title
            - "start": Start time
            - "end": End time
            - "description": Event description
            - "attendees": List of attendees
    
    Examples:
        - List today's events: start_date="2024-01-15T00:00:00", end_date="2024-01-15T23:59:59"
        - List this week's events: start_date="2024-01-15T00:00:00", end_date="2024-01-21T23:59:59"
        - List events on a specific date: start_date="January 15", end_date="January 15"
        - List tomorrow's events: start_date="tomorrow", end_date="tomorrow"
    
    Note:
        All times are in Asia/Kolkata timezone. If no date range is specified, shows upcoming events.
        The function automatically assumes the current year for dates without year specification.
    """
    def _list_events():
        service = get_calendar_service()
        
        def parse_date_string(date_str: str) -> tuple:
            """Parse date string and return start and end ISO format."""
            if not date_str:
                return None, None
                
            # If it's already in ISO format, return as is
            if 'T' in date_str and len(date_str) >= 10:
                start_dt = datetime.datetime.fromisoformat(date_str)
                end_dt = start_dt + datetime.timedelta(days=1)
                return start_dt.isoformat(), end_dt.isoformat()
                
            # Handle relative dates
            now = datetime.datetime.now()
            current_year = now.year
            
            if date_str.lower() == "today":
                start_dt = now.replace(hour=0, minute=0, second=0, microsecond=0)
                end_dt = start_dt + datetime.timedelta(days=1)
                return start_dt.isoformat(), end_dt.isoformat()
            elif date_str.lower() == "tomorrow":
                start_dt = (now + datetime.timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
                end_dt = start_dt + datetime.timedelta(days=1)
                return start_dt.isoformat(), end_dt.isoformat()
            elif date_str.lower() == "yesterday":
                start_dt = (now - datetime.timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
                end_dt = start_dt + datetime.timedelta(days=1)
                return start_dt.isoformat(), end_dt.isoformat()
            
            # Handle day names - first check if today is that day
            weekdays = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]
            if date_str.lower() in weekdays:
                day_idx = weekdays.index(date_str.lower())
                today_idx = now.weekday()
                
                # If today is the requested day, use today
                if day_idx == today_idx:
                    target_date = now
                else:
                    # Otherwise, find the next occurrence
                    days_ahead = (day_idx - today_idx) % 7
                    if days_ahead == 0:  # This shouldn't happen now, but just in case
                        days_ahead = 7
                    target_date = now + datetime.timedelta(days=days_ahead)
                
                start_dt = target_date.replace(hour=0, minute=0, second=0, microsecond=0)
                end_dt = start_dt + datetime.timedelta(days=1)
                return start_dt.isoformat(), end_dt.isoformat()
            
            # Handle "next" day names
            if date_str.lower().startswith("next "):
                day_name = date_str.lower().replace("next ", "")
                if day_name in weekdays:
                    day_idx = weekdays.index(day_name)
                    today_idx = now.weekday()
                    days_ahead = (day_idx - today_idx) % 7 + 7  # Add 7 to get next week
                    target_date = now + datetime.timedelta(days=days_ahead)
                    start_dt = target_date.replace(hour=0, minute=0, second=0, microsecond=0)
                    end_dt = start_dt + datetime.timedelta(days=1)
                    return start_dt.isoformat(), end_dt.isoformat()
            
            # Handle "this" day names
            if date_str.lower().startswith("this "):
                day_name = date_str.lower().replace("this ", "")
                if day_name in weekdays:
                    day_idx = weekdays.index(day_name)
                    today_idx = now.weekday()
                    days_ahead = (day_idx - today_idx) % 7
                    if days_ahead == 0:  # Same day
                        days_ahead = 7
                    target_date = now + datetime.timedelta(days=days_ahead)
                    start_dt = target_date.replace(hour=0, minute=0, second=0, microsecond=0)
                    end_dt = start_dt + datetime.timedelta(days=1)
                    return start_dt.isoformat(), end_dt.isoformat()
            
            # Handle month names with day (e.g., "January 15", "March 20")
            import re
            month_pattern = r"(january|february|march|april|may|june|july|august|september|october|november|december)\s+(\d{1,2})"
            match = re.search(month_pattern, date_str.lower())
            if match:
                month_name = match.group(1)
                day = int(match.group(2))
                months = ["january", "february", "march", "april", "may", "june", 
                         "july", "august", "september", "october", "november", "december"]
                month_idx = months.index(month_name)
                # Assume current year unless explicitly specified
                target_date = datetime.datetime(current_year, month_idx + 1, day)
                start_dt = target_date.replace(hour=0, minute=0, second=0, microsecond=0)
                end_dt = start_dt + datetime.timedelta(days=1)
                return start_dt.isoformat(), end_dt.isoformat()
            
            # If we can't parse it, return None
            return None, None
        
        # Parse start and end dates
        if start_date:
            parsed_start_date, _ = parse_date_string(start_date)
        else:
            parsed_start_date = None
            
        if end_date:
            _, parsed_end_date = parse_date_string(end_date)
        else:
            parsed_end_date = None
        
        # Set default date range if not provided
        if not parsed_start_date:
            parsed_start_date = datetime.datetime.now().replace(hour=0, minute=0, second=0, microsecond=0).isoformat()
        if not parsed_end_date:
            parsed_end_date = (datetime.datetime.now() + datetime.timedelta(days=7)).replace(hour=23, minute=59, second=59, microsecond=999999).isoformat()
        
        # Make dates timezone aware
        start_dt = make_timezone_aware(datetime.datetime.fromisoformat(parsed_start_date), "Asia/Kolkata")
        end_dt = make_timezone_aware(datetime.datetime.fromisoformat(parsed_end_date), "Asia/Kolkata")
        
        events_result = (
            service.events()
            .list(
                calendarId="primary",
                timeMin=start_dt.isoformat(),
                timeMax=end_dt.isoformat(),
                maxResults=10,
                singleEvents=True,
                orderBy="startTime",
            )
            .execute()
        )
        
        events = events_result.get("items", [])
        
        # Format events for better readability
        formatted_events = []
        for event in events:
            formatted_event = {
                "id": event.get("id"),
                "summary": event.get("summary", "No title"),
                "start": event["start"].get("dateTime", event["start"].get("date")),
                "end": event["end"].get("dateTime", event["end"].get("date")),
                "description": event.get("description", ""),
                "attendees": [attendee.get("email") for attendee in event.get("attendees", [])]
            }
            formatted_events.append(formatted_event)
        
        return formatted_events

    result = safe_api_call(_list_events)
    if isinstance(result, dict) and "error" in result:
        return result
    return result or []

def check_time_slot_availability(
    start_iso: str,
    end_iso: str,
) -> Dict[str, Any]:
    """
    Check if a specific time slot is available in the user's calendar.
    
    This tool checks if the specified time slot conflicts with any existing events.
    It's useful for validating event creation requests before actually creating them.
    
    Args:
        start_iso (str): ISO format start time (e.g., "2024-01-15T15:00:00")
        end_iso (str): ISO format end time (e.g., "2024-01-15T16:00:00")
    
    Returns:
        Dict[str, Any]: Availability check result containing:
            - "available": Boolean indicating if the slot is free
            - "conflicting_events": List of events that conflict with this time slot
            - "start_time": The requested start time
            - "end_time": The requested end time
    
    Examples:
        - Check if 3-4 PM tomorrow is free: start_iso="2024-01-16T15:00:00", end_iso="2024-01-16T16:00:00"
        - Validate meeting time before creation
    
    Note:
        All times are in Asia/Kolkata timezone. Returns detailed conflict information if the slot is busy.
    """
    def _check_availability():
        service = get_calendar_service()
        
        # Parse the requested time slot
        requested_start = make_timezone_aware(datetime.datetime.fromisoformat(start_iso), "Asia/Kolkata")
        requested_end = make_timezone_aware(datetime.datetime.fromisoformat(end_iso), "Asia/Kolkata")
        
        # Get events that overlap with the requested time slot
        events_result = (
            service.events()
            .list(
                calendarId="primary",
                timeMin=requested_start.isoformat(),
                timeMax=requested_end.isoformat(),
                singleEvents=True,
                orderBy="startTime",
            )
            .execute()
        )
        
        conflicting_events = []
        for event in events_result.get("items", []):
            event_start = event["start"].get("dateTime", event["start"].get("date"))
            event_end = event["end"].get("dateTime", event["end"].get("date"))
            
            # Parse event times
            if "T" not in event_start:
                event_start_dt = datetime.datetime.fromisoformat(event_start + "T00:00:00")
                event_end_dt = datetime.datetime.fromisoformat(event_end + "T23:59:59")
            else:
                event_start_dt = datetime.datetime.fromisoformat(event_start)
                event_end_dt = datetime.datetime.fromisoformat(event_end)
            
            # Make timezone aware
            event_start_dt = make_timezone_aware(event_start_dt, "Asia/Kolkata")
            event_end_dt = make_timezone_aware(event_end_dt, "Asia/Kolkata")
            
            # Check for overlap
            if (event_start_dt < requested_end and event_end_dt > requested_start):
                conflicting_events.append({
                    "id": event.get("id"),
                    "summary": event.get("summary", "No title"),
                    "start": event_start,
                    "end": event_end,
                    "description": event.get("description", "")
                })
        
        return {
            "available": len(conflicting_events) == 0,
            "conflicting_events": conflicting_events,
            "start_time": start_iso,
            "end_time": end_iso,
            "message": "Time slot is available" if len(conflicting_events) == 0 else f"Time slot conflicts with {len(conflicting_events)} existing event(s)"
        }

    result = safe_api_call(_check_availability)
    if isinstance(result, dict) and "error" in result:
        return result
    return result

def find_events_by_name_and_date(
    event_name: str,
    date: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """
    Find events by name and optionally by date.
    
    This tool searches for events that match the given name and date criteria.
    It's useful for finding specific events to update or delete without needing event IDs.
    
    Args:
        event_name (str): Name or partial name of the event to search for
        date (str, optional): Date to search on (e.g., "tomorrow", "Friday", "January 15")
    
    Returns:
        List[Dict[str, Any]]: List of matching events, each containing:
            - "id": Event ID
            - "summary": Event title
            - "start": Start time
            - "end": End time
            - "description": Event description
    
    Examples:
        - Find all events with "meeting" in the name: event_name="meeting"
        - Find "Team Meeting" on Friday: event_name="Team Meeting", date="Friday"
        - Find "Project Review" tomorrow: event_name="Project Review", date="tomorrow"
    
    Note:
        All times are in Asia/Kolkata timezone. The search is case-insensitive.
    """
    def _find_events():
        service = get_calendar_service()
        
        def parse_date_string(date_str: str) -> tuple:
            """Parse date string and return start and end ISO format."""
            if not date_str:
                return None, None
                
            # If it's already in ISO format, return as is
            if 'T' in date_str and len(date_str) >= 10:
                start_dt = datetime.datetime.fromisoformat(date_str)
                end_dt = start_dt + datetime.timedelta(days=1)
                return start_dt.isoformat(), end_dt.isoformat()
                
            # Handle relative dates
            now = datetime.datetime.now()
            current_year = now.year
            
            if date_str.lower() == "today":
                start_dt = now.replace(hour=0, minute=0, second=0, microsecond=0)
                end_dt = start_dt + datetime.timedelta(days=1)
                return start_dt.isoformat(), end_dt.isoformat()
            elif date_str.lower() == "tomorrow":
                start_dt = (now + datetime.timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
                end_dt = start_dt + datetime.timedelta(days=1)
                return start_dt.isoformat(), end_dt.isoformat()
            elif date_str.lower() == "yesterday":
                start_dt = (now - datetime.timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
                end_dt = start_dt + datetime.timedelta(days=1)
                return start_dt.isoformat(), end_dt.isoformat()
            
            # Handle day names - first check if today is that day
            weekdays = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]
            if date_str.lower() in weekdays:
                day_idx = weekdays.index(date_str.lower())
                today_idx = now.weekday()
                
                # If today is the requested day, use today
                if day_idx == today_idx:
                    target_date = now
                else:
                    # Otherwise, find the next occurrence
                    days_ahead = (day_idx - today_idx) % 7
                    if days_ahead == 0:  # This shouldn't happen now, but just in case
                        days_ahead = 7
                    target_date = now + datetime.timedelta(days=days_ahead)
                
                start_dt = target_date.replace(hour=0, minute=0, second=0, microsecond=0)
                end_dt = start_dt + datetime.timedelta(days=1)
                return start_dt.isoformat(), end_dt.isoformat()
            
            # Handle "next" day names
            if date_str.lower().startswith("next "):
                day_name = date_str.lower().replace("next ", "")
                if day_name in weekdays:
                    day_idx = weekdays.index(day_name)
                    today_idx = now.weekday()
                    days_ahead = (day_idx - today_idx) % 7 + 7  # Add 7 to get next week
                    target_date = now + datetime.timedelta(days=days_ahead)
                    start_dt = target_date.replace(hour=0, minute=0, second=0, microsecond=0)
                    end_dt = start_dt + datetime.timedelta(days=1)
                    return start_dt.isoformat(), end_dt.isoformat()
            
            # Handle "this" day names
            if date_str.lower().startswith("this "):
                day_name = date_str.lower().replace("this ", "")
                if day_name in weekdays:
                    day_idx = weekdays.index(day_name)
                    today_idx = now.weekday()
                    days_ahead = (day_idx - today_idx) % 7
                    if days_ahead == 0:  # Same day
                        days_ahead = 7
                    target_date = now + datetime.timedelta(days=days_ahead)
                    start_dt = target_date.replace(hour=0, minute=0, second=0, microsecond=0)
                    end_dt = start_dt + datetime.timedelta(days=1)
                    return start_dt.isoformat(), end_dt.isoformat()
            
            # Handle month names with day (e.g., "January 15", "March 20")
            import re
            month_pattern = r"(january|february|march|april|may|june|july|august|september|october|november|december)\s+(\d{1,2})"
            match = re.search(month_pattern, date_str.lower())
            if match:
                month_name = match.group(1)
                day = int(match.group(2))
                months = ["january", "february", "march", "april", "may", "june", 
                         "july", "august", "september", "october", "november", "december"]
                month_idx = months.index(month_name)
                # Assume current year unless explicitly specified
                target_date = datetime.datetime(current_year, month_idx + 1, day)
                start_dt = target_date.replace(hour=0, minute=0, second=0, microsecond=0)
                end_dt = start_dt + datetime.timedelta(days=1)
                return start_dt.isoformat(), end_dt.isoformat()
            
            # If we can't parse it, return None
            return None, None
        
        # Parse date if provided
        start_date, end_date = parse_date_string(date) if date else (None, None)
        
        # Set default date range if not provided (next 30 days)
        if not start_date:
            start_date = datetime.datetime.now().replace(hour=0, minute=0, second=0, microsecond=0).isoformat()
        if not end_date:
            end_date = (datetime.datetime.now() + datetime.timedelta(days=30)).replace(hour=23, minute=59, second=59, microsecond=999999).isoformat()
        
        # Make dates timezone aware
        start_dt = make_timezone_aware(datetime.datetime.fromisoformat(start_date), "Asia/Kolkata")
        end_dt = make_timezone_aware(datetime.datetime.fromisoformat(end_date), "Asia/Kolkata")
        
        # Debug information
        debug_info = {
            "search_criteria": {
                "event_name": event_name,
                "date": date,
                "start_date": start_date,
                "end_date": end_date,
                "start_dt": start_dt.isoformat(),
                "end_dt": end_dt.isoformat()
            }
        }
        
        events_result = (
            service.events()
            .list(
                calendarId="primary",
                timeMin=start_dt.isoformat(),
                timeMax=end_dt.isoformat(),
                maxResults=50,
                singleEvents=True,
                orderBy="startTime",
            )
            .execute()
        )
        
        events = events_result.get("items", [])
        
        # Filter events by name (case-insensitive)
        matching_events = []
        event_name_lower = event_name.lower()
        
        for event in events:
            event_summary = event.get("summary", "").lower()
            if event_name_lower in event_summary or event_summary in event_name_lower:
                formatted_event = {
                    "id": event.get("id"),
                    "summary": event.get("summary", "No title"),
                    "start": event["start"].get("dateTime", event["start"].get("date")),
                    "end": event["end"].get("dateTime", event["end"].get("date")),
                    "description": event.get("description", ""),
                    "attendees": [attendee.get("email") for attendee in event.get("attendees", [])]
                }
                matching_events.append(formatted_event)
        
        # Add debug info to result
        result = {
            "events": matching_events,
            "total_events_found": len(events),
            "matching_events_count": len(matching_events),
            "debug": debug_info
        }
        
        return result

    result = safe_api_call(_find_events)
    if isinstance(result, dict) and "error" in result:
        return result
    return result or []

def delete_event_by_name_and_date(
    event_name: str,
    date: Optional[str] = None,
    confirmed: bool = False,
) -> Dict[str, Any]:
    """
    Delete an event by name and optionally by date.
    
    This tool allows users to delete events by specifying the event name and date,
    making it much more user-friendly than requiring event IDs.
    
    Args:
        event_name (str): Name or partial name of the event to delete
        date (str, optional): Date to search on (e.g., "tomorrow", "Friday", "January 15")
        confirmed (bool): Must be True to actually delete the event (prevents accidental deletion)
    
    Returns:
        Dict[str, Any]: Confirmation message indicating successful deletion or list of matching events
    
    Examples:
        - Delete "Team Meeting" on Friday: event_name="Team Meeting", date="Friday"
        - Delete "Project Review" tomorrow: event_name="Project Review", date="tomorrow"
        - Delete all events with "meeting" in the name: event_name="meeting"
    
    Note:
        All times are in Asia/Kolkata timezone. If multiple events match, lists them for user selection.
        The 'confirmed' parameter must be set to True to actually delete the event.
    """
    if not confirmed:
        # First, find matching events
        matching_events_result = find_events_by_name_and_date(event_name, date)
        
        # Handle the new return format
        if isinstance(matching_events_result, dict) and "events" in matching_events_result:
            matching_events = matching_events_result["events"]
            debug_info = matching_events_result.get("debug", {})
        else:
            matching_events = matching_events_result or []
            debug_info = {}
        
        if not matching_events:
            return {
                "message": f"No events found matching '{event_name}'",
                "search_criteria": {"event_name": event_name, "date": date},
                "debug": debug_info,
                "status": "no_events_found",
                "suggestion": "Try searching without date restrictions or check the event name spelling."
            }
        
        if len(matching_events) == 1:
            event = matching_events[0]
            return {
                "message": f"Found 1 event to delete: '{event['summary']}' on {event['start']}",
                "event_details": event,
                "debug": debug_info,
                "status": "pending_confirmation",
                "confirmation_prompt": f"Should I delete '{event['summary']}' scheduled for {event['start']}? Say 'yes', 'confirm', or 'delete it' to proceed."
            }
        else:
            event_list = "\n".join([f"- {event['summary']} on {event['start']} (ID: {event['id']})" for event in matching_events])
            return {
                "message": f"Found {len(matching_events)} events matching '{event_name}':",
                "matching_events": matching_events,
                "debug": debug_info,
                "status": "multiple_events_found",
                "event_list": event_list,
                "confirmation_prompt": f"Please specify which event to delete by providing more details about the event name or date, or use the event ID."
            }
    
    # If confirmed, find and delete the event
    matching_events_result = find_events_by_name_and_date(event_name, date)
    
    # Handle the new return format
    if isinstance(matching_events_result, dict) and "events" in matching_events_result:
        matching_events = matching_events_result["events"]
    else:
        matching_events = matching_events_result or []
    
    if not matching_events:
        return {
            "message": f"No events found matching '{event_name}' to delete",
            "status": "no_events_found"
        }
    
    if len(matching_events) > 1:
        return {
            "message": f"Multiple events found matching '{event_name}'. Please be more specific about which event to delete.",
            "matching_events": matching_events,
            "status": "multiple_events_found"
        }
    
    # Delete the single matching event
    event_to_delete = matching_events[0]
    
    def _delete_event():
        service = get_calendar_service()
        
        # Delete the event
        service.events().delete(calendarId="primary", eventId=event_to_delete["id"]).execute()
        
        return {
            "message": f"Event '{event_to_delete['summary']}' has been successfully deleted",
            "deleted_event": event_to_delete,
            "status": "deleted"
        }

    result = safe_api_call(_delete_event)
    if isinstance(result, dict) and "error" in result:
        return result
    return result

def update_event_by_name_and_date(
    event_name: str,
    date: Optional[str] = None,
    start_iso: Optional[str] = None,
    end_iso: Optional[str] = None,
    summary: Optional[str] = None,
    description: Optional[str] = None,
    attendees: Optional[List[str]] = None,
    confirmed: bool = False,
) -> Dict[str, Any]:
    """
    Update an event by name and optionally by date.
    
    This tool allows users to update events by specifying the event name and date,
    making it much more user-friendly than requiring event IDs.
    
    Args:
        event_name (str): Name or partial name of the event to update
        date (str, optional): Date to search on (e.g., "tomorrow", "Friday", "January 15")
        start_iso (str, optional): New ISO format start time (e.g., "2024-01-15T11:00:00")
        end_iso (str, optional): New ISO format end time (e.g., "2024-01-15T12:00:00")
        summary (str, optional): New event title
        description (str, optional): New event description
        attendees (List[str], optional): New list of attendee email addresses
        confirmed (bool): Must be True to actually update the event (prevents accidental changes)
    
    Returns:
        Dict[str, Any]: The updated event details or confirmation message
    
    Examples:
        - Update "Team Meeting" on Friday to start at 2 PM: event_name="Team Meeting", date="Friday", start_iso="2024-01-19T14:00:00"
        - Change title of "Project Review" tomorrow: event_name="Project Review", date="tomorrow", summary="Updated Project Review"
        - Add attendees to "Weekly Standup": event_name="Weekly Standup", attendees=["john@example.com"]
    
    Note:
        All times are in Asia/Kolkata timezone. If multiple events match, lists them for user selection.
        The 'confirmed' parameter must be set to True to actually update the event.
    """
    if not confirmed:
        # First, find matching events
        matching_events_result = find_events_by_name_and_date(event_name, date)
        
        # Handle the new return format
        if isinstance(matching_events_result, dict) and "events" in matching_events_result:
            matching_events = matching_events_result["events"]
            debug_info = matching_events_result.get("debug", {})
        else:
            matching_events = matching_events_result or []
            debug_info = {}
        
        if not matching_events:
            return {
                "message": f"No events found matching '{event_name}'",
                "search_criteria": {"event_name": event_name, "date": date},
                "debug": debug_info,
                "status": "no_events_found",
                "suggestion": "Try searching without date restrictions or check the event name spelling."
            }
        
        if len(matching_events) == 1:
            event = matching_events[0]
            changes = []
            if start_iso is not None:
                changes.append(f"start time to {start_iso}")
            if end_iso is not None:
                changes.append(f"end time to {end_iso}")
            if summary is not None:
                changes.append(f"title to '{summary}'")
            if description is not None:
                changes.append(f"description to '{description}'")
            if attendees is not None:
                changes.append(f"attendees to {attendees}")
            
            change_text = ", ".join(changes) if changes else "the event"
            
            return {
                "message": f"Found 1 event to update: '{event['summary']}' on {event['start']}",
                "event_details": event,
                "debug": debug_info,
                "proposed_changes": {
                    "start_iso": start_iso,
                    "end_iso": end_iso,
                    "summary": summary,
                    "description": description,
                    "attendees": attendees
                },
                "status": "pending_confirmation",
                "confirmation_prompt": f"Should I update {change_text} for '{event['summary']}'? Say 'yes', 'confirm', or 'update it' to proceed."
            }
        else:
            event_list = "\n".join([f"- {event['summary']} on {event['start']} (ID: {event['id']})" for event in matching_events])
            return {
                "message": f"Found {len(matching_events)} events matching '{event_name}':",
                "matching_events": matching_events,
                "debug": debug_info,
                "status": "multiple_events_found",
                "event_list": event_list,
                "confirmation_prompt": f"Please specify which event to update by providing more details about the event name or date, or use the event ID."
            }
    
    # If confirmed, find and update the event
    matching_events_result = find_events_by_name_and_date(event_name, date)
    
    # Handle the new return format
    if isinstance(matching_events_result, dict) and "events" in matching_events_result:
        matching_events = matching_events_result["events"]
    else:
        matching_events = matching_events_result or []
    
    if not matching_events:
        return {
            "message": f"No events found matching '{event_name}' to update",
            "status": "no_events_found"
        }
    
    if len(matching_events) > 1:
        return {
            "message": f"Multiple events found matching '{event_name}'. Please be more specific about which event to update.",
            "matching_events": matching_events,
            "status": "multiple_events_found"
        }
    
    # Update the single matching event
    event_to_update = matching_events[0]
    
    def _update_event():
        service = get_calendar_service()
        
        # First, get the current event
        event = service.events().get(calendarId="primary", eventId=event_to_update["id"]).execute()
        
        # Update only the provided fields
        if start_iso is not None:
            event["start"]["dateTime"] = start_iso
        if end_iso is not None:
            event["end"]["dateTime"] = end_iso
        if summary is not None:
            event["summary"] = summary
        if description is not None:
            event["description"] = description
        if attendees is not None:
            event["attendees"] = [{"email": email} for email in attendees]
        
        # Update the event
        updated_event = service.events().update(
            calendarId="primary", 
            eventId=event_to_update["id"], 
            body=event
        ).execute()
        
        return updated_event

    result = safe_api_call(_update_event)
    if isinstance(result, dict) and "error" in result:
        return result
    return result

def parse_time_from_natural_language(time_str: str, date_str: Optional[str] = None) -> str:
    """
    Parse time from natural language and convert to ISO format.
    
    This function converts natural language time expressions to ISO format datetime strings.
    
    Args:
        time_str (str): Natural language time (e.g., "2 PM", "3:30 PM", "14:00")
        date_str (str, optional): Date string (e.g., "Friday", "tomorrow", "January 15")
    
    Returns:
        str: ISO format datetime string (e.g., "2024-01-19T14:00:00")
    
    Examples:
        - parse_time_from_natural_language("2 PM", "Friday") → "2024-01-19T14:00:00"
        - parse_time_from_natural_language("3:30 PM", "tomorrow") → "2024-01-16T15:30:00"
        - parse_time_from_natural_language("9 AM") → "2024-01-15T09:00:00" (today)
    
    Note:
        All times are in Asia/Kolkata timezone. If no date is provided, uses today's date.
    """
    import re
    
    # Get the target date
    if date_str:
        # Use the existing date parsing logic
        def parse_date_string(date_str: str) -> tuple:
            if not date_str:
                return None, None
                
            now = datetime.datetime.now()
            current_year = now.year
            
            if date_str.lower() == "today":
                return now.replace(hour=0, minute=0, second=0, microsecond=0).isoformat(), None
            elif date_str.lower() == "tomorrow":
                tomorrow = now + datetime.timedelta(days=1)
                return tomorrow.replace(hour=0, minute=0, second=0, microsecond=0).isoformat(), None
            elif date_str.lower() == "yesterday":
                yesterday = now - datetime.timedelta(days=1)
                return yesterday.replace(hour=0, minute=0, second=0, microsecond=0).isoformat(), None
            
            # Handle day names
            weekdays = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]
            if date_str.lower() in weekdays:
                day_idx = weekdays.index(date_str.lower())
                today_idx = now.weekday()
                
                # If today is the requested day, use today
                if day_idx == today_idx:
                    target_date = now
                else:
                    # Otherwise, find the next occurrence
                    days_ahead = (day_idx - today_idx) % 7
                    if days_ahead == 0:  # This shouldn't happen now, but just in case
                        days_ahead = 7
                    target_date = now + datetime.timedelta(days=days_ahead)
                
                return target_date.replace(hour=0, minute=0, second=0, microsecond=0).isoformat(), None
            
            # Handle "next" day names
            if date_str.lower().startswith("next "):
                day_name = date_str.lower().replace("next ", "")
                if day_name in weekdays:
                    day_idx = weekdays.index(day_name)
                    today_idx = now.weekday()
                    days_ahead = (day_idx - today_idx) % 7 + 7  # Add 7 to get next week
                    target_date = now + datetime.timedelta(days=days_ahead)
                    return target_date.replace(hour=0, minute=0, second=0, microsecond=0).isoformat(), None
            
            # Handle month names with day
            month_pattern = r"(january|february|march|april|may|june|july|august|september|october|november|december)\s+(\d{1,2})"
            match = re.search(month_pattern, date_str.lower())
            if match:
                month_name = match.group(1)
                day = int(match.group(2))
                months = ["january", "february", "march", "april", "may", "june", 
                         "july", "august", "september", "october", "november", "december"]
                month_idx = months.index(month_name)
                target_date = datetime.datetime(current_year, month_idx + 1, day)
                return target_date.replace(hour=0, minute=0, second=0, microsecond=0).isoformat(), None
            
            return None, None
        
        date_iso, _ = parse_date_string(date_str)
        if not date_iso:
            # If we can't parse the date, use today
            target_date = datetime.datetime.now()
        else:
            target_date = datetime.datetime.fromisoformat(date_iso)
    else:
        # Use today's date
        target_date = datetime.datetime.now()
    
    # Parse the time
    time_str = time_str.strip().lower()
    
    # Handle 24-hour format (e.g., "14:00", "15:30")
    if re.match(r'^\d{1,2}:\d{2}$', time_str):
        hour, minute = map(int, time_str.split(':'))
        if hour < 0 or hour > 23 or minute < 0 or minute > 59:
            raise ValueError(f"Invalid time format: {time_str}")
    else:
        # Handle 12-hour format (e.g., "2 PM", "3:30 PM", "9 AM")
        time_pattern = r'^(\d{1,2})(?::(\d{2}))?\s*(am|pm)$'
        match = re.match(time_pattern, time_str)
        if not match:
            raise ValueError(f"Invalid time format: {time_str}")
        
        hour = int(match.group(1))
        minute = int(match.group(2)) if match.group(2) else 0
        period = match.group(3)
        
        if hour < 1 or hour > 12 or minute < 0 or minute > 59:
            raise ValueError(f"Invalid time format: {time_str}")
        
        # Convert to 24-hour format
        if period == 'pm' and hour != 12:
            hour += 12
        elif period == 'am' and hour == 12:
            hour = 0
    
    # Create the datetime object
    result_datetime = target_date.replace(hour=hour, minute=minute, second=0, microsecond=0)
    
    # Make it timezone aware
    result_datetime = make_timezone_aware(result_datetime, "Asia/Kolkata")
    
    return result_datetime.isoformat()
