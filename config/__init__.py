"""Configuration module for Slackbot HR Ops."""

from .settings import Config, get_config
from .prompts import get_orchestrator_system_prompt

__all__ = ["Config", "get_config", "get_orchestrator_system_prompt"]
