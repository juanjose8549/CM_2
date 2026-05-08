# User Account Update Service - AI Agent

This is a FastAPI service for updating user accounts using PostgreSQL and MongoDB, powered by an **AI agent** built with LangChain.

## Features

- **AI Agent**: Natural language interface using LangChain with support for OpenAI, DeepSeek, and NVIDIA NIM LLMs
- **User Management**: Update user accounts via REST API or AI agent
- **Excel Validation**: Scan Excel files for malicious content (macros, scripts, etc.)
- **Audit Logging**: Track all changes in MongoDB

## Setup

1. Install dependencies:
   ```bash
   python3.11 -m venv .virtualenv
   source .virtualenv/bin/activate
   pip install -r requirements.txt
   ```

2. Configure environment variables in `.env`:
   ```env
   # Database
   DATABASE_URL=postgresql+asyncpg://user:password@localhost/db
   MONGO_URL=mongodb://localhost:27017

   # LLM Provider (choose one)
   LLM_PROVIDER=openai     # or "deepseek" or "nvidia"
   OPENAI_API_KEY=sk-your-openai-key
   DEEPSEEK_API_KEY=sk-your-deepseek-key
   NVIDIA_API_KEY=nvapi-your-nvidia-key  # Gratis en build.nvidia.com

   # Modelo (opcional, funciona para cualquier proveedor)
   # LLM_MODEL=meta/llama-3.1-8b-instruct

   # CORS (optional)
   ALLOW_ORIGINS=*
   ALLOW_ORIGIN=*
   ALLOW_METHODS=*
   ```

3. Set up databases:
   - **PostgreSQL**: Create a database and update `DATABASE_URL` in `.env`
   - **MongoDB**: Ensure MongoDB is running, update `MONGO_URL` if needed

4. Run the service:
   ```bash
   uvicorn main:app --reload
   ```

## API Endpoints

### POST /agent/chat

Send a natural language message to the AI agent. The agent will analyze your request and execute the appropriate action.

**Request body:**
```json
{
  "mensaje": "Update user 5, change their name to John"
}
```

**Response:**
```json
{
  "respuesta": "User #5 updated successfully. Modified fields: name"
}
```

**Example queries:**
- *"Find user with ID 5"*
- *"Update user 3, change their name to John"*
- *"Disable user 7's account"*
- *"Validate this Excel file: /path/to/file.xlsx"*
- *"Read the spreadsheet and show me the data"*

### PATCH /users/{user_id}

Update a user account directly via REST API.

**Headers:**
- `X-User-ID`: ID of the authenticated user performing the update

**Body (JSON, partial update):**
- `name`: string (optional)
- `surname`: string (optional)
- `password`: string (optional)
- `is_active`: boolean (optional)

**Response:**
- `200`: `{"message": "User updated successfully"}`
- `400`: Invalid data
- `404`: User not found

### POST /excel/validate

Upload and validate an Excel file for malicious content.

### POST /excel/read

Upload and read a validated Excel file's content.

## AI Agent

The service includes an intelligent AI agent that understands natural language requests. It uses the **ReAct** (Reasoning + Acting) pattern to decide which actions to take.

### Supported LLM Providers

| Provider | Default Model | Environment Variable | Cost |
|---|---|---|---|
| **OpenAI** | `gpt-4o-mini` | `OPENAI_API_KEY` | Pago por uso |
| **DeepSeek** | `deepseek-chat` | `DEEPSEEK_API_KEY` | Económico |
| **NVIDIA NIM** | `meta/llama-3.3-70b-instruct` | `NVIDIA_API_KEY` | **Gratuito** (con rate limit) |

> **NVIDIA**: Regístrate gratis en [build.nvidia.com](https://build.nvidia.com) para obtener tu API Key. Tiene rate limits generosos para desarrollo y pruebas. Puedes cambiar el modelo con `LLM_MODEL` (ej: `LLM_MODEL=mistralai/mistral-large`, `LLM_MODEL=google/gemma-3-12b-it`, etc.).

Set `LLM_PROVIDER=openai`, `LLM_PROVIDER=deepseek`, or `LLM_PROVIDER=nvidia` in `.env` to switch between providers.

### Agent Capabilities

The agent can:
- **Search users** by ID
- **Update user data** (name, surname, password, active status)
- **Validate Excel files** for malicious content
- **Read Excel files** content (after validation)
- Answer general questions about the system

## Project Structure

```
├── main.py                 # FastAPI application entry point
├── models.py               # SQLAlchemy models and Pydantic schemas
├── database.py             # Database connections (PostgreSQL + MongoDB)
├── excel_validator.py      # Excel malware detection engine
├── agent/
│   ├── __init__.py         # Agent module initializer
│   ├── config.py           # LLM provider configuration (OpenAI/DeepSeek)
│   ├── prompts.py          # System prompts for the agent
│   ├── herramientas.py     # LangChain tools for the agent
│   └── agente.py           # Agent setup and execution
├── tests/
│   └── test_agente.py      # Agent unit tests
└── requirements.txt        # Python dependencies
```

## Running Tests

```bash
pytest tests/ -v
```