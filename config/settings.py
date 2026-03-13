"""
Configuration loader for Slackbot HR Ops.

Loads from environment variables with defaults where appropriate.
Extends the existing HR automation config where needed.
"""
import os
import sys
from pathlib import Path
from typing import Any, List, Optional

# Add hr_automation to path for imports
hr_automation_path = Path(__file__).parent.parent / "hr_automation"
if hr_automation_path.exists():
    sys.path.insert(0, str(hr_automation_path / "server"))


def _load_env_file():
    """Load .env file from project root."""
    from dotenv import load_dotenv

    project_root = Path(__file__).parent.parent
    env_path = project_root / ".env"

    # Also try loading from the linked hr_automation directory
    hr_env_path = hr_automation_path / ".env"

    # Load both env files (project .env takes precedence)
    if hr_env_path.exists():
        load_dotenv(hr_env_path)
    if env_path.exists():
        load_dotenv(env_path, override=True)


_load_env_file()


def _parse_list(value: str) -> List[str]:
    """Parse comma-separated string into list, trimming whitespace."""
    if not value:
        return []
    return [item.strip() for item in value.split(",") if item.strip()]


class Config:
    """Application configuration loaded from environment variables."""

    # =====================================================
    # Anthropic Claude API
    # =====================================================
    ANTHROPIC_API_KEY: str = os.environ.get("ANTHROPIC_API_KEY", "")

    # =====================================================
    # Slack Bot Configuration
    # =====================================================
    SLACK_BOT_TOKEN: str = os.environ.get("SLACK_BOT_TOKEN", "")
    SLACK_SIGNING_SECRET: str = os.environ.get("SLACK_SIGNING_SECRET", "")
    SLACK_APP_LEVEL_TOKEN: str = os.environ.get("SLACK_APP_LEVEL_TOKEN", "")
    SLACK_HR_CHANNEL: str = os.environ.get("SLACK_HR_CHANNEL", "hr-operations")
    SLACK_HR_CHANNEL_ID: str = os.environ.get("SLACK_HR_CHANNEL_ID", "")

    # HR Team User IDs (comma-separated list)
    HR_TEAM_USER_IDS: List[str] = _parse_list(
        os.environ.get("HR_TEAM_USER_IDS", "")
    )

    # =====================================================
    # Google Workspace (from existing HR automation)
    # =====================================================
    CONTRACT_TEMPLATE_DOC_ID: str = os.environ.get("CONTRACT_TEMPLATE_DOC_ID", "")
    CONTRACTS_FOLDER_ID: str = os.environ.get("CONTRACTS_FOLDER_ID", "")
    GMAIL_SENDER: str = os.environ.get("GMAIL_SENDER", "")

    # Employee Data (Google Sheets)
    EMPLOYEE_SHEET_ID: str = os.environ.get(
        "EMPLOYEE_SHEET_ID",
        "1VbRZ4q1VMxrwnDJGwVN9w1sUOBBWHmBf9yXRT0OAY4g"
    )
    EMPLOYEE_SHEET_NAME: str = os.environ.get("EMPLOYEE_SHEET_NAME", "Active Employees")
    JD_FOLDER_ID: str = os.environ.get("JD_FOLDER_ID", "")

    # =====================================================
    # Database
    # =====================================================
    DB_PATH: str = os.environ.get("DB_PATH", "hr_automation.db")

    # =====================================================
    # Server Configuration
    # =====================================================
    FLASK_HOST: str = os.environ.get("FLASK_HOST", "127.0.0.1")
    FLASK_PORT: int = int(os.environ.get("FLASK_PORT", "5000"))
    FLASK_DEBUG: bool = os.environ.get("FLASK_DEBUG", "false").lower() == "true"

    # =====================================================
    # Logging
    # =====================================================
    LOG_LEVEL: str = os.environ.get("LOG_LEVEL", "INFO")
    LOG_FILE: str = os.environ.get("LOG_FILE", "logs/slackbot.log")

    # =====================================================
    # Agent SDK Configuration
    # =====================================================
    CONVERSATION_TIMEOUT_MINUTES: int = int(
        os.environ.get("CONVERSATION_TIMEOUT_MINUTES", "30")
    )

    # =====================================================
    # Onboarding Configuration
    # =====================================================
    ONBOARDING_TEMPLATE_KEY: str = os.environ.get(
        "ONBOARDING_TEMPLATE_KEY", "internship_offer"
    )

    @classmethod
    def validate(cls) -> List[str]:
        """
        Validate required configuration values.

        Returns:
            List of missing required config keys
        """
        required = [
            "ANTHROPIC_API_KEY",
            "SLACK_BOT_TOKEN",
            "SLACK_SIGNING_SECRET",
            "GMAIL_SENDER",
        ]

        missing = []
        for key in required:
            if not getattr(cls, key):
                missing.append(key)

        return missing

    @classmethod
    def is_hr_team_member(cls, user_id: str) -> bool:
        """
        Check if a user is an HR team member.

        Args:
            user_id: Slack user ID (e.g., "U123456")

        Returns:
            True if user is in HR team
        """
        return user_id in cls.HR_TEAM_USER_IDS


# Singleton instance
_config: Optional[Config] = None


def get_config() -> Config:
    """Get the singleton configuration instance."""
    global _config
    if _config is None:
        # Validate on first access
        missing = Config.validate()
        if missing:
            raise ValueError(
                f"Missing required configuration: {', '.join(missing)}. "
                "Please set these environment variables in .env"
            )
        _config = Config()
    return _config
