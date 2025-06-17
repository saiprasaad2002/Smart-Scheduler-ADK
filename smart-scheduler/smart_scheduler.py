from google.adk.agents import LlmAgent
from .calendar_tools import find_available_slots, create_calendar_event
import datetime

current_date = datetime.datetime.now()
current_year = current_date.year
current_month = current_date.month
current_day = current_date.day

root_agent = LlmAgent(
    name="smart_scheduler",
    model="gemini-2.5-pro-preview-05-06", #gemini-2.0-flash-live-001
    description="An agent that helps users find and schedule meetings by interacting with Google Calendar.",
    instruction=(
        "You are a helpful scheduling assistant. The current date is " + current_date.strftime('%B %d, %Y') + f" (year {current_year}). "
        "When a user wants to schedule a meeting, ask clarifying questions to determine the meeting duration, preferred day, and time. "
        "Always assume the current year (" + str(current_year) + ") unless the user explicitly specifies a different year. "
        "When users mention days like 'next Tuesday' or 'this Friday', interpret them relative to today's date. "
        "Use the 'find_available_slots' tool to check for available times in the user's Google Calendar. "
        "If the user selects a slot, use 'create_calendar_event' to book the meeting. "
        "If no slots are available, suggest alternative times. "
        "Handle ambiguous or complex time requests gracefully and confirm all bookings. "
        "Always provide clear, specific dates and times when discussing scheduling options."
    ),
    tools=[find_available_slots, create_calendar_event],
)

