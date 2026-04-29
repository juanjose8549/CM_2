"""
Base Skill class for the AI Agent.
All agent capabilities must inherit from this class.
"""
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional


class Skill(ABC):
    """Base class for all agent skills/capabilities."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Unique name identifier for the skill."""
        pass

    @abstractmethod
    async def execute(self, params: Dict[str, Any], context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Execute the skill with given parameters.
        
        Args:
            params: Parameters required for execution
            context: Optional shared context (session info, user data, etc.)
        
        Returns:
            Dict with execution results
        """
        pass

    @abstractmethod
    def get_description(self) -> str:
        """
        Human-readable description of what this skill does.
        Used by the LLM to understand when to call this skill.
        """
        pass

    @abstractmethod
    def get_parameters_schema(self) -> Dict[str, Any]:
        """
        JSON Schema for the function parameters.
        Used for LLM function calling.
        
        Returns:
            Dict following OpenAI/Anthropic function calling schema format
        """
        pass

    @property
    def requires_file_upload(self) -> bool:
        """Whether this skill requires a file upload before execution."""
        return False

    @property
    def is_destructive(self) -> bool:
        """Whether this skill modifies data (requires confirmation)."""
        return False
