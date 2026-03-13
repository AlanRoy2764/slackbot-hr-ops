"""HR Skills for Slackbot HR Ops."""

from .base_skill import BaseSkill, SkillResult
from .hr_letter_skill import HrLetterSkill
from .onboarding_skill import OnboardingSkill

__all__ = [
    "BaseSkill",
    "SkillResult",
    "HrLetterSkill",
    "OnboardingSkill",
]

# Registry of available skills
SKILL_REGISTRY = {
    "hr_letter": HrLetterSkill,
    "onboarding": OnboardingSkill,
}


def get_skill(name: str) -> BaseSkill:
    """Get a skill instance by name."""
    skill_class = SKILL_REGISTRY.get(name)
    if not skill_class:
        raise ValueError(f"Unknown skill: {name}. Available: {list(SKILL_REGISTRY)}")
    return skill_class()


def list_skills() -> list[str]:
    """List all available skill names."""
    return list(SKILL_REGISTRY.keys())
