"""
Pytest configuration and fixtures.
"""
import os
import sys
import pytest

# Add project root to path
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if project_root not in sys.path:
    sys.path.insert(0, project_root)


@pytest.fixture
def mock_env_vars():
    """Mock environment variables for testing."""
    return {
        "ANTHROPIC_API_KEY": "test-key",
        "SLACK_BOT_TOKEN": "xoxb-test",
        "SLACK_SIGNING_SECRET": "test-secret",
        "SLACK_APP_LEVEL_TOKEN": "xapp-test",
        "GMAIL_SENDER": "hr@example.com",
        "HR_TEAM_USER_IDS": "U123456,U123457",
        "EMPLOYEE_SHEET_ID": "test-sheet-id",
        "CONTRACTS_FOLDER_ID": "test-folder-id",
    }
