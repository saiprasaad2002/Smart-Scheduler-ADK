# 🗓️ Smart Scheduler - AI Calendar Assistant

> A calendar assistant that helps you schedule, manage, and organize your Google Calendar using natural language.

[![Made with Google ADK](https://img.shields.io/badge/Built%20with-Google%20ADK-4285F4?style=flat-square&logo=google)](https://google.github.io/adk-docs/)

---

## ✨ What Can It Do?

**🎤 Voice & Text Commands**
- Schedule , Update, Delete meetings using natural language
- Find available time slots
- List your upcoming events

**🛡️ Smart Features**
- Automatically prevents scheduling conflicts
- Understands natural time expressions
- Works in Asia/Kolkata timezone
- Handles connection issues gracefully

---

## 🚀 Quick Start

### 1. Setup
```bash
# Install dependencies
pip install -r requirements.txt

# Get Google Calendar API credentials
# 1. Go to Google Cloud Console
# 2. Enable Google Calendar API
# 3. Create OAuth 2.0 credentials
# 4. Download as 'credentials.json' and place in smart-scheduler/ folder
```

### 2. Run
```bash
adk web or adk run
```

### 3. Use
Just talk or type naturally:
```
"Schedule a meeting tomorrow at 2 PM"
"Update Team Meeting on Friday to start at 3 PM"
"Delete Project Review tomorrow"
"Show my events this week"
"Find available slots for a 1-hour meeting next Tuesday"
```

---

## 💬 How It Works

### Workflow
1. **You speak/type** a natural language request
2. **AI understands** your intent and extracts details
3. **System checks** your calendar for conflicts
4. **Action executes** (schedule/update/delete/find)
5. **You get confirmation** with clear feedback

### Voice Commands
The assistant recognizes these confirmations:
- "yes", "confirm", "go ahead", "do it"
- "create it", "update it", "delete it"
- "sounds good", "perfect", "alright"

### Examples

**Scheduling:**
```
You: "Schedule a team meeting tomorrow at 3 PM"
AI: "✅ Event created successfully! Team Meeting scheduled for tomorrow at 3 PM"
```

**Updating:**
```
You: "Update the client call on Friday to start at 2 PM"
AI: "✅ Event updated successfully! Client Call has been modified"
```

**Deleting:**
```
You: "Delete the project review tomorrow"
AI: "✅ Event deleted successfully! The event has been removed from your calendar"
```

**Finding Slots:**
```
You: "Find available 30-minute slots tomorrow morning"
AI: "I found 3 available slots tomorrow morning: 9:00 AM, 10:30 AM, 11:00 AM"
```

---

## 🔧 Troubleshooting

**Voice Issues:**
- Speak clearly and use recognized confirmation words
- If voice doesn't work, try typing instead
- ADK is not yet in it's full potential when it comes to voice-enabled agentic conversation, so this application's maximum potential is utilized in text-conversation

---

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes (including better prompting or enabling other features for betterment of this agent)
4. Test thoroughly
5. Submit a pull request

---


<div align="center">

**Made with ❤️ using Google ADK**

</div> 
