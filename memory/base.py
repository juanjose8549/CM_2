"""
Base memory interface for the AI Agent.
Defines the contract for conversation and context memory storage.
"""
from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional
from datetime import datetime


class Message:
    """Represents a single message in a conversation."""
    
    def __init__(
        self,
        role: str,
        content: str,
        timestamp: Optional[datetime] = None,
        metadata: Optional[Dict[str, Any]] = None
    ):
        self.role = role  # 'user', 'assistant', 'tool_call', 'system'
        self.content = content
        self.timestamp = timestamp or datetime.utcnow()
        self.metadata = metadata or {}

    def to_dict(self) -> Dict[str, Any]:
        return {
            "role": self.role,
            "content": self.content,
            "timestamp": self.timestamp.isoformat(),
            "metadata": self.metadata
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Message":
        return cls(
            role=data["role"],
            content=data["content"],
            timestamp=datetime.fromisoformat(data["timestamp"]) if "timestamp" in data else None,
            metadata=data.get("metadata", {})
        )


class SessionMemory:
    """Represents a conversation session with its messages."""
    
    def __init__(
        self,
        session_id: str,
        user_id: Optional[int] = None,
        messages: Optional[List[Message]] = None
    ):
        self.session_id = session_id
        self.user_id = user_id
        self.messages = messages or []
        self.created_at = datetime.utcnow()
        self.last_activity = datetime.utcnow()
        self.metadata: Dict[str, Any] = {}

    def add_message(self, message: Message):
        self.messages.append(message)
        self.last_activity = datetime.utcnow()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "session_id": self.session_id,
            "user_id": self.user_id,
            "messages": [m.to_dict() for m in self.messages],
            "created_at": self.created_at.isoformat(),
            "last_activity": self.last_activity.isoformat(),
            "metadata": self.metadata
        }


class MemoryBackend(ABC):
    """Abstract base class for memory storage backends."""

    @abstractmethod
    async def create_session(self, session_id: str, user_id: Optional[int] = None) -> SessionMemory:
        """Create a new conversation session."""
        pass

    @abstractmethod
    async def get_session(self, session_id: str) -> Optional[SessionMemory]:
        """Retrieve a session by ID."""
        pass

    @abstractmethod
    async def save_message(self, session_id: str, message: Message) -> bool:
        """Save a message to a session."""
        pass

    @abstractmethod
    async def get_conversation_history(
        self,
        session_id: str,
        limit: Optional[int] = None
    ) -> List[Message]:
        """Get conversation history for a session."""
        pass

    @abstractmethod
    async def delete_session(self, session_id: str) -> bool:
        """Delete a session and its messages."""
        pass

    @abstractmethod
    async def list_sessions(self, user_id: Optional[int] = None) -> List[str]:
        """List all session IDs, optionally filtered by user."""
        pass
