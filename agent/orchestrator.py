"""
Agent Orchestrator - The brain of the AI Agent.
Coordinates skills, LLM interactions, and conversation flow.
"""
from typing import Dict, Any, Optional, List
import json

from skills.base import Skill
from skills.user_skill import UserUpdateSkill, GetUserSkill, ListUsersSkill
from skills.excel_skill import ExcelValidateSkill, ExcelReadSkill
from agent.session_manager import SessionManager
from agent.system_prompt import SYSTEM_PROMPT_TEMPLATE


class AgentOrchestrator:
    """
    Orchestrates the AI agent:
    - Manages skill registration and execution
    - Handles LLM communication (OpenAI/Anthropic)
    - Coordinates conversation flow with memory
    """

    def __init__(self, llm_client=None, llm_config: Optional[Dict] = None):
        self.skills: Dict[str, Skill] = {}
        self.session_manager = SessionManager(use_mongo=False)  # Default: in-memory for dev
        self.llm_client = llm_client
        self.llm_config = llm_config or {
            "model": "gpt-4",
            "temperature": 0.7,
            "max_tokens": 2000
        }
        self._register_default_skills()

    def _register_default_skills(self):
        """Register the built-in skills."""
        self.register_skill(UserUpdateSkill())
        self.register_skill(GetUserSkill())
        self.register_skill(ListUsersSkill())
        self.register_skill(ExcelValidateSkill())
        self.register_skill(ExcelReadSkill())

    def register_skill(self, skill: Skill):
        """Register a new skill/capability."""
        self.skills[skill.name] = skill
        print(f"  ✅ Skill registered: {skill.name}")

    def get_skill(self, name: str) -> Optional[Skill]:
        """Get a registered skill by name."""
        return self.skills.get(name)

    def get_skills_descriptions(self) -> str:
        """Build a formatted string of all skills for the system prompt."""
        descriptions = []
        for name, skill in self.skills.items():
            destructive = " ⚠️ REQUIERE CONFIRMACIÓN" if skill.is_destructive else ""
            file_upload = " 📎 REQUIERE ARCHIVO" if skill.requires_file_upload else ""
            descriptions.append(
                f"### {name}{destructive}{file_upload}\n"
                f"{skill.get_description()}\n"
            )
        return "\n".join(descriptions)

    def get_tools_for_llm(self) -> List[Dict]:
        """Build the tools/functions list for LLM function calling."""
        tools = []
        for name, skill in self.skills.items():
            schema = skill.get_parameters_schema()
            if schema:
                tools.append(schema)
        return tools

    async def process_message(
        self,
        session_id: str,
        user_id: int,
        message: str
    ) -> Dict[str, Any]:
        """
        Process a user message through the agent pipeline.
        
        1. Get/create session
        2. Save user message
        3. Build system prompt with context
        4. Send to LLM with function calling
        5. If LLM requests a skill execution -> execute it
        6. Return response to user
        """
        # 1. Get or create session
        session = self.session_manager.get_or_create_session(session_id, user_id)

        # 2. Save user message
        self.session_manager.add_user_message(session_id, message)

        # 3. Check if there's a pending file for this session
        pending_file = self.session_manager.get_uploaded_file(session_id)

        # 4. Build conversation context
        history_context = self.session_manager.build_conversation_context(session_id)
        history_count = len(session.messages)

        system_prompt = SYSTEM_PROMPT_TEMPLATE.format(
            skills_descriptions=self.get_skills_descriptions(),
            session_id=session_id,
            user_id=user_id,
            history_count=history_count
        )

        if pending_file:
            system_prompt += (
                f"\n\n## Archivo Pendiente\n"
                f"El usuario ha subido un archivo: '{pending_file['filename']}' "
                f"(tipo: {pending_file['content_type']}). "
                f"Está disponible temporalmente en: {pending_file['file_path']}\n"
                f"Usa la herramienta adecuada para procesarlo."
            )

        # 5. Build conversation messages for LLM
        conversation_messages = [
            {"role": "system", "content": system_prompt}
        ]
        
        for msg in session.messages[-20:]:
            role_map = {
                "user": "user",
                "assistant": "assistant",
                "tool_call": "function",
                "system": "system"
            }
            role = role_map.get(msg.role, "user")
            content = msg.content
            
            if msg.role == "tool_call":
                conversation_messages.append({
                    "role": "function",
                    "name": msg.metadata.get("tool", "unknown"),
                    "content": json.dumps(msg.metadata.get("result_success", {}))
                })
            else:
                conversation_messages.append({"role": role, "content": content})

        conversation_messages.append({"role": "user", "content": message})

        # 6. Call LLM or deterministic mode
        try:
            if self.llm_client:
                response = await self._call_llm(conversation_messages)
            else:
                response = await self._deterministic_response(
                    message, pending_file, session_id
                )
        except Exception as e:
            return {
                "session_id": session_id,
                "response": f"Lo siento, ocurrió un error al procesar tu mensaje: {str(e)}",
                "requires_file": False,
                "finished": True,
                "error": str(e)
            }

        # 7. Save assistant response
        self.session_manager.add_assistant_message(
            session_id, response.get("response", "")
        )

        return {
            "session_id": session_id,
            "response": response.get("response", ""),
            "requires_file": response.get("requires_file", False),
            "requires_confirmation": response.get("requires_confirmation", False),
            "finished": response.get("finished", True),
            "tool_executed": response.get("tool_executed")
        }

    async def _call_llm(self, messages: List[Dict]) -> Dict[str, Any]:
        """
        Call the LLM with function calling support.
        Placeholder for OpenAI/Anthropic integration.
        """
        return await self._deterministic_response(
            messages[-1]["content"] if messages else "", None, ""
        )

    async def _deterministic_response(
        self,
        message: str,
        pending_file: Optional[Dict],
        session_id: str
    ) -> Dict[str, Any]:
        """
        Deterministic response mode when no LLM is configured.
        Uses simple intent matching as fallback for development.
        """
        message_lower = message.lower().strip()

        # ============================================================
        # PRIORITY 1: If there's a pending file, process it
        # ============================================================
        if pending_file:
            file_path = pending_file["file_path"]
            filename = pending_file["filename"]

            if any(word in message_lower for word in [
                "validar", "validate", "revisar", "check", "escanea",
                "analiza", "examina"
            ]):
                skill = self.skills.get("validate_excel")
                if skill:
                    result = await skill.execute({
                        "file_path": file_path,
                        "filename": filename
                    })
                    self.session_manager.clear_uploaded_file(session_id)
                    if result["success"]:
                        return {
                            "response": result.get("summary", "Validación completada."),
                            "finished": True,
                            "tool_executed": "validate_excel"
                        }
                    else:
                        return {
                            "response": f"No pude validar el archivo: {result.get('error', 'Error desconocido')}",
                            "finished": True
                        }

            if any(word in message_lower for word in [
                "leer", "read", "contenido", "muestra", "show",
                "extrae", "datos"
            ]):
                skill = self.skills.get("read_excel")
                if skill:
                    result = await skill.execute({
                        "file_path": file_path,
                        "filename": filename
                    })
                    self.session_manager.clear_uploaded_file(session_id)
                    if result["success"]:
                        return {
                            "response": result.get("summary", "Lectura completada."),
                            "finished": True,
                            "tool_executed": "read_excel"
                        }
                    else:
                        return {
                            "response": f"No pude leer el archivo: {result.get('error', 'Error desconocido')}",
                            "finished": True
                        }

            # If there's a pending file but user said something else
            return {
                "response": (
                    f"Tienes el archivo **'{filename}'** pendiente. "
                    f"¿Quieres que lo **valide** (revise si es seguro) o que **lea** su contenido?"
                ),
                "finished": False
            }

        # ============================================================
        # PRIORITY 2: Handle user-related intents
        # ============================================================
        if any(word in message_lower for word in ["usuarios", "users", "lista", "list", "todos"]):
            skill = self.skills.get("list_users")
            if skill:
                result = await skill.execute({})
                if result["success"] and result.get("users"):
                    users_list = "\n".join(
                        f"  - #{u['id']}: {u['name']} {u['surname']} ({'activo' if u['is_active'] else 'inactivo'})"
                        for u in result.get("users", [])
                    )
                    return {
                        "response": f"📋 Hay **{result['total']} usuarios** en el sistema:\n{users_list}",
                        "finished": True,
                        "tool_executed": "list_users"
                    }
                else:
                    return {
                        "response": "📋 No hay usuarios registrados en el sistema.",
                        "finished": True,
                        "tool_executed": "list_users"
                    }

        # ============================================================
        # PRIORITY 3: Check if user wants to upload a file
        # ============================================================
        if any(word in message_lower for word in ["excel", "archivo", "file", "subir", "upload"]):
            return {
                "response": (
                    "Claro, puedes subir tu archivo Excel usando el botón de carga. "
                    "Una vez que lo suba, dime si quieres que lo **valide** (revise si es seguro) "
                    "o que **lea** su contenido."
                ),
                "requires_file": True,
                "finished": False
            }

        # ============================================================
        # PRIORITY 4: Greetings
        # ============================================================
        if any(word in message_lower for word in ["hola", "hello", "hi", "buenas", "saludos"]):
            return {
                "response": (
                    "¡Hola! Soy tu asistente AI. Puedo ayudarte con:\n\n"
                    "📋 **Gestión de usuarios** - Consultar y actualizar usuarios\n"
                    "📊 **Validación de Excel** - Revisar si un archivo Excel es seguro\n"
                    "📖 **Lectura de Excel** - Leer el contenido de archivos Excel\n\n"
                    "¿En qué puedo ayudarte hoy?"
                ),
                "finished": False
            }

        # ============================================================
        # PRIORITY 5: Default response
        # ============================================================
        return {
            "response": (
                "No estoy seguro de cómo ayudarte con eso. Estas son las cosas que puedo hacer:\n\n"
                "📋 **Usuarios:** 'muéstrame los usuarios', 'busca a Juan', 'actualiza usuario 1'\n"
                "📊 **Excel:** 'valida este Excel', 'lee el archivo' (primero súbelo)\n\n"
                "¿Qué te gustaría hacer?"
            ),
            "finished": False
        }

    async def handle_file_upload(
        self,
        session_id: str,
        file_path: str,
        filename: str,
        content_type: str
    ) -> Dict[str, Any]:
        """
        Handle a file upload for a session.
        Stores the file reference and returns a message to the user.
        """
        self.session_manager.store_uploaded_file(session_id, file_path, filename, content_type)

        self.session_manager.add_user_message(
            session_id,
            f"[Subió el archivo: {filename}]"
        )

        response = (
            f"📎 He recibido el archivo **'{filename}'**.\n\n"
            f"¿Qué quieres hacer con él?\n"
            f"- **Validarlo** (revisar si contiene código malicioso)\n"
            f"- **Leerlo** (extraer su contenido)"
        )

        self.session_manager.add_assistant_message(session_id, response)

        return {
            "session_id": session_id,
            "response": response,
            "requires_file": False,
            "finished": False
        }
