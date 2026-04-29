"""
Session manager for the AI Agent.
Handles session creation, retrieval, and cleanup.
"""
from typing import Dict, Any, Optional
import uuid

from memory.base import MemoryBackend, SessionMemory, Message
from memory.conversation import MongoMemory, InMemoryMemory


class SessionManager:
    """Manages AI agent sessions - creation, lookup, and cleanup."""

    def __init__(self, use_mongo: bool = True):
        """
        Initialize session manager.
        
        Args:
            use_mongo: If True, uses MongoDB for persistence.
                       If False, uses in-memory storage (better for development/testing).
        """
        self.memory: MemoryBackend = MongoMemory() if use_mongo else InMemoryMemory()
        self._file_store: Dict[str, Dict] = {}  # session_id -> {file_path, filename, content_type}

    def get_or_create_session(
        self,
        session_id: Optional[str] = None,
        user_id: Optional[int] = None
    ) -> SessionMemory:
        """
        Get an existing session or create a new one.
        
        Args:
            session_id: Optional existing session ID
            user_id: Optional user ID for the session
        
        Returns:
            SessionMemory object
        """
        if session_id:
            session = self.memory.get_session(session_id)
            if session:
                return session
        
        # Create new session
        new_session_id = session_id or str(uuid.uuid4())
        return self.memory.create_session(new_session_id, user_id)

    def add_user_message(self, session_id: str, content: str) -> Message:
        """Add a user message to the conversation."""
        message = Message(role="user", content=content)
        self.memory.save_message(session_id, message)
        return message

    def add_assistant_message(self, session_id: str, content: str) -> Message:
        """Add an assistant message to the conversation."""
        message = Message(role="assistant", content=content)
        self.memory.save_message(session_id, message)
        return message

    def add_tool_call_message(
        self,
        session_id: str,
        tool_name: str,
        params: Dict[str, Any],
        result: Dict[str, Any],
        tool_call_id: str = ""
    ) -> Message:
        """Add a tool call record to the conversation."""
        message = Message(
            role="tool_call",
            content=f"Tool '{tool_name}' executed",
            metadata={
                "tool": tool_name,
                "tool_call_id": tool_call_id,
                "params": params,
                "result_data": result,
                "result_success": result.get("success", False)
            }
        )
        self.memory.save_message(session_id, message)
        return message

    def get_history(
        self,
        session_id: str,
        limit: Optional[int] = None
    ):
        """Get conversation history for a session."""
        return self.memory.get_conversation_history(session_id, limit)

    def store_uploaded_file(
        self,
        session_id: str,
        file_path: str,
        filename: str,
        content_type: str
    ):
        """Store reference to an uploaded file for a session."""
        self._file_store[session_id] = {
            "file_path": file_path,
            "filename": filename,
            "content_type": content_type
        }

    def get_uploaded_file(self, session_id: str) -> Optional[Dict]:
        """Get the uploaded file reference for a session."""
        return self._file_store.get(session_id)

    def clear_uploaded_file(self, session_id: str):
        """Clear the uploaded file reference for a session."""
        self._file_store.pop(session_id, None)

    def delete_session(self, session_id: str) -> bool:
        """Delete a session and all its data."""
        self._file_store.pop(session_id, None)
        return self.memory.delete_session(session_id)

    def build_conversation_context(self, session_id: str) -> str:
        """
        Build a summarized context string from conversation history.
        Used for the system prompt.
        """
        messages = self.memory.get_conversation_history(session_id, limit=20)
        
        if not messages:
            return "No hay historial previo en esta conversación."
        
        context_parts = ["Historial reciente de la conversación:"]
        for msg in messages[-10:]:  # Last 10 messages
            prefix = {
                "user": "👤 Usuario",
                "assistant": "🤖 Asistente",
                "tool_call": "🔧 Herramienta",
                "system": "⚙️ Sistema"
            }.get(msg.role, msg.role)
            
            context_parts.append(f"{prefix}: {msg.content[:200]}")
        
        return "\n".join(context_parts)
