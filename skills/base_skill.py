"""
Base class for all HR skills.

Provides a consistent interface for skill execution.
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class SkillResult:
    """
    Result of a skill execution.

    Attributes:
        success: Whether the skill executed successfully
        message: Main message to display to the user
        details: Additional details (optional)
        next_action: Suggested next action (optional)
        error: Error message if execution failed
        attachments: List of attachments (file URLs, etc.)
    """
    success: bool
    message: str
    details: str = ""
    next_action: Optional[str] = None
    error: Optional[str] = None
    attachments: List[Dict[str, Any]] = field(default_factory=list)

    def to_slack_message(self) -> Dict[str, Any]:
        """
        Convert result to a Slack message format.

        Returns:
            Dictionary suitable for Slack API chat.postMessage
        """
        blocks = []

        # Main message
        if self.message:
            blocks.append({
                "type": "section",
                "text": {"type": "mrkdwn", "text": self.message}
            })

        # Details (if any)
        if self.details:
            blocks.append({
                "type": "section",
                "text": {"type": "mrkdwn", "text": self.details}
            })

        # Error (if any)
        if self.error:
            blocks.append({
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f":warning: *Error:* {self.error}"
                }
            })

        # Attachments (if any)
        if self.attachments:
            attachment_lines = []
            for attachment in self.attachments:
                title = attachment.get("title", "Attachment")
                url = attachment.get("url", "")
                if url:
                    attachment_lines.append(f"• <{url}|{title}>")

            if attachment_lines:
                blocks.append({
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": "*Attachments:*\n" + "\n".join(attachment_lines)
                    }
                })

        # Next action (if any)
        if self.next_action:
            blocks.append({
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"*Next:* {self.next_action}"
                }
            })

        return {"blocks": blocks} if blocks else {"text": self.message}


class BaseSkill(ABC):
    """
    Abstract base class for all HR skills.

    All skills must inherit from this class and implement
    the required methods.
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """Get the skill name."""
        pass

    @property
    @abstractmethod
    def description(self) -> str:
        """Get a short description of what this skill does."""
        pass

    @abstractmethod
    async def execute(
        self,
        params: Dict[str, Any],
        session: Optional[Any] = None
    ) -> SkillResult:
        """
        Execute the skill with given parameters.

        Args:
            params: Skill-specific parameters
            session: Optional thread session for context

        Returns:
            SkillResult with outcome
        """
        pass

    @abstractmethod
    def get_required_params(self) -> List[str]:
        """
        Get list of required parameter names.

        Returns:
            List of parameter names that must be provided
        """
        pass

    def get_optional_params(self) -> List[str]:
        """
        Get list of optional parameter names.

        Returns:
            List of optional parameter names
        """
        return []

    def validate_params(self, params: Dict[str, Any]) -> Optional[str]:
        """
        Validate skill parameters.

        Args:
            params: Parameters to validate

        Returns:
            Error message if validation fails, None if valid
        """
        required = self.get_required_params()
        missing = [p for p in required if p not in params or not params.get(p)]

        if missing:
            return f"Missing required parameters: {', '.join(missing)}"

        return None

    def format_help(self) -> str:
        """
        Format help text for this skill.

        Returns:
            Formatted help string
        """
        lines = [
            f"*{self.name}*",
            f"{self.description}",
            "",
            "*Required parameters:*",
        ]

        required = self.get_required_params()
        if required:
            for param in required:
                lines.append(f"• `{param}`")
        else:
            lines.append("None")

        optional = self.get_optional_params()
        if optional:
            lines.append("")
            lines.append("*Optional parameters:*")
            for param in optional:
                lines.append(f"• `{param}`")

        return "\n".join(lines)
