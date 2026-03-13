"""
Tests for permission utilities.
"""
import os
import pytest
from unittest.mock import patch

from utils.permissions import (
    is_hr_team_member,
    is_hr_channel,
    require_hr_team,
    format_access_denied_message
)


class TestPermissions:
    """Test permission utilities."""

    @patch.dict(os.environ, {
        "HR_TEAM_USER_IDS": "U123456,U123457,U123458",
    }, clear=False)
    def test_is_hr_team_member(self):
        """Test HR team member check."""
        from config.settings import Config
        # Reload to pick up new env var
        import importlib
        import config.settings
        importlib.reload(config.settings)
        from config.settings import Config

        assert Config.is_hr_team_member("U123456") is True
        assert Config.is_hr_team_member("U123457") is True
        assert Config.is_hr_team_member("U999999") is False

    def test_is_hr_channel_no_id_set(self):
        """Test channel check when no specific ID is set."""
        with patch('config.settings.Config.SLACK_HR_CHANNEL_ID', ""):
            assert is_hr_channel("C123456") is True

    def test_is_hr_channel_with_id(self):
        """Test channel check with specific ID set."""
        with patch('config.settings.Config.SLACK_HR_CHANNEL_ID', "C123456"):
            assert is_hr_channel("C123456") is True
            assert is_hr_channel("C789012") is False

    @patch('utils.permissions.is_hr_team_member', return_value=False)
    def test_require_hr_team_denied(self, mock_check):
        """Test require_hr_team raises for non-member."""
        with pytest.raises(PermissionError, match="not authorized"):
            require_hr_team("U999999")

    @patch('utils.permissions.is_hr_team_member', return_value=True)
    def test_require_hr_team_allowed(self, mock_check):
        """Test require_hr_team passes for member."""
        # Should not raise
        require_hr_team("U123456")

    def test_format_access_denied_message(self):
        """Test access denied message formatting."""
        message = format_access_denied_message()
        assert "HR team members" in message
        assert "administrator" in message
