"""
User management skill for the AI Agent.
Handles user CRUD operations, leveraging existing database models.
"""
from typing import Dict, Any, Optional, List
from datetime import datetime

import bcrypt
from sqlalchemy import select
from sqlalchemy.orm import Session

from skills.base import Skill
from models import User, UserUpdate
from database import get_db, audit_collection


class UserUpdateSkill(Skill):
    """Skill to update user information in the database."""

    @property
    def name(self) -> str:
        return "update_user"

    @property
    def is_destructive(self) -> bool:
        return True

    def get_description(self) -> str:
        return (
            "Actualiza los datos de un usuario existente en la base de datos. "
            "Puede modificar nombre, apellido, contraseña y estado activo/inactivo. "
            "Requiere el ID del usuario y opcionalmente los campos a actualizar."
        )

    def get_parameters_schema(self) -> Dict[str, Any]:
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.get_description(),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "user_id": {
                            "type": "integer",
                            "description": "ID del usuario a actualizar"
                        },
                        "name": {
                            "type": "string",
                            "description": "Nuevo nombre del usuario (opcional)"
                        },
                        "surname": {
                            "type": "string",
                            "description": "Nuevo apellido del usuario (opcional)"
                        },
                        "password": {
                            "type": "string",
                            "description": "Nueva contraseña del usuario (opcional)"
                        },
                        "is_active": {
                            "type": "boolean",
                            "description": "Estado activo/inactivo del usuario (opcional)"
                        }
                    },
                    "required": ["user_id"]
                }
            }
        }

    async def execute(self, params: Dict[str, Any], context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Update a user in the database.
        
        Args:
            params: Must include 'user_id', optionally 'name', 'surname', 'password', 'is_active'
            context: Should include 'updater_id' (who is making the change)
        
        Returns:
            Dict with result message and updated fields
        """
        user_id = params.get("user_id")
        if not user_id:
            return {"success": False, "error": "Se requiere el ID del usuario"}

        updater_id = context.get("updater_id", 0) if context else 0

        db: Session = next(get_db())
        try:
            result = db.execute(select(User).where(User.id == user_id))
            user = result.scalar_one_or_none()

            if not user:
                return {"success": False, "error": f"Usuario con ID {user_id} no encontrado"}

            # Validate fields
            if params.get("password") is not None and not params["password"].strip():
                return {"success": False, "error": "La contraseña no puede estar vacía"}
            if params.get("is_active") is not None and not isinstance(params["is_active"], bool):
                return {"success": False, "error": "is_active debe ser un valor booleano"}

            # Track changes for audit
            changes = {}

            # Update fields
            if params.get("name") is not None:
                user.name = params["name"]
                changes["name"] = params["name"]
            if params.get("surname") is not None:
                user.surname = params["surname"]
                changes["surname"] = params["surname"]
            if params.get("password") is not None:
                user.password_hash = bcrypt.hashpw(
                    params["password"].encode(), bcrypt.gensalt()
                ).decode()
                changes["password_updated"] = True
            if params.get("is_active") is not None:
                user.is_active = params["is_active"]
                changes["is_active"] = params["is_active"]

            user.updated_by = updater_id
            user.updated_at = datetime.utcnow()

            db.commit()

            # Audit log in MongoDB
            log = {
                "user_id": user_id,
                "updated_by": updater_id,
                "updated_at": user.updated_at.isoformat(),
                "changes": changes,
                "source": "ai_agent"
            }
            try:
                audit_collection.insert_one(log)
            except Exception:
                pass  # Audit logging is non-critical

            return {
                "success": True,
                "message": f"Usuario ID {user_id} actualizado exitosamente",
                "updated_fields": list(changes.keys())
            }

        except Exception as e:
            db.rollback()
            return {"success": False, "error": f"Error al actualizar usuario: {str(e)}"}
        finally:
            db.close()


class GetUserSkill(Skill):
    """Skill to retrieve user information."""

    @property
    def name(self) -> str:
        return "get_user"

    def get_description(self) -> str:
        return (
            "Obtiene la información de un usuario por su ID. "
            "Retorna nombre, apellido, estado y fechas de actualización."
        )

    def get_parameters_schema(self) -> Dict[str, Any]:
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.get_description(),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "user_id": {
                            "type": "integer",
                            "description": "ID del usuario a consultar"
                        }
                    },
                    "required": ["user_id"]
                }
            }
        }

    async def execute(self, params: Dict[str, Any], context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        user_id = params.get("user_id")
        if not user_id:
            return {"success": False, "error": "Se requiere el ID del usuario"}

        db: Session = next(get_db())
        try:
            result = db.execute(select(User).where(User.id == user_id))
            user = result.scalar_one_or_none()

            if not user:
                return {"success": False, "error": f"Usuario con ID {user_id} no encontrado"}

            return {
                "success": True,
                "user": {
                    "id": user.id,
                    "name": user.name,
                    "surname": user.surname,
                    "is_active": user.is_active,
                    "updated_by": user.updated_by,
                    "updated_at": user.updated_at.isoformat() if user.updated_at else None
                }
            }
        except Exception as e:
            return {"success": False, "error": f"Error al consultar usuario: {str(e)}"}
        finally:
            db.close()


class ListUsersSkill(Skill):
    """Skill to list/search users."""

    @property
    def name(self) -> str:
        return "list_users"

    def get_description(self) -> str:
        return (
            "Lista los usuarios del sistema. Puede filtrar por nombre, apellido "
            "o estado activo/inactivo. Retorna una lista de usuarios coincidentes."
        )

    def get_parameters_schema(self) -> Dict[str, Any]:
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.get_description(),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "search_term": {
                            "type": "string",
                            "description": "Término de búsqueda para filtrar por nombre o apellido (opcional)"
                        },
                        "is_active": {
                            "type": "boolean",
                            "description": "Filtrar por estado activo/inactivo (opcional)"
                        },
                        "limit": {
                            "type": "integer",
                            "description": "Máximo de resultados a retornar (opcional, default 50)"
                        }
                    }
                }
            }
        }

    async def execute(self, params: Dict[str, Any], context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        db: Session = next(get_db())
        try:
            query = select(User)
            
            search_term = params.get("search_term")
            if search_term:
                like_pattern = f"%{search_term}%"
                query = query.where(
                    (User.name.ilike(like_pattern)) | (User.surname.ilike(like_pattern))
                )
            
            is_active = params.get("is_active")
            if is_active is not None:
                query = query.where(User.is_active == is_active)
            
            limit = min(params.get("limit", 50), 200)
            query = query.limit(limit)
            
            result = db.execute(query)
            users = result.scalars().all()

            return {
                "success": True,
                "total": len(users),
                "users": [
                    {
                        "id": u.id,
                        "name": u.name,
                        "surname": u.surname,
                        "is_active": u.is_active,
                        "updated_at": u.updated_at.isoformat() if u.updated_at else None
                    }
                    for u in users
                ]
            }
        except Exception as e:
            return {"success": False, "error": f"Error al listar usuarios: {str(e)}"}
        finally:
            db.close()
