"""
Tests for thread session management.
"""
import time
import pytest

from utils.thread_sessions import ThreadSession, ThreadSessionManager


class TestThreadSession:
    """Test ThreadSession class."""

    def test_session_creation(self):
        """Test creating a new session."""
        session = ThreadSession(
            thread_ts="1234567890.123456",
            user_id="U123456",
            channel_id="C789012"
        )

        assert session.thread_ts == "1234567890.123456"
        assert session.user_id == "U123456"
        assert session.channel_id == "C789012"
        assert len(session.history) == 0
        assert session.is_stale(timeout_minutes=60) is False

    def test_add_message(self):
        """Test adding messages to history."""
        session = ThreadSession(
            thread_ts="1234567890.123456",
            user_id="U123456",
            channel_id="C789012"
        )

        session.add_message("user", "Hello")
        session.add_message("assistant", "Hi there!")

        assert len(session.history) == 2
        assert session.history[0]["role"] == "user"
        assert session.history[0]["content"] == "Hello"

    def test_get_history_text(self):
        """Test getting formatted history."""
        session = ThreadSession(
            thread_ts="1234567890.123456",
            user_id="U123456",
            channel_id="C789012"
        )

        session.add_message("user", "Hello")
        session.add_message("assistant", "Hi there!")

        history = session.get_history_text()
        assert "User: Hello" in history
        assert "Assistant: Hi there!" in history

    def test_skill_state(self):
        """Test skill-specific state management."""
        session = ThreadSession(
            thread_ts="1234567890.123456",
            user_id="U123456",
            channel_id="C789012"
        )

        session.set_skill_state("current_template", "contract_extension")
        session.set_skill_state("step", "gathering_info")

        assert session.get_skill_state("current_template") == "contract_extension"
        assert session.get_skill_state("step") == "gathering_info"
        assert session.get_skill_state("nonexistent") is None

    def test_is_stale(self):
        """Test session staleness detection."""
        session = ThreadSession(
            thread_ts="1234567890.123456",
            user_id="U123456",
            channel_id="C789012"
        )

        # Fresh session should not be stale
        assert session.is_stale(timeout_minutes=30) is False

        # Simulate old session
        old_time = time.time() - (31 * 60)  # 31 minutes ago
        session.last_activity = old_time

        assert session.is_stale(timeout_minutes=30) is True


class TestThreadSessionManager:
    """Test ThreadSessionManager class."""

    def test_get_or_create(self):
        """Test getting or creating a session."""
        manager = ThreadSessionManager()

        session1 = manager.get_or_create("1234567890.123456", "U123456", "C789012")
        session2 = manager.get_or_create("1234567890.123456", "U123456", "C789012")

        # Should return the same session
        assert session1 is session2
        assert manager.count() == 1

    def test_get_nonexistent(self):
        """Test getting a non-existent session."""
        manager = ThreadSessionManager()

        session = manager.get("nonexistent")
        assert session is None

    def test_remove(self):
        """Test removing a session."""
        manager = ThreadSessionManager()

        manager.get_or_create("1234567890.123456", "U123456", "C789012")
        assert manager.count() == 1

        manager.remove("1234567890.123456")
        assert manager.count() == 0

    def test_cleanup_stale(self):
        """Test cleaning up stale sessions."""
        manager = ThreadSessionManager()

        session1 = manager.get_or_create("fresh", "U123456", "C789012")
        session2 = manager.get_or_create("stale", "U789012", "C345678")

        # Make session2 stale
        session2.last_activity = time.time() - (31 * 60)

        removed = manager.cleanup_stale(timeout_minutes=30)

        assert removed == 1
        assert manager.get("fresh") is not None
        assert manager.get("stale") is None
