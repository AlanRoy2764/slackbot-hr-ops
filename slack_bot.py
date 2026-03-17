"""
Slack Bot for HR Operations.

Thread-based Slack bot using Socket Mode.
Responds to @bot mentions in the HR channel.
"""
import asyncio
import logging
import os
from typing import Any, Dict

from dotenv import load_dotenv
from slack_bolt import App
from slack_bolt.adapter.socket_mode import SocketModeHandler

from config.prompts import SKILL_DESCRIPTIONS
from config.settings import Config
from slack_agent_orchestrator import get_orchestrator
from utils.permissions import format_access_denied_message, is_hr_team_member
from utils.thread_sessions import get_session_manager

# Load environment
load_dotenv()

# Configure logging
os.makedirs("logs", exist_ok=True)
logging.basicConfig(
    level=Config.LOG_LEVEL,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(Config.LOG_FILE),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Initialize Slack app
# For Socket Mode, we only need the token (no signing_secret)
app = App(
    token=Config.SLACK_BOT_TOKEN,
)

# ---------------------------------------------------------------------------
# Bot identity helpers
# ---------------------------------------------------------------------------

_bot_user_id: str = ""


def _get_bot_user_id() -> str:
    global _bot_user_id
    if not _bot_user_id:
        _bot_user_id = app.client.auth_test()["user_id"]
    return _bot_user_id


# ---------------------------------------------------------------------------
# Reaction helpers
# ---------------------------------------------------------------------------

def _add_reaction(channel: str, ts: str, emoji: str) -> None:
    try:
        app.client.reactions_add(channel=channel, timestamp=ts, name=emoji)
    except Exception as e:
        logger.debug(f"Could not add reaction {emoji}: {e}")


def _remove_reaction(channel: str, ts: str, emoji: str) -> None:
    try:
        app.client.reactions_remove(channel=channel, timestamp=ts, name=emoji)
    except Exception as e:
        logger.debug(f"Could not remove reaction {emoji}: {e}")


# ---------------------------------------------------------------------------
# Event handlers
# ---------------------------------------------------------------------------

@app.event("app_mention")
def handle_app_mention(event: Dict[str, Any], logger: logging.Logger) -> None:
    """
    Handle @bot mentions in channels.

    Starts a new thread conversation for each mention.
    """
    channel_id = event["channel"]
    event_ts = event["ts"]          # timestamp of the mention itself
    thread_ts = event["ts"]         # use mention as thread root
    user_id = event.get("user", "")
    text = event.get("text", "")

    _add_reaction(channel_id, event_ts, "thinking_face")

    try:
        logger.info(
            f"App mention from user {user_id} in channel {channel_id}: {text[:50]}..."
        )

        # Verify HR team access
        if not is_hr_team_member(user_id):
            _remove_reaction(channel_id, event_ts, "thinking_face")
            _add_reaction(channel_id, event_ts, "x")
            app.client.chat_postMessage(
                channel=channel_id,
                thread_ts=thread_ts,
                text=format_access_denied_message()
            )
            return

        # Create or get session for this thread
        session_manager = get_session_manager()
        session = session_manager.get_or_create(
            thread_ts=thread_ts,
            user_id=user_id,
            channel_id=channel_id
        )

        # Remove bot mention from text
        bot_user_id = _get_bot_user_id()
        clean_text = text.replace(f"<@{bot_user_id}>", "").strip()

        # Handle help command
        if clean_text.lower().strip() in ["help", "hi", "hello"]:
            _remove_reaction(channel_id, event_ts, "thinking_face")
            _add_reaction(channel_id, event_ts, "white_check_mark")
            app.client.chat_postMessage(
                channel=channel_id,
                thread_ts=thread_ts,
                text=SKILL_DESCRIPTIONS
            )
            session.add_message("user", clean_text)
            session.add_message("assistant", SKILL_DESCRIPTIONS)
            return

        # Swap to "processing" reaction
        _remove_reaction(channel_id, event_ts, "thinking_face")
        _add_reaction(channel_id, event_ts, "gear")

        # Use orchestrator to process the request
        orchestrator = get_orchestrator()
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            result = loop.run_until_complete(orchestrator.process_message(
                user_message=clean_text,
                user_id=user_id,
                channel_id=channel_id,
                conversation_history=list(session.history),
                user_context={"user_id": user_id, "channel_id": channel_id},
                session=session,
            ))
        finally:
            loop.close()

        logger.info(f"Orchestrator result: {result}")

        message_to_send = result.get("message", "")
        blocks_to_send = result.get("blocks")

        session.add_message("user", clean_text)

        if message_to_send or blocks_to_send:
            kwargs: Dict[str, Any] = {
                "channel": channel_id,
                "thread_ts": thread_ts,
                "text": message_to_send or "HR Bot response",
            }
            if blocks_to_send:
                kwargs["blocks"] = blocks_to_send
            app.client.chat_postMessage(**kwargs)
            session.add_message("assistant", message_to_send)
            _remove_reaction(channel_id, event_ts, "gear")
            _add_reaction(channel_id, event_ts, "white_check_mark")
        else:
            logger.warning(f"No message in result! Result: {result}")
            app.client.chat_postMessage(
                channel=channel_id,
                thread_ts=thread_ts,
                text="I processed your request but couldn't format a response. Please try again."
            )
            _remove_reaction(channel_id, event_ts, "gear")
            _add_reaction(channel_id, event_ts, "x")

    except Exception as e:
        logger.error(f"Error handling app_mention: {e}", exc_info=True)
        _remove_reaction(channel_id, event_ts, "thinking_face")
        _remove_reaction(channel_id, event_ts, "gear")
        _add_reaction(channel_id, event_ts, "x")
        app.client.chat_postMessage(
            channel=channel_id,
            thread_ts=thread_ts,
            text=(
                "I'd be happy to help with that! I can generate HR letters and send onboarding emails.\n\n"
                "Could you tell me more about what you need? For example:\n"
                "• Generate a contract extension for [name]\n"
                "• Send onboarding email for [name]"
            )
        )


@app.event("message")
def handle_message(event: Dict[str, Any], logger: logging.Logger) -> None:
    """
    Handle regular messages in channels.

    Processes replies in bot threads.
    """
    # Ignore the bot's own messages and system subtypes
    user_id = event.get("user", "")
    if user_id == _get_bot_user_id():
        return
    if event.get("bot_id"):
        return
    if event.get("subtype") in ("bot_message", "message_changed", "message_deleted"):
        return

    # Only handle messages in threads (replies to bot)
    thread_ts = event.get("thread_ts")
    if not thread_ts:
        return

    channel_id = event["channel"]
    text = event.get("text", "")
    event_ts = event["ts"]

    try:
        logger.info(
            f"Thread reply from user {user_id} in thread {thread_ts}: {text[:50]}..."
        )

        # Get the session for this thread
        session_manager = get_session_manager()
        session = session_manager.get(thread_ts)

        if not session:
            # Unknown thread — might be a reply to a message we didn't start
            return

        # Verify HR team access
        if not is_hr_team_member(user_id):
            _add_reaction(channel_id, event_ts, "x")
            app.client.chat_postMessage(
                channel=channel_id,
                thread_ts=thread_ts,
                text=format_access_denied_message()
            )
            return

        _add_reaction(channel_id, event_ts, "gear")

        # Use orchestrator to process the reply
        orchestrator = get_orchestrator()
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            result = loop.run_until_complete(orchestrator.process_message(
                user_message=text,
                user_id=user_id,
                channel_id=channel_id,
                conversation_history=list(session.history),
                user_context={"user_id": user_id, "channel_id": channel_id},
                session=session,
            ))
        finally:
            loop.close()

        logger.info(f"Thread reply orchestrator result: {result}")

        message_to_send = result.get("message", "")
        blocks_to_send = result.get("blocks")

        session.add_message("user", text)

        if message_to_send or blocks_to_send:
            kwargs: Dict[str, Any] = {
                "channel": channel_id,
                "thread_ts": thread_ts,
                "text": message_to_send or "HR Bot response",
            }
            if blocks_to_send:
                kwargs["blocks"] = blocks_to_send
            app.client.chat_postMessage(**kwargs)
            session.add_message("assistant", message_to_send)
            _remove_reaction(channel_id, event_ts, "gear")
            _add_reaction(channel_id, event_ts, "white_check_mark")
        else:
            app.client.chat_postMessage(
                channel=channel_id,
                thread_ts=thread_ts,
                text="I processed your request but couldn't format a response. Please try again."
            )
            _remove_reaction(channel_id, event_ts, "gear")
            _add_reaction(channel_id, event_ts, "x")

    except Exception as e:
        logger.error(f"Error handling message: {e}", exc_info=True)
        _remove_reaction(channel_id, event_ts, "gear")
        _add_reaction(channel_id, event_ts, "x")
        app.client.chat_postMessage(
            channel=channel_id,
            thread_ts=thread_ts,
            text="I understand. Could you provide more details so I can help you better?"
        )


def main():
    """Start the Slack bot in Socket Mode."""
    try:
        # Validate configuration
        missing = Config.validate()
        if missing:
            logger.error(f"Missing required configuration: {', '.join(missing)}")
            logger.error("Please set these environment variables in .env")
            return

        logger.info("Starting HR Operations Slackbot...")
        auth_result = app.client.auth_test()
        logger.info(f"Bot user ID: {auth_result['user_id']}")
        logger.info(f"Connected to workspace: {auth_result['team']}")

        # Start Socket Mode handler
        handler = SocketModeHandler(
            app,
            Config.SLACK_APP_LEVEL_TOKEN
        )

        logger.info("Bot is running! Press Ctrl+C to stop.")
        handler.start()

    except KeyboardInterrupt:
        logger.info("Bot stopped by user")
    except Exception as e:
        logger.error(f"Bot error: {e}", exc_info=True)


if __name__ == "__main__":
    main()
