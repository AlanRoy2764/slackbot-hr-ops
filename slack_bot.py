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


@app.event("app_mention")
def handle_app_mention(event: Dict[str, Any], logger: logging.Logger) -> None:
    """
    Handle @bot mentions in channels.

    Starts a new thread conversation for each mention.
    """
    try:
        channel_id = event["channel"]
        thread_ts = event["ts"]  # Use message timestamp as thread root
        user_id = event["user"]
        text = event.get("text", "")

        logger.info(
            f"App mention from user {user_id} in channel {channel_id}: {text[:50]}..."
        )

        # Verify HR team access
        if not is_hr_team_member(user_id):
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
        auth_result = app.client.auth_test()
        bot_user_id = auth_result["user_id"]
        clean_text = text.replace(f"<@{bot_user_id}>", "").strip()

        # Handle help command
        if clean_text.lower().strip() in ["help", "hi", "hello"]:
            app.client.chat_postMessage(
                channel=channel_id,
                thread_ts=thread_ts,
                text=SKILL_DESCRIPTIONS
            )
            session.add_message("assistant", SKILL_DESCRIPTIONS)
            return

        # Use orchestrator to process the request
        try:
            import asyncio
            orchestrator = get_orchestrator()

            # Run async orchestrator in sync context
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                result = loop.run_until_complete(orchestrator.process_message(
                    user_message=clean_text,
                    user_id=user_id,
                    channel_id=channel_id,
                    conversation_history=list(session.history),
                    user_context={"user_id": user_id, "channel_id": channel_id}
                ))
            finally:
                loop.close()

            # Debug: Log the result
            logger.info(f"Orchestrator result type: {type(result)}")
            logger.info(f"Orchestrator result keys: {result.keys() if isinstance(result, dict) else 'N/A'}")
            logger.info(f"Orchestrator result: {result}")

            # Extract message from result (try message field first, then blocks)
            message_to_send = result.get("message", "")
            logger.info(f"Initial message_to_send: {message_to_send!r}")

            # If message is empty, try to extract from blocks
            if not message_to_send and result.get("blocks"):
                logger.info(f"Extracting from blocks: {result.get('blocks')}")
                # Extract text from blocks - concatenate all section text
                message_parts = []
                for block in result["blocks"]:
                    if block.get("type") == "section":
                        text_obj = block.get("text", {})
                        if isinstance(text_obj, dict) and "text" in text_obj:
                            message_parts.append(text_obj["text"])
                        elif isinstance(text_obj, str):
                            message_parts.append(text_obj)
                message_to_send = "\n".join(message_parts)
                logger.info(f"Extracted message: {message_to_send!r}")

            # Send response in thread
            if message_to_send:
                logger.info(f"Sending response to Slack (length {len(message_to_send)}): {message_to_send[:100]}...")
                slack_response = app.client.chat_postMessage(
                    channel=channel_id,
                    thread_ts=thread_ts,
                    text=message_to_send
                )
                logger.info(f"Slack API response: {slack_response}")
                session.add_message("assistant", message_to_send)
            else:
                logger.warning(f"No message in result! Result: {result}")
                # Send fallback
                app.client.chat_postMessage(
                    channel=channel_id,
                    thread_ts=thread_ts,
                    text="I processed your request but didn't get a response. Please try again."
                )

            session.add_message("user", clean_text)

        except Exception as e:
            logger.error(f"Orchestrator error: {e}", exc_info=True)
            # Fallback response
            app.client.chat_postMessage(
                channel=channel_id,
                thread_ts=thread_ts,
                text=f"I'd be happy to help with that! I can generate HR letters and send onboarding emails.\n\nCould you tell me more about what you need? For example:\n• Generate a contract extension for [name]\n• Send onboarding email for [name]"
            )
            session.add_message("assistant", "Fallback response")

    except Exception as e:
        logger.error(f"Error handling app_mention: {e}", exc_info=True)


@app.event("message")
def handle_message(event: Dict[str, Any], logger: logging.Logger) -> None:
    """
    Handle regular messages in channels.

    Processes replies in bot threads.
    """
    try:
        # Only handle messages in threads (replies to bot)
        thread_ts = event.get("thread_ts")
        if not thread_ts:
            return

        channel_id = event["channel"]
        user_id = event["user"]
        text = event.get("text", "")

        logger.info(
            f"Thread reply from user {user_id} in thread {thread_ts}: {text[:50]}..."
        )

        # Get the session for this thread
        session_manager = get_session_manager()
        session = session_manager.get(thread_ts)

        if not session:
            # Unknown thread - might be a reply to a message we didn't start
            return

        # Verify HR team access
        if not is_hr_team_member(user_id):
            app.client.chat_postMessage(
                channel=channel_id,
                thread_ts=thread_ts,
                text=format_access_denied_message()
            )
            return

        # Use orchestrator to process the reply
        try:
            import asyncio
            orchestrator = get_orchestrator()

            # Run async orchestrator in sync context
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                result = loop.run_until_complete(orchestrator.process_message(
                    user_message=text,
                    user_id=user_id,
                    channel_id=channel_id,
                    conversation_history=list(session.history),
                    user_context={"user_id": user_id, "channel_id": channel_id}
                ))
            finally:
                loop.close()

            logger.info(f"Thread reply orchestrator result: {result}")

            # Extract message from result
            message_to_send = result.get("message", "")
            if not message_to_send and result.get("blocks"):
                message_parts = []
                for block in result["blocks"]:
                    if block.get("type") == "section":
                        text_obj = block.get("text", {})
                        if isinstance(text_obj, dict) and "text" in text_obj:
                            message_parts.append(text_obj["text"])
                message_to_send = "\n".join(message_parts)

            # Send response in thread
            if message_to_send:
                logger.info(f"Sending thread reply: {message_to_send[:100]}...")
                app.client.chat_postMessage(
                    channel=channel_id,
                    thread_ts=thread_ts,
                    text=message_to_send
                )
                session.add_message("assistant", message_to_send)

            session.add_message("user", text)

        except Exception as e:
            logger.error(f"Orchestrator error: {e}")
            # Fallback response
            app.client.chat_postMessage(
                channel=channel_id,
                thread_ts=thread_ts,
                text=f"I understand. Could you provide more details so I can help you better?"
            )
            session.add_message("assistant", "Fallback response")

    except Exception as e:
        logger.error(f"Error handling message: {e}", exc_info=True)


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
