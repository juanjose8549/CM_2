import os
import asyncio
import bcrypt

from fastapi import FastAPI, HTTPException, Depends, Header
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from models import User, UserUpdate
from datetime import datetime
from database import get_db, audit_collection, engine, Base

# ─── Configuración CORS desde variables de entorno ───
ALLOW_ORIGINS = os.getenv("ALLOW_ORIGINS")
ALLOW_ORIGIN = os.getenv("ALLOW_ORIGIN")
ALLOW_METHODS = os.getenv("ALLOW_METHODS")

app = FastAPI()

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
    """Crea las tablas en la base de datos al iniciar la aplicación."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


@app.patch("/users/{user_id}")
async def update_user(
    user_id: int,
    update: UserUpdate,
    updater_id: int = Header(..., alias="X-User-ID"),
    db: AsyncSession = Depends(get_db),
):
    """
    Actualiza parcialmente los datos de un usuario.

    - Busca al usuario por ID en PostgreSQL.
    - Si no existe, responde con 404.
    - Si existe, aplica los cambios enviados en el body.
    - Las contraseñas se hashean con bcrypt (en un hilo separado para no bloquear).
    - Registra un log de auditoría en MongoDB.
    """
    # ── 1. Buscar usuario ──
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")

    # ── 2. Validar campos ──
    if update.password is not None and not update.password.strip():
        raise HTTPException(status_code=400, detail="Contraseña inválida")
    if update.is_active is not None and not isinstance(update.is_active, bool):
        raise HTTPException(status_code=400, detail="is_active debe ser booleano")

    # ── 3. Aplicar cambios ──
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

    # ── 4. Preparar log de auditoría (sin incluir la contraseña) ──
    datos_enviados = update.model_dump(exclude_unset=True)
    cambios = {k: v for k, v in datos_enviados.items() if k != "password"}
    if "password" in datos_enviados:
        cambios["password_updated"] = True

    log = {
        "user_id": user_id,
        "updated_by": updater_id,
        "updated_at": user.updated_at.isoformat(),
        "changes": cambios,
    }

    # ── 5. Guardar log en MongoDB (asíncrono con Motor) ──
    await audit_collection.insert_one(log)

    return {"message": "Usuario actualizado exitosamente"}
