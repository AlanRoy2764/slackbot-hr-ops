"""
Thread-based session management for Slackbot HR Ops.

Manages conversation context across thread messages.
Each thread has its own isolated conversation state.
"""
import threading
import time
from collections import deque
from dataclasses import dataclass, field
from typing import Any, Deque, Dict, Optional

from config.settings import Config


@dataclass
class ThreadSession:
    """
    A conversation session tied to a specific Slack thread.

    Each session maintains:
    - Conversation history (user and bot messages)
    - User context (who started the conversation)
    - Channel context
    - Timestamp of last activity
    - Any skill-specific state
    """

    thread_ts: str  # Thread timestamp (unique identifier)
    user_id: str  # User who started the conversation
    channel_id: str  # Channel where conversation started
    created_at: float = field(default_factory=time.time)
    last_activity: float = field(default_factory=time.time)
    history: Deque[Dict[str, Any]] = field(default_factory=lambda: deque(maxlen=50))
    skill_state: Dict[str, Any] = field(default_factory=dict)

    def add_message(self, role: str, content: str) -> None:
        """
        Add a message to the conversation history.

        Args:
            role: Either "user" or "assistant"
            content: Message content
        """
        self.history.append({
            "role": role,
            "content": content,
            "timestamp": time.time(),
        })
        self.last_activity = time.time()

    def get_history_text(self, limit: Optional[int] = None) -> str:
        """
        Get conversation history as formatted text.

        Args:
            limit: Maximum number of recent messages to include

        Returns:
            Formatted conversation history
        """
        messages = list(self.history)
        if limit:
            messages = messages[-limit:]

        lines = []
        for msg in messages:
            role = msg["role"].capitalize()
            content = msg["content"]
            lines.append(f"{role}: {content}")

        return "\n\n".join(lines)

    def set_skill_state(self, key: str, value: Any) -> None:
        """Set a skill-specific state value."""
        self.skill_state[key] = value
        self.last_activity = time.time()

    def get_skill_state(self, key: str, default: Any = None) -> Any:
        """Get a skill-specific state value."""
        return self.skill_state.get(key, default)

    def clear_skill_state(self) -> None:
        """Clear all skill-specific state."""
        self.skill_state.clear()
        self.last_activity = time.time()

    def is_stale(self, timeout_minutes: Optional[int] = None) -> bool:
        """
        Check if the session has timed out.

        Args:
            timeout_minutes: Timeout in minutes (uses config default if None)

        Returns:
            True if session is stale
        """
        if timeout_minutes is None:
            timeout_minutes = Config.CONVERSATION_TIMEOUT_MINUTES

        timeout_seconds = timeout_minutes * 60
        return (time.time() - self.last_activity) > timeout_seconds


class ThreadSessionManager:
    """
    Manages thread-based conversation sessions.

    Handles:
    - Creating new sessions
    - Retrieving existing sessions
    - Cleaning up stale sessions
    """

    def __init__(self):
        """Initialize the session manager."""
        self._sessions: Dict[str, ThreadSession] = {}
        self._lock = threading.Lock()

    def get_or_create(
        self,
        thread_ts: str,
        user_id: str,
        channel_id: str
    ) -> ThreadSession:
        """
        Get an existing session or create a new one.

        Args:
            thread_ts: Thread timestamp
            user_id: User ID
            channel_id: Channel ID

        Returns:
            ThreadSession instance
        """
        with self._lock:
            if thread_ts not in self._sessions:
                self._sessions[thread_ts] = ThreadSession(
                    thread_ts=thread_ts,
                    user_id=user_id,
                    channel_id=channel_id,
                )
            else:
                # Update activity on existing session
                self._sessions[thread_ts].last_activity = time.time()

            return self._sessions[thread_ts]

    def get(self, thread_ts: str) -> Optional[ThreadSession]:
        """
        Get an existing session without creating a new one.

        Args:
            thread_ts: Thread timestamp

        Returns:
            ThreadSession instance or None
        """
        with self._lock:
            return self._sessions.get(thread_ts)

    def remove(self, thread_ts: str) -> None:
        """
        Remove a session.

        Args:
            thread_ts: Thread timestamp to remove
        """
        with self._lock:
            self._sessions.pop(thread_ts, None)

    def cleanup_stale(self, timeout_minutes: Optional[int] = None) -> int:
        """
        Remove all stale sessions.

        Args:
            timeout_minutes: Timeout in minutes (uses config default if None)

        Returns:
            Number of sessions removed
        """
        with self._lock:
            stale = [
                ts for ts, session in self._sessions.items()
                if session.is_stale(timeout_minutes)
            ]
            for ts in stale:
                del self._sessions[ts]
            return len(stale)

    def get_all_active(self) -> Dict[str, ThreadSession]:
        """
        Get all non-stale sessions.

        Returns:
            Dictionary of thread_ts to ThreadSession
        """
        with self._lock:
            return {
                ts: session
                for ts, session in self._sessions.items()
                if not session.is_stale()
            }

    def count(self) -> int:
        """Get the total number of sessions (including stale)."""
        with self._lock:
            return len(self._sessions)


# Singleton instance
_session_manager: Optional[ThreadSessionManager] = None


def get_session_manager() -> ThreadSessionManager:
    """Get the singleton ThreadSessionManager instance."""
    global _session_manager
    if _session_manager is None:
        _session_manager = ThreadSessionManager()
    return _session_manager
