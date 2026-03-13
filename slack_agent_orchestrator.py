"""
Slack Agent Orchestrator - Main entry point for Agent SDK integration.

Routes incoming Slack messages to appropriate HR skills using Claude Agent SDK.
"""
import logging
from typing import Any, Dict, List, Optional

import anthropic
from config.prompts import get_orchestrator_system_prompt
from config.settings import Config
from skills import SKILL_REGISTRY

# Configure logging
logging.basicConfig(
    level=Config.LOG_LEVEL,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class SlackAgentOrchestrator:
    """
    Orchestrates HR skill execution using Claude Agent SDK.

    This class:
    1. Receives user messages from Slack
    2. Routes to appropriate HR skill based on intent
    3. Maintains conversation context across thread messages
    4. Returns structured responses for Slack
    """

    def __init__(self):
        """Initialize the orchestrator."""
        self.client = anthropic.Anthropic(api_key=Config.ANTHROPIC_API_KEY)
        self.system_prompt = get_orchestrator_system_prompt()
        self.skills = list(SKILL_REGISTRY.keys())

    def build_prompt(
        self,
        user_message: str,
        conversation_history: Optional[List[Dict[str, str]]] = None,
        user_context: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        Build the prompt for Claude.

        Args:
            user_message: The user's message
            conversation_history: Previous messages in the thread
            user_context: Additional context (user_id, channel_id, etc.)

        Returns:
            Formatted prompt string
        """
        lines = [user_message]

        # Add conversation context if available
        if conversation_history and len(conversation_history) > 0:
            lines.append("\n\nPrevious conversation:")
            for msg in conversation_history[-10:]:  # Last 10 messages
                role = msg.get("role", "user")
                content = msg.get("content", "")
                lines.append(f"\n{role.capitalize()}: {content}")

        # Add user context
        if user_context:
            context_parts = []
            if user_context.get("user_name"):
                context_parts.append(f"User: {user_context['user_name']}")
            if user_context.get("channel_name"):
                context_parts.append(f"Channel: {user_context['channel_name']}")

            if context_parts:
                lines.append("\n\nContext: " + ", ".join(context_parts))

        # Add available skills reminder
        lines.append(f"\n\nAvailable skills: {', '.join(self.skills)}")

        return "\n".join(lines)

    async def process_message(
        self,
        user_message: str,
        user_id: str,
        channel_id: str,
        conversation_history: Optional[List[Dict[str, str]]] = None,
        user_context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Process a user message through the Agent SDK.

        Args:
            user_message: The user's message text
            user_id: Slack user ID
            channel_id: Slack channel ID
            conversation_history: Previous messages in this thread
            user_context: Additional context (user_name, channel_name, etc.)

        Returns:
            Response dict with:
            - message: Main response text
            - blocks: Optional Slack blocks
            - skill_used: Name of skill that was invoked (if any)
            - error: Error message if something went wrong
        """
        try:
            # Build the prompt
            prompt = self.build_prompt(
                user_message=user_message,
                conversation_history=conversation_history,
                user_context=user_context
            )

            # Query Claude
            response = self.client.messages.create(
                model="claude-sonnet-4-20250514",  # Or "claude-3-5-sonnet-20241022"
                max_tokens=2000,
                system=self.system_prompt,
                messages=[{"role": "user", "content": prompt}]
            )

            # Extract response text
            response_text = response.content[0].text

            # Check if a skill should be invoked
            skill_result = await self._try_invoke_skill(
                user_message=user_message,
                conversation_history=conversation_history,
                response_text=response_text
            )

            if skill_result:
                # Skill was invoked, return its result
                slack_message = skill_result.to_slack_message()
                return {
                    "message": slack_message.get("text", ""),
                    "blocks": slack_message.get("blocks"),
                    "skill_used": skill_result.__class__.__name__,
                    "success": skill_result.success,
                }
            else:
                # No skill invoked, return Claude's response
                return {
                    "message": response_text,
                    "blocks": None,
                    "skill_used": None,
                    "success": True,
                }

        except Exception as e:
            logger.error(f"Error processing message: {e}", exc_info=True)
            return {
                "message": "Sorry, I encountered an error processing your request.",
                "blocks": None,
                "skill_used": None,
                "error": str(e),
                "success": False,
            }

    async def _try_invoke_skill(
        self,
        user_message: str,
        conversation_history: Optional[List[Dict[str, str]]] = None,
        response_text: Optional[str] = None
    ) -> Optional[Any]:
        """
        Try to invoke a skill based on the user's message.

        Args:
            user_message: The user's message
            conversation_history: Previous messages
            response_text: Claude's response (may contain skill invocation)

        Returns:
            SkillResult if a skill was invoked, None otherwise
        """
        # Check for skill invocation patterns
        skill_patterns = {
            "hr_letter": [
                "generate", "letter", "contract", "document",
                "employment contract", "extension", "probation",
                "internship", "traineeship", "offer letter"
            ],
            "onboarding": [
                "onboarding", "welcome email", "new hire",
                "send email"
            ],
        }

        user_lower = user_message.lower()

        # Find matching skill
        matched_skill = None
        for skill_name, patterns in skill_patterns.items():
            if any(pattern in user_lower for pattern in patterns):
                matched_skill = skill_name
                break

        if not matched_skill:
            return None

        # Extract parameters from message
        params = await self._extract_params(
            user_message=user_message,
            skill_name=matched_skill,
            conversation_history=conversation_history
        )

        if not params or "employee_name" not in params:
            # Can't proceed without employee name
            return None

        # Invoke the skill
        skill_instance = SKILL_REGISTRY[matched_skill]()
        return await skill_instance.execute(params)

    async def _extract_params(
        self,
        user_message: str,
        skill_name: str,
        conversation_history: Optional[List[Dict[str, str]]] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Extract parameters for a skill from the user's message.

        Args:
            user_message: The user's message
            skill_name: Name of the skill to extract params for
            conversation_history: Previous messages

        Returns:
            Dict of parameters or None if extraction failed
        """
        # For now, do simple extraction
        # In production, this could use Claude to extract structured params
        params = {}

        # Extract employee name (after "for" keyword)
        if " for " in user_message.lower():
            parts = user_message.lower().split(" for ")
            if len(parts) > 1:
                # Get the name (first few words after "for")
                name_part = parts[1].strip().split()[0:3]  # Up to 3 words
                params["employee_name"] = " ".join(name_part).title()

        # Extract template type for hr_letter
        if skill_name == "hr_letter":
            from skills.hr_letter_skill import HrLetterSkill
            skill = HrLetterSkill()

            for template in skill.TEMPLATE_TYPES:
                if template.replace("_", " ") in user_message.lower():
                    params["template_type"] = template
                    break

            if "template_type" not in params:
                params["template_type"] = "contract_extension"  # Default

        return params if "employee_name" in params else None

    def get_help_message(self) -> str:
        """Get the help message for the bot."""
        from config.prompts import SKILL_DESCRIPTIONS
        return SKILL_DESCRIPTIONS


# Singleton instance
_orchestrator: Optional[SlackAgentOrchestrator] = None


def get_orchestrator() -> SlackAgentOrchestrator:
    """Get the singleton orchestrator instance."""
    global _orchestrator
    if _orchestrator is None:
        _orchestrator = SlackAgentOrchestrator()
    return _orchestrator
