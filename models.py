from sqlalchemy import Column, Integer, String, Boolean, DateTime
from pydantic import BaseModel
from typing import Optional
from datetime import datetime
from database import Base


class User(Base):
    """Modelo SQLAlchemy para la tabla 'users'."""
    __tablename__ = 'users'

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    surname = Column(String, nullable=False)
    password_hash = Column(String, nullable=False)
    is_active = Column(Boolean, default=True)
    updated_by = Column(Integer, nullable=True)
    updated_at = Column(DateTime, nullable=True)


# ─── Esquemas Pydantic (válidos para request/response) ───

class UserUpdate(BaseModel):
    """Esquema para la actualización parcial de un usuario."""
    name: Optional[str] = None
    surname: Optional[str] = None
    password: Optional[str] = None
    is_active: Optional[bool] = None


class UserResponse(BaseModel):
    """Esquema para la respuesta con datos del usuario."""
    id: int
    name: str
    surname: str
    is_active: bool
    updated_by: Optional[int]
    updated_at: Optional[datetime]