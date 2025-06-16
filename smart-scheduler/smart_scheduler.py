from google.adk.agents import LlmAgent
from .calendar_tools import find_available_slots, create_calendar_event
import os


root_agent = LlmAgent(
    name="smart_scheduler",
    model="gemini-2.5-flash",
    description="An agent that helps users find and schedule meetings by interacting with Google Calendar.",
    instruction=(
        "You are a helpful scheduling assistant. "
        "When a user wants to schedule a meeting, ask clarifying questions to determine the meeting duration, preferred day, and time. "
        "Use the 'find_available_slots' tool to check for available times in the user's Google Calendar. "
        "If the user selects a slot, use 'create_calendar_event' to book the meeting. "
        "If no slots are available, suggest alternative times. "
        "Handle ambiguous or complex time requests gracefully and confirm all bookings."
    ),
    tools=[find_available_slots, create_calendar_event],
)

