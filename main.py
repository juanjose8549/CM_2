"""
AI Agent - FastAPI Application
Transforms the original user management + Excel validation service into
an intelligent conversational agent.
"""
import os
import tempfile
import uuid
from typing import Optional

from fastapi import FastAPI, HTTPException, Header, File, UploadFile, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from dotenv import load_dotenv

from agent.orchestrator import AgentOrchestrator

load_dotenv()

# ---------------------------------------------------------------------------
# App Configuration
# ---------------------------------------------------------------------------
ALLOW_ORIGINS = os.getenv("ALLOW_ORIGINS", "*")
ALLOW_ORIGIN = os.getenv("ALLOW_ORIGIN", "*")
ALLOW_METHODS = os.getenv("ALLOW_METHODS", "*")

app = FastAPI(
    title="AI Agent Service",
    description="Agente conversacional para gestión de usuarios y análisis de archivos Excel",
    version="2.0.0"
)

# Enable CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=[ALLOW_ORIGINS, ALLOW_ORIGIN],
    allow_credentials=True,
    allow_methods=[ALLOW_METHODS],
    allow_headers=["*"],
)

# ---------------------------------------------------------------------------
# Agent Initialization
# ---------------------------------------------------------------------------
agent = AgentOrchestrator()

print("\n" + "="*60)
print("  🤖 AI AGENT SERVICE")
print("="*60)
print("\n📋 Skills registrados:")
for name, skill in agent.skills.items():
    file_req = "📎" if skill.requires_file_upload else ""
    destructive = "⚠️" if skill.is_destructive else ""
    print(f"  {file_req}{destructive} {name}")
print("="*60 + "\n")

# ---------------------------------------------------------------------------
# Health Check
# ---------------------------------------------------------------------------
@app.get("/")
async def root():
    return {
        "service": "AI Agent Service",
        "version": "2.0.0",
        "status": "online",
        "skills": list(agent.skills.keys())
    }

@app.get("/health")
async def health():
    return {"status": "healthy"}

# ---------------------------------------------------------------------------
# Chat Endpoint (Main Agent Interface)
# ---------------------------------------------------------------------------
@app.post("/chat")
async def chat(
    message: str = Form(...),
    session_id: Optional[str] = Form(None),
    x_user_id: int = Header(..., alias="X-User-ID"),
    x_session_id: Optional[str] = Header(None, alias="X-Session-ID")
):
    """
    Main chat endpoint for the AI Agent.
    
    Send a message in natural language and the agent will:
    - Understand your intent
    - Use the appropriate tools if needed
    - Respond in natural language
    
    Headers:
    - X-User-ID: Your user ID (required)
    - X-Session-ID: Session ID to continue a conversation (optional)
    
    Body (form-data):
    - message: Your message in natural language (required)
    - session_id: Alternative way to provide session ID (optional)
    """
    sid = session_id or x_session_id or str(uuid.uuid4())

    try:
        result = await agent.process_message(
            session_id=sid,
            user_id=x_user_id,
            message=message
        )
        return JSONResponse(content=result)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error processing message: {str(e)}")


# ---------------------------------------------------------------------------
# File Upload Endpoint
# ---------------------------------------------------------------------------
@app.post("/chat/{session_id}/upload")
async def upload_file(
    session_id: str,
    file: UploadFile = File(...),
    x_user_id: int = Header(..., alias="X-User-ID")
):
    """
    Upload a file (Excel) to be processed by the agent.
    
    The agent will remember the file for the current session.
    After uploading, tell the agent what to do with it (validate or read).
    """
    if not file.filename.endswith('.xlsx'):
        raise HTTPException(
            status_code=400,
            detail=f"Formato de archivo no válido: {file.filename}. Solo se permiten archivos .xlsx"
        )

    temp_path = None
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix='.xlsx') as tmp_file:
            content = await file.read()
            tmp_file.write(content)
            temp_path = tmp_file.name

        result = await agent.handle_file_upload(
            session_id=session_id,
            file_path=temp_path,
            filename=file.filename,
            content_type=file.content_type or "application/octet-stream"
        )

        return JSONResponse(content=result)

    except Exception as e:
        if temp_path and os.path.exists(temp_path):
            os.unlink(temp_path)
        raise HTTPException(status_code=500, detail=f"Error al procesar el archivo: {str(e)}")


# ---------------------------------------------------------------------------
# Session Management Endpoints
# ---------------------------------------------------------------------------
@app.get("/chat/{session_id}/history")
async def get_chat_history(
    session_id: str,
    x_user_id: int = Header(..., alias="X-User-ID")
):
    """Get the conversation history for a session."""
    try:
        session = agent.session_manager.get_or_create_session(session_id, x_user_id)
        messages = agent.session_manager.get_history(session_id)
        
        return JSONResponse(content={
            "session_id": session_id,
            "message_count": len(messages),
            "messages": [
                {
                    "role": m.role,
                    "content": m.content[:500] if m.content else "",
                    "timestamp": m.timestamp.isoformat(),
                    "metadata": m.metadata
                }
                for m in messages
            ]
        })
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error getting history: {str(e)}")


@app.delete("/chat/{session_id}")
async def delete_session(
    session_id: str,
    x_user_id: int = Header(..., alias="X-User-ID")
):
    """Delete a conversation session."""
    try:
        success = agent.session_manager.delete_session(session_id)
        if success:
            return JSONResponse(content={
                "message": f"Sesión {session_id} eliminada exitosamente"
            })
        else:
            raise HTTPException(status_code=404, detail="Sesión no encontrada")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error deleting session: {str(e)}")


# ---------------------------------------------------------------------------
# List Active Sessions
# ---------------------------------------------------------------------------
@app.get("/sessions")
async def list_sessions(
    x_user_id: int = Header(..., alias="X-User-ID")
):
    """List all active sessions for the current user."""
    try:
        sessions = agent.session_manager.memory.list_sessions(user_id=x_user_id)
        return JSONResponse(content={
            "user_id": x_user_id,
            "sessions": sessions,
            "total": len(sessions)
        })
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error listing sessions: {str(e)}")