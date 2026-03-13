"""
Tests for configuration module.
"""
import os
import pytest
from unittest.mock import patch

from config.settings import Config


class TestConfig:
    """Test Config class."""

    def test_parse_list(self):
        """Test _parse_list function."""
        from config.settings import _parse_list

        assert _parse_list("") == []
        assert _parse_list("one") == ["one"]
        assert _parse_list("one, two, three") == ["one", "two", "three"]
        assert _parse_list("one,two,three") == ["one", "two", "three"]
        assert _parse_list(" one , two , three ") == ["one", "two", "three"]

    @patch.dict(os.environ, {
        "ANTHROPIC_API_KEY": "test-key",
        "SLACK_BOT_TOKEN": "xoxb-test",
        "SLACK_SIGNING_SECRET": "test-secret",
        "GMAIL_SENDER": "test@example.com",
        "HR_TEAM_USER_IDS": "U123456,U123457",
    })
    def test_is_hr_team_member(self):
        """Test HR team member check."""
        assert Config.is_hr_team_member("U123456") is True
        assert Config.is_hr_team_member("U123457") is True
        assert Config.is_hr_team_member("U999999") is False

    @patch.dict(os.environ, {
        "ANTHROPIC_API_KEY": "test-key",
        "SLACK_BOT_TOKEN": "xoxb-test",
        "SLACK_SIGNING_SECRET": "test-secret",
        "GMAIL_SENDER": "test@example.com",
        "HR_TEAM_USER_IDS": "",
    })
    def test_validate_missing_required(self):
        """Test validation with missing required config."""
        # Should not raise if all required are present
        Config.validate()

    @patch.dict(os.environ, {
        "ANTHROPIC_API_KEY": "",
        "SLACK_BOT_TOKEN": "xoxb-test",
        "SLACK_SIGNING_SECRET": "test-secret",
        "GMAIL_SENDER": "test@example.com",
    }, clear=False)
    def test_validate_with_missing(self):
        """Test validation with missing values."""
        missing = Config.validate()
        assert "ANTHROPIC_API_KEY" in missing
