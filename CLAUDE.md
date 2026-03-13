# Slackbot HR Ops - Claude AI Assistant Documentation

This file contains context for Claude Code to understand and work on this project effectively.

## Project Overview

An HR Operations Slackbot that provides conversational access to HR workflows like letter generation and onboarding. Uses thread-based conversations to keep channels clean while maintaining context.

**Location:** `/Users/alanroyantony/Documents/Claude Project/Slackbot HR Ops`

**Status:** 🟡 Partially Working - See `STATUS.md` for current bugs and progress.

## Quick Start for Claude

When working on this project:

1. **Read STATUS.md first** - Contains current bugs, what works, and what needs fixing
2. **Python 3.9+** is required (venv uses Python 3.9)
3. **Activate venv:** `source venv/bin/activate`
4. **Bot runs on:** Socket Mode (no public URL needed)
5. **Main entry point:** `slack_bot.py`

## Critical Files

### Core Application

| File | Purpose | Status |
|------|---------|--------|
| `slack_bot.py` | Main Slack bot entry point | ⚠️ Has bug in response display |
| `slack_agent_orchestrator.py` | Routes messages to skills using Claude API | ✅ Working |
| `config/settings.py` | Environment config loader | ✅ Working |
| `config/prompts.py` | System prompts for Claude | ✅ Working |

### Skills

| File | Purpose | Status |
|------|---------|--------|
| `skills/base_skill.py` | Base class with `SkillResult` dataclass | ⚠️ `to_slack_message()` needs fix |
| `skills/hr_letter_skill.py` | HR letter generation (contract, extension, etc.) | ✅ Working |
| `skills/onboarding_skill.py` | Onboarding email sending | ❓ Untested |

### Utilities

| File | Purpose | Status |
|------|---------|--------|
| `utils/employee_lookup.py` | Fetches employee data from Google Sheets | ✅ Working |
| `utils/permissions.py` | HR team access control via user IDs | ✅ Working |
| `utils/thread_sessions.py` | Thread-based conversation context | ✅ Working |

## Known Bug - Response Not Displayed in Slack

**Symptom:** Bot receives events, processes them (200 OK from Claude API), but response doesn't appear in Slack. Sends fallback: "I processed your request but didn't get a response."

**Root Cause:** The `SkillResult.to_slack_message()` returns `{"blocks": [...]}` without `"text"` key. Then:

```python
# In slack_agent_orchestrator.py line 137
slack_message = skill_result.to_slack_message()
return {
    "message": slack_message.get("text", ""),  # Returns ""!
    "blocks": slack_message.get("blocks"),
    ...
}
```

**Fix Location:** `skills/base_skill.py` lines 31-92 or `slack_bot.py` lines 115-147

**Fix Options:**
1. Add `"text"` field to `to_slack_message()` return value
2. Improve extraction logic in `slack_bot.py` (attempted but untested)
3. Pass blocks directly to Slack API instead of extracting text

## Architecture

```
┌─────────────────┐      ┌──────────────────┐      ┌─────────────────────┐
│ Slack @mention  │ ───> │  slack_bot.py    │ ───> │ ThreadSessionManager │
│  or thread reply│      │  (Socket Mode)   │      │  (context per thread)│
└─────────────────┘      └──────────────────┘      └─────────────────────┘
                                                                │
                                                                ▼
┌─────────────────┐      ┌──────────────────┐      ┌─────────────────────┐
│  Slack Thread   │ <────│ Orchestrator     │ <────│  Claude API         │
│   Response      │      │  (intent detect) │      │  (anthropic SDK)    │
└─────────────────┘      └──────────────────┘      └─────────────────────┘
                                  │
                    ┌─────────────┼─────────────┐
                    ▼             ▼             ▼
              ┌──────────┐  ┌──────────┐  ┌──────────┐
              │hr_letter │  │onboarding│  │  Future  │
              │  skill   │  │  skill   │  │  skills  │
              └──────────┘  └──────────┘  └──────────┘
```

## Key Patterns

### Adding a New Skill

1. Create `skills/your_skill.py`:
```python
from skills.base_skill import BaseSkill, SkillResult

class YourSkill(BaseSkill):
    @property
    def name(self) -> str:
        return "your_skill"

    @property
    def description(self) -> str:
        return "What this skill does"

    async def execute(self, params: dict, session=None) -> SkillResult:
        # Your implementation
        return SkillResult(
            success=True,
            message="Success message",
            details="Optional details"
        )

    def get_required_params(self) -> list[str]:
        return ["param1", "param2"]
```

2. Register in `skills/__init__.py`:
```python
from skills.your_skill import YourSkill

SKILL_REGISTRY = {
    "your_skill": YourSkill,
    # ... existing skills
}
```

3. Add patterns to `slack_agent_orchestrator.py`:
```python
skill_patterns = {
    "your_skill": ["trigger_word", "another_trigger"],
    # ... existing patterns
}
```

### Environment Variables

