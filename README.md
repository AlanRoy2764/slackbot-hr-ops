# Slackbot HR Ops with Claude Agent SDK

An HR Operations Slackbot that provides conversational access to HR workflows like letter generation and onboarding.

## Features

- **Thread-based conversations** - Keeps main channels clean
- **HR team only access** - Secure permission checks
- **Multi-skill support** - Extensible architecture
- **Context retention** - Maintains conversation state

## Quick Start

### Prerequisites

- Python 3.10+
- Slack App with Bot Token and Signing Secret
- Google Workspace configured with `gws` CLI
- Anthropic API key

### Installation

```bash
# Clone or navigate to project
cd "/Users/alanroyantony/Documents/Claude Project/Slackbot HR Ops"

# Install dependencies
pip install -r requirements.txt

# Set up environment
cp .env.example .env
# Edit .env with your values
```

### Configuration

Edit `.env` with your credentials:

```bash
# Required
ANTHROPIC_API_KEY=sk-ant-...
SLACK_BOT_TOKEN=xoxb-...
SLACK_SIGNING_SECRET=...
HR_TEAM_USER_IDS=U123456,U123457

# Google Workspace
CONTRACTS_FOLDER_ID=...
GMAIL_SENDER=hr@yourcompany.com

# See .env.example for all options
```

### Running the Bot

```bash
# Development (Socket Mode)
python slack_bot.py

# Production (with gunicorn)
gunicorn -w 4 -b 0.0.0.0:5000 slack_bot:app
```

## Usage

### In Slack

1. Invite the bot to your HR channel
2. Tag the bot: `@hr-bot help`
3. Bot will respond in a thread
4. Continue conversation in the thread

### Available Commands

- `@hr-bot generate contract for [name]` - Generate HR letter
- `@hr-bot onboarding for [name]` - Send onboarding email
- `@hr-bot help` - Show available commands

## Architecture

```
Slack Message → Slack Bot → Agent SDK → HR Skills → Response
                                            ↓
                                    Thread-based Context
```

## Skills

### hr_letter
Generate HR letters from templates:
- Contract extensions
- Employment contracts
- Internship offers
- Probation confirmations

### onboarding
Send onboarding emails to new hires.

## Development

### Adding a New Skill

1. Create `skills/your_skill.py`
2. Inherit from `BaseSkill`
3. Implement required methods
4. Register in orchestrator

### Running Tests

```bash
pytest
```

## Troubleshooting

### Bot not responding
- Check `SLACK_BOT_TOKEN` is valid
- Verify bot is invited to the channel
- Check logs in `logs/slackbot.log`

### Permission denied
- Verify user ID is in `HR_TEAM_USER_IDS`
- Check bot has required scopes

### Letter generation fails
- Verify `CONTRACTS_FOLDER_ID` is correct
- Check `gws` CLI is configured
- Ensure templates exist in Drive

## License

MIT
