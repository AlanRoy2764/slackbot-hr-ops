"""
Permission utilities for Slackbot HR Ops.

Handles access control for HR team members.
"""
from typing import Optional

from config.settings import Config


# User group cache for HR team
_hr_team_group_id: Optional[str] = None


def is_hr_team_member(user_id: str) -> bool:
    """
    Check if a user is an HR team member.

    Args:
        user_id: Slack user ID (e.g., "U123456")

    Returns:
        True if user is in HR team
    """
    return Config.is_hr_team_member(user_id)


def is_hr_channel(channel_id: str) -> bool:
    """
    Check if a channel is the designated HR channel.

    Args:
        channel_id: Slack channel ID (e.g., "C123456")

    Returns:
        True if channel is HR channel
    """
    if not Config.SLACK_HR_CHANNEL_ID:
        # If no specific channel ID set, allow all channels
        return True
    return channel_id == Config.SLACK_HR_CHANNEL_ID


def require_hr_team(user_id: str) -> None:
    """
    Raise an exception if user is not an HR team member.

    Args:
        user_id: Slack user ID

    Raises:
        PermissionError: If user is not in HR team
    """
    if not is_hr_team_member(user_id):
        raise PermissionError(
            f"User {user_id} is not authorized to use this bot. "
            "This bot is only available to HR team members."
        )


def format_access_denied_message() -> str:
    """
    Get the access denied message for Slack.

    Returns:
        Formatted message string
    """
    return (
        "Sorry, this bot is only available to HR team members. "
        "If you believe this is an error, please contact your administrator."
    )