Required in `.env`:
```bash
# Anthropic Claude API
ANTHROPIC_API_KEY=sk-ant-...

# Slack Bot (Socket Mode)
SLACK_BOT_TOKEN=xoxb-...
SLACK_APP_LEVEL_TOKEN=xapp-...
SLACK_SIGNING_SECRET=...  # Kept for compatibility

# HR Team Access (comma-separated Slack user IDs)
HR_TEAM_USER_IDS=U08483FRUQ4,U123456,U123457

# Google Workspace
CONTRACTS_FOLDER_ID=...
GMAIL_SENDER=hr@yourcompany.com
EMPLOYEE_SHEET_ID=1VbRZ4q1VMxrwnDJGwVN9w1sUOBBWHmBf9yXRT0OAY4g
```

### Slack Bot Events

The bot handles two event types:

1. **`app_mention`** - Initial @bot mention in channel
   - Starts new thread conversation
   - Creates new session
   - Routes to appropriate skill

2. **`message`** - Replies in bot's thread
   - Continues existing conversation
   - Retrieves existing session
   - Maintains context

### Thread-Based Response Pattern

Always respond in thread using `thread_ts`:
```python
app.client.chat_postMessage(
    channel=channel_id,
    thread_ts=thread_ts,  # Critical: respond in thread
    text=message_to_send
)
```

### Async/Sync Integration

The orchestrator is async but Slack Bolt handlers are sync. Use:
```python
import asyncio

loop = asyncio.new_event_loop()
asyncio.set_event_loop(loop)
try:
    result = loop.run_until_complete(orchestrator.process_message(...))
finally:
    loop.close()
```

## Dependencies

Core dependencies in `requirements.txt`:
- `slack-bolt>=1.18.0` - Slack SDK with Socket Mode
- `anthropic>=0.40.0` - Claude API client
- `python-dotenv>=1.0.0` - Environment loading
- `python-docx>=1.1.0` - Document generation
- `openpyxl>=3.1.0` - Excel/Sheets handling

**Note:** There is NO `claude-agent-sdk` PyPI package. Use `anthropic` SDK directly.

## Slack App Configuration

**Required Scopes:**
- `app_mentions:read`
- `chat:write`
- `channels:history`
- `groups:history`

**Event Subscriptions:**
- `app_mention`
- `message.channels`

**Important:** After changing scopes or events, you MUST reinstall the app to the workspace and update the bot token.

## Integration with Existing HR Automation

The bot reuses code from `~/Documents/Claude Project/Google Workspace Automation/hr-automation/`:

- **Employee lookup** from `contract_renewal.py`
- **Document generation** from `docx_templates.py`
- **Email sending** from `gmail_sender.py`
- **Google Sheets** access via `gws` CLI

**Note:** The `hr_automation` symlink was never created. Instead, `sys.path` manipulation in `skills/hr_letter_skill.py` adds the paths dynamically.

## Testing

Run tests:
```bash
pytest
```

Run specific test:
```bash
pytest tests/test_skills.py
```

## Logging

Logs go to:
- **Console:** stdout/stderr
- **File:** `logs/slackbot.log` (currently not writing - see STATUS.md)

To view bot logs when running in background:
```bash
tail -f /private/tmp/claude-501/-Users-alanroyantony-Documents-Claude-Project-Slackbot-HR-Ops/*/tasks/*.output
```

## Common Issues

### Bot not responding to mentions
- Check bot is invited to channel
- Verify Event Subscriptions enabled in Slack App
- Check bot is running: `ps aux | grep slack_bot.py`
- Verify token is current (reinstall app if changed)

### "Access denied" message
- Add user ID to `HR_TEAM_USER_IDS` in `.env`
- User ID format: `U` followed by numbers (e.g., `U08483FRUQ4`)

### Employee not found
- Check `EMPLOYEE_SHEET_ID` in `.env`
- Verify employee name matches Google Sheets exactly
- Check sheet name is "Active Employees"

### Code changes not reflected
- Restart bot after code changes
- Check you're editing the right file (not in venv)
- Virtual environment location: `venv/` in project root

## Development Workflow

1. Make code changes
2. Stop bot if running: `pkill -f slack_bot.py`
3. Start bot: `source venv/bin/activate && python slack_bot.py`
4. Test in Slack
5. Check logs for errors
6. Iterate

## Files to NOT Edit

- `venv/` - Virtual environment (reinstall if needed)
- `__pycache__/` - Python cache (auto-generated)
- `*.pyc` - Compiled Python (auto-generated)

## Future Enhancements

See `STATUS.md` for detailed roadmap. Briefly:
- Fix response display bug (critical)
- Test onboarding skill
- Add leave balance inquiry
- Add holiday request submission
- Production systemd deployment
- Monitoring and alerting

## Related Projects

- **Parent HR Automation:** `~/Documents/Claude Project/Google Workspace Automation/hr-automation/`
- **Claude Commands:** `~/.claude/commands/` (contains `hr-letter.md`)

## Support

For issues or questions:
1. Check `STATUS.md` for known bugs
2. Review logs in console or `logs/slackbot.log`
3. Check Slack App configuration matches requirements
4. Verify all environment variables are set correctly
