# 🤖 AI Agent Service

Agente conversacional inteligente construido sobre FastAPI que combina **gestión de usuarios** con **análisis de seguridad de archivos Excel**.

## Arquitectura

```
proyecto/
├── agent/
│   ├── orchestrator.py      # Orquestador principal del agente
│   ├── session_manager.py   # Gestión de sesiones conversacionales
│   └── system_prompt.py     # Prompts y configuración del LLM
├── skills/
│   ├── base.py              # Clase base Skill (interfaz para capacidades)
│   ├── user_skill.py        # CRUD de usuarios (actualizar, consultar, listar)
│   └── excel_skill.py       # Validación y lectura segura de Excel
├── memory/
│   ├── base.py              # Interfaz de memoria conversacional
│   └── conversation.py      # MongoDB + InMemory backends
├── main.py                  # FastAPI app con endpoints del agente
├── database.py              # PostgreSQL + MongoDB (del proyecto original)
├── models.py                # Modelos SQLAlchemy + Pydantic
└── excel_validator.py       # Motor de análisis de Excel (del proyecto original)
```

## Setup

1. **Instalar dependencias:**
   ```bash
   python3.11 -m venv .virtualenv
   source .virtualenv/bin/activate
   python -m pip install -r requirements.txt
   ```

2. **Configurar bases de datos (`.env`):**
   ```
   DATABASE_URL=postgresql+psycopg2://user:password@localhost/db
   MONGO_URL=mongodb://localhost:27017
   ALLOW_ORIGINS=*
   ALLOW_ORIGIN=*
   ALLOW_METHODS=*
   ```

3. **Ejecutar el servicio:**
   ```bash
   uvicorn main:app --reload
   ```

## API Endpoints

### 🤖 Chat con el Agente

```
POST /chat
```

Envía un mensaje en lenguaje natural al agente.

**Headers:**
- `X-User-ID`: ID del usuario autenticado (requerido)
- `X-Session-ID`: ID de sesión para continuar conversación (opcional)

**Body (form-data):**
- `message`: Tu mensaje en lenguaje natural

**Ejemplo:**
```bash
curl -X POST http://localhost:8000/chat \
  -H "X-User-ID: 1" \
  -F "message=Hola, muéstrame los usuarios"
```

### 📎 Subir Archivos

```
POST /chat/{session_id}/upload
```

Sube un archivo Excel para que el agente lo procese.

**Headers:**
- `X-User-ID`: ID del usuario autenticado

**Body (multipart):**
- `file`: Archivo .xlsx a procesar

**Ejemplo:**
```bash
curl -X POST http://localhost:8000/chat/mi-sesion/upload \
  -H "X-User-ID: 1" \
  -F "file=@reporte.xlsx"
```

### 📜 Historial de Conversación

```
GET /chat/{session_id}/history
DELETE /chat/{session_id}
GET /sessions
```

## Capacidades del Agente (Skills)

| Skill | ¿Qué hace? | ¿Requiere archivo? |
|-------|-----------|-------------------|
| `update_user` | Actualiza datos de un usuario (nombre, apellido, contraseña, estado) | ❌ |
| `get_user` | Consulta información de un usuario por ID | ❌ |
| `list_users` | Lista/busca usuarios por nombre, apellido o estado | ❌ |
| `validate_excel` | Escanea un Excel en busca de código malicioso (VBA, macros, etc.) | ✅ |
| `read_excel` | Lee el contenido de un Excel de forma segura (solo valores) | ✅ |

## Modo Determinista vs LLM

Actualmente el agente funciona en **modo determinista** (sin LLM), ideal para desarrollo. 
Para habilitar un LLM real (GPT-4, Claude), instala el proveedor correspondiente:

```bash
pip install openai  # Para GPT-4
# o
pip install anthropic  # Para Claude
```

Y configura la API key en el archivo `.env`:
```
OPENAI_API_KEY=sk-...
```

El orquestador (`agent/orchestrator.py`) ya tiene la estructura lista para integrarlo.