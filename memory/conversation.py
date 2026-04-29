"""
MongoDB-based conversation memory backend.
Stores conversations in MongoDB for persistence and scalability.
"""
from typing import Dict, Any, List, Optional
from datetime import datetime

from memory.base import MemoryBackend, SessionMemory, Message
from database import mongo_client


class MongoMemory(MemoryBackend):
    """
    MongoDB implementation of conversation memory.
    Uses the existing MongoDB connection from database.py.
    
    Note: Uses pymongo (synchronous). For async, use motor.
    """

    def __init__(self):
        self.db = mongo_client["agent_db"]
        self.sessions_collection = self.db["sessions"]
        self.messages_collection = self.db["messages"]

    def create_session(self, session_id: str, user_id: Optional[int] = None) -> SessionMemory:
        session = SessionMemory(session_id=session_id, user_id=user_id)
        
        self.sessions_collection.update_one(
            {"session_id": session_id},
            {"$setOnInsert": {
                "session_id": session_id,
                "user_id": user_id,
                "created_at": session.created_at,
                "last_activity": session.last_activity,
                "metadata": {}
            }},
            upsert=True
        )
        
        return session

    def get_session(self, session_id: str) -> Optional[SessionMemory]:
        session_data = self.sessions_collection.find_one(
            {"session_id": session_id}
        )
        
        if not session_data:
            return None

        messages_data = list(self.messages_collection.find(
            {"session_id": session_id}
        ).sort("timestamp", 1))

        session = SessionMemory(
            session_id=session_id,
            user_id=session_data.get("user_id"),
            messages=[Message.from_dict(m) for m in messages_data]
        )
        session.created_at = session_data.get("created_at", datetime.utcnow())
        session.last_activity = session_data.get("last_activity", datetime.utcnow())
        session.metadata = session_data.get("metadata", {})
        
        return session

    def save_message(self, session_id: str, message: Message) -> bool:
        try:
            # Save message
            message_dict = message.to_dict()
            message_dict["session_id"] = session_id
            self.messages_collection.insert_one(message_dict)

            # Update session activity
            self.sessions_collection.update_one(
                {"session_id": session_id},
                {
                    "$set": {"last_activity": datetime.utcnow()},
                    "$inc": {"message_count": 1}
                }
            )
            return True
        except Exception as e:
            print(f"Error saving message: {e}")
            return False

    def get_conversation_history(
        self,
        session_id: str,
        limit: Optional[int] = None
    ) -> List[Message]:
        query = self.messages_collection.find(
            {"session_id": session_id}
        ).sort("timestamp", 1)
        
        if limit:
            query = query.limit(limit)
        
        messages_data = list(query)
        return [Message.from_dict(m) for m in messages_data]

    def delete_session(self, session_id: str) -> bool:
        try:
            self.messages_collection.delete_many({"session_id": session_id})
            self.sessions_collection.delete_one({"session_id": session_id})
            return True
        except Exception as e:
            print(f"Error deleting session: {e}")
            return False

    def list_sessions(self, user_id: Optional[int] = None) -> List[str]:
        query = {}
        if user_id is not None:
            query["user_id"] = user_id
        
        sessions = list(self.sessions_collection.find(
            query,
            {"session_id": 1}
        ).sort("last_activity", -1).limit(100))
        
        return [s["session_id"] for s in sessions]


class InMemoryMemory(MemoryBackend):
    """
    In-memory fallback implementation.
    Useful for development/testing without MongoDB.
    """

    def __init__(self):
        self.sessions: Dict[str, SessionMemory] = {}

    def create_session(self, session_id: str, user_id: Optional[int] = None) -> SessionMemory:
        session = SessionMemory(session_id=session_id, user_id=user_id)
        self.sessions[session_id] = session
        return session

    def get_session(self, session_id: str) -> Optional[SessionMemory]:
        return self.sessions.get(session_id)

    def save_message(self, session_id: str, message: Message) -> bool:
        session = self.get_session(session_id)
        if not session:
            return False
        session.add_message(message)
        return True

    def get_conversation_history(
        self,
        session_id: str,
        limit: Optional[int] = None
    ) -> List[Message]:
        session = self.get_session(session_id)
        if not session:
            return []
        messages = session.messages
        if limit:
            messages = messages[-limit:]
        return messages

    def delete_session(self, session_id: str) -> bool:
        return self.sessions.pop(session_id, None) is not None

    def list_sessions(self, user_id: Optional[int] = None) -> List[str]:
        if user_id is not None:
            return [
                s.session_id for s in self.sessions.values()
                if s.user_id == user_id
            ]
        return list(self.sessions.keys())
