import os
import asyncio
import bcrypt
import tempfile
import json

from fastapi import FastAPI, HTTPException, Depends, Header, File, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from models import User, UserUpdate
from datetime import datetime
from database import get_db, audit_collection, engine, Base
from excel_validator import validate_excel_safety, get_safe_excel_content

# ─── Importaciones del agente AI ───
from agent.agente import crear_agente, ejecutar_consulta
from models import ConsultaAgente

ALLOW_ORIGINS = os.getenv("ALLOW_ORIGINS")
ALLOW_ORIGIN = os.getenv("ALLOW_ORIGIN")
ALLOW_METHODS = os.getenv("ALLOW_METHODS")

app = FastAPI()

# Variable global para el agente (se inicializa en el startup)
agente_ejecutor = None

# Middleware CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=[f'{ALLOW_ORIGINS}', f'{ALLOW_ORIGIN}'],
    allow_credentials=True,
    allow_methods=[f'{ALLOW_METHODS}'],
    allow_headers=["*"],
)

@app.on_event("startup")
async def on_startup():
    """Inicializa el agente AI y crea las tablas en la base de datos."""
    global agente_ejecutor

    # Inicializar el agente LangChain
    proveedor = os.getenv("LLM_PROVIDER", "openai")
    print(f"Inicializando agente AI con proveedor: {proveedor}")
    agente_ejecutor = crear_agente()

    # Crear tablas en la base de datos
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

@app.post("/excel/validate")
async def validate_excel(file: UploadFile = File(...)):
    """
    Valida un archivo Excel:
    1. Verifica que sea .xlsx
    2. Escanea en busca de código malicioso
    3. Retorna resultado de validación
    """
    # Validar extensión
    if not file.filename.endswith('.xlsx'):
        raise HTTPException(
            status_code=400,
            detail=f"Formato de archivo no válido: {file.filename}. Solo se permiten archivos .xlsx"
        )
    
    # Validar tipo MIME
    if file.content_type not in [
        'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        'application/octet-stream',
    ]:
        raise HTTPException(
            status_code=400,
            detail=f"Tipo de contenido no válido: {file.content_type}"
        )
    
    # Guardar archivo temporalmente
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix='.xlsx') as tmp_file:
            content = await file.read()
            tmp_file.write(content)
            tmp_path = tmp_file.name
        
        # Validar el archivo Excel
        validation_result = validate_excel_safety(tmp_path)
        
        response = {
            "filename": file.filename,
            "file_size": len(content),
            "safe": validation_result["safe"],
            "validation": validation_result,
        }
        
        return JSONResponse(content=response)
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error al procesar el archivo: {str(e)}")
    finally:
        # Limpiar archivo temporal
        import os as os_module
        try:
            os_module.unlink(tmp_path)
        except:
            pass

@app.post("/excel/read")
async def read_excel(file: UploadFile = File(...)):
    """
    Lee un archivo Excel validado y retorna su contenido.
    Primero valida que sea seguro, luego extrae los datos.
    """
    # Validar extensión
    if not file.filename.endswith('.xlsx'):
        raise HTTPException(
            status_code=400,
            detail=f"Formato de archivo no válido: {file.filename}. Solo se permiten archivos .xlsx"
        )
    
    # Guardar archivo temporalmente
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix='.xlsx') as tmp_file:
            content = await file.read()
            tmp_file.write(content)
            tmp_path = tmp_file.name
        
        # Primero validar seguridad
        validation_result = validate_excel_safety(tmp_path)
        
        if not validation_result["safe"]:
            return JSONResponse(
                status_code=400,
                content={
                    "error": "El archivo contiene código malicioso",
                    "details": validation_result["errors"],
                    "malicious_patterns": validation_result["details"]["malicious_patterns_found"],
                }
            )
        
        # Si es seguro, leer el contenido
        safe_content = get_safe_excel_content(tmp_path)
        
        response = {
            "filename": file.filename,
            "file_size": len(content),
            "safe": True,
            "data": safe_content,
        }
        
        return JSONResponse(content=response)
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error al procesar el archivo: {str(e)}")
    finally:
        # Limpiar archivo temporal
        import os as os_module
        try:
            os_module.unlink(tmp_path)
        except:
            pass


@app.patch("/users/{user_id}")
async def update_user(
        user_id: int,
        update: UserUpdate,
        updater_id: int = Header(..., alias="X-User-ID"),
        db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # Validate
    if update.password is not None and not update.password.strip():
        raise HTTPException(status_code=400, detail="Invalid password")
    if update.is_active is not None and not isinstance(update.is_active, bool):
        raise HTTPException(status_code=400, detail="Invalid is_active")

    # Update fields
    if update.name is not None:
        user.name = update.name
    if update.surname is not None:
        user.surname = update.surname
    if update.password is not None:
        # Ejecutamos bcrypt en un hilo separado para no bloquear el event loop
        hashed = await asyncio.to_thread(
            bcrypt.hashpw, update.password.encode(), bcrypt.gensalt()
        )
        user.password_hash = hashed.decode()
    if update.is_active is not None:
        user.is_active = update.is_active

    user.updated_by = updater_id
    user.updated_at = datetime.utcnow()

    changes = {k: v for k, v in update.dict(exclude_unset=True).items() if k != 'password'}
    if 'password' in update.dict(exclude_unset=True):
        changes['password_updated'] = True

    log = {
        "user_id": user_id,
        "updated_by": updater_id,
        "updated_at": user.updated_at.isoformat(),
        "changes": changes
    }
    audit_collection.insert_one(log)

    return {"message": "User updated successfully"}