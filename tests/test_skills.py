"""
Tests for skill modules.
"""
import pytest
from unittest.mock import Mock, patch, AsyncMock

from skills.base_skill import BaseSkill, SkillResult
from skills.hr_letter_skill import HrLetterSkill
from skills.onboarding_skill import OnboardingSkill


class TestSkillResult:
    """Test SkillResult dataclass."""

    def test_success_result(self):
        """Test creating a success result."""
        result = SkillResult(
            success=True,
            message="Success!",
            details="Some details",
        )

        assert result.success is True
        assert result.message == "Success!"
        assert result.details == "Some details"
        assert result.error is None

    def test_to_slack_message_basic(self):
        """Test converting basic result to Slack message."""
        result = SkillResult(
            success=True,
            message="Hello world",
        )

        message = result.to_slack_message()
        assert message["text"] == "Hello world"
        assert "blocks" in message

    def test_to_slack_message_with_error(self):
        """Test converting error result to Slack message."""
        result = SkillResult(
            success=False,
            message="Failed",
            error="Something went wrong",
        )

        message = result.to_slack_message()
        assert "Failed" in str(message["blocks"])
        assert "warning" in str(message["blocks"])


class TestHrLetterSkill:
    """Test HrLetterSkill."""

    def test_name_and_description(self):
        """Test skill metadata."""
        skill = HrLetterSkill()
        assert skill.name == "hr_letter"
        assert "letter" in skill.description.lower()

    def test_required_params(self):
        """Test required parameters."""
        skill = HrLetterSkill()
        assert "employee_name" in skill.get_required_params()
        assert "template_type" in skill.get_required_params()

    def test_optional_params(self):
        """Test optional parameters."""
        skill = HrLetterSkill()
        optional = skill.get_optional_params()
        assert "career_level" in optional
        assert "new_end_date" in optional

    def test_validate_params_missing(self):
        """Test validation with missing params."""
        skill = HrLetterSkill()
        error = skill.validate_params({"employee_name": "John"})
        assert error is not None
        assert "template_type" in error

    def test_validate_params_valid(self):
        """Test validation with valid params."""
        skill = HrLetterSkill()
        error = skill.validate_params({
            "employee_name": "John",
            "template_type": "contract_extension"
        })
        assert error is None

    @pytest.mark.asyncio
    async def test_execute_missing_employee(self):
        """Test execute with non-existent employee."""
        skill = HrLetterSkill()

        with patch('utils.employee_lookup.get_employee_lookup') as mock_lookup:
            mock_lookup.return_value.find_by_name.return_value = None

            result = await skill.execute({
                "employee_name": "Nonexistent",
                "template_type": "contract_extension"
            })

            assert result.success is False
            assert "not found" in result.message.lower()


class TestOnboardingSkill:
    """Test OnboardingSkill."""

    def test_name_and_description(self):
        """Test skill metadata."""
        skill = OnboardingSkill()
        assert skill.name == "onboarding"
        assert "onboarding" in skill.description.lower()

    def test_required_params(self):
        """Test required parameters."""
        skill = OnboardingSkill()
        assert "employee_name" in skill.get_required_params()

    def test_optional_params(self):
        """Test optional parameters."""
        skill = OnboardingSkill()
        optional = skill.get_optional_params()
        assert "start_date" in optional
        assert "include_docs" in optional
        assert "custom_message" in optional
