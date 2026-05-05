"""
Herramientas (tools) del agente AI.
Todas las funciones reciven un solo string (tool_input) y lo procesan internamente.
Esto evita problemas de parseo entre el LLM y LangChain al usar @tool con tipos.

Cada herramienta tiene dos versiones:
  - listar_usuarios_async (etc): funcion async que se ejecuta en el event loop principal
  - listar_usuarios (etc): wrapper sync para compatibilidad con Tool(func=...)

En agente.py se registran ambas con Tool(coroutine=..., func=...)
para que LangChain use la version async cuando ejecuta con .ainvoke().
"""

import os
import json
import asyncio

from excel_validator import validate_excel_safety, get_safe_excel_content
from models import User
from database import get_db, audit_collection
from sqlalchemy import select, func as sa_func
from datetime import datetime
import bcrypt


def _parsear(args_str: str) -> dict:
    """
    Intenta parsear el string como JSON. Si no es JSON,
    devuelve {'valor': <string_limpio>}.
    """
    if not args_str or not args_str.strip():
        return {}
    try:
        data = json.loads(args_str)
        if isinstance(data, dict):
            return data
        return {"valor": data}
    except (json.JSONDecodeError, ValueError):
        limpio = args_str.strip().strip('"').strip("'")
        return {"valor": limpio}


def _async_run(coro):
    """
    Ejecuta una coroutine de forma segura, detectando si ya hay
    un event loop corriendo (ej: desde FastAPI) o no.
    Solo se usa como fallback para mode sincrono (func=).
    """
    try:
        loop = asyncio.get_running_loop()
        future = asyncio.run_coroutine_threadsafe(coro, loop)
        return future.result(timeout=30)
    except RuntimeError:
        return asyncio.run(coro)


# ═══════════════════════════════════════════════════════════════
#  VERSIONES ASYNC (se registran como coroutine= en Tool())
# ═══════════════════════════════════════════════════════════════

async def listar_usuarios_async(args_str: str) -> str:
    """
    Cuenta y lista los usuarios registrados en la base de datos.
    Uso: cualquier string (se ignora), ej: 'listar' o 'contar'
    """
    async for db in get_db():
        # Contar total optimizadamente
        r = await db.execute(sa_func.count(User.id))
        total = r.scalar()
        
        if total == 0:
            return "No hay usuarios registrados en la base de datos."

        r = await db.execute(select(User).order_by(User.id))
        usuarios = r.scalars().all()
        
        activos = sum(1 for u in usuarios if u.is_active)
        inactivos = total - activos

        lines = [f"Total de usuarios en la base de datos: {total}"]
        lines.append(f"  Activos: {activos}")
        lines.append(f"  Inactivos: {inactivos}")
        lines.append("")
        lines.append("Listado de usuarios:")
        for u in usuarios:
            estado = "Activo" if u.is_active else "Inactivo"
            lines.append(f"  #{u.id} - {u.name} {u.surname} ({estado})")

        return "\n".join(lines)


async def buscar_usuario_async(args_str: str) -> str:
    """
    Busca un usuario por su ID.
    Uso: pasar el ID directamente (ej: '1') o como JSON: {"user_id": 1}
    """
    args = _parsear(args_str)
    try:
        user_id = int(args.get("user_id", args.get("valor", 0)))
    except (ValueError, TypeError):
        return f"No se pudo interpretar '{args_str}' como ID de usuario."

    async for db in get_db():
        r = await db.execute(select(User).where(User.id == user_id))
        u = r.scalar_one_or_none()
        if not u:
            return f"Usuario con ID {user_id} no encontrado."
        return (
            f"Datos del usuario #{u.id}:\n"
            f"  Nombre: {u.name}\n"
            f"  Apellido: {u.surname}\n"
            f"  Activo: {'Si' if u.is_active else 'No'}"
        )


async def actualizar_usuario_async(args_str: str) -> str:
    """
    Actualiza datos de un usuario.
    Uso: JSON con user_id (requerido), nombre, apellido, password, activo (opcional)
    Ej: {"user_id": 1, "nombre": "Juan"}
    """
    args = _parsear(args_str)
    user_id = args.get("user_id")
    if not user_id:
        return "Falta 'user_id' en los argumentos."

    async for db in get_db():
        r = await db.execute(select(User).where(User.id == int(user_id)))
        u = r.scalar_one_or_none()
        if not u:
            return f"Usuario con ID {user_id} no encontrado."

        cambios = {}
        if args.get("nombre"):
            u.name = args["nombre"]
            cambios["name"] = args["nombre"]
        if args.get("apellido"):
            u.surname = args["apellido"]
            cambios["surname"] = args["apellido"]
        if args.get("password"):
            pw = args["password"]
            if not pw.strip():
                return "La contrasena no puede estar vacia."
            hashed = await asyncio.to_thread(bcrypt.hashpw, pw.encode(), bcrypt.gensalt())
            u.password_hash = hashed.decode()
            cambios["password_updated"] = True
        if args.get("activo") is not None:
            val = args["activo"]
            if isinstance(val, bool):
                u.is_active = val
            else:
                u.is_active = str(val).lower() in ("true", "1", "si", "yes")
            cambios["is_active"] = u.is_active

        if not cambios:
            return "No se especificaron cambios."

        u.updated_by = args.get("updater_id", 1)
        u.updated_at = datetime.utcnow()
        await db.flush()

        await audit_collection.insert_one({
            "user_id": int(user_id),
            "updated_by": u.updated_by,
            "updated_at": u.updated_at.isoformat(),
            "changes": cambios,
        })

        return f"Usuario #{user_id} actualizado. Campos: {', '.join(cambios.keys())}"


async def validar_excel_async(args_str: str) -> str:
    """
    Valida si un Excel contiene codigo malicioso.
    Uso: ruta del archivo o JSON: {"ruta_archivo": "/ruta/doc.xlsx"}
    """
    args = _parsear(args_str)
    ruta = args.get("ruta_archivo", args.get("valor", ""))
    if not ruta:
        return "No se especifico ruta."
    if not os.path.exists(ruta):
        return f"No existe: '{ruta}'"
    if not ruta.endswith(".xlsx"):
        return f"No es .xlsx: '{ruta}'"

    res = validate_excel_safety(ruta)
    if res["safe"]:
        return (
            f"Archivo seguro.\n"
            f"  Hojas: {res['details']['sheets']}\n"
            f"  Celdas: {res['details']['cells_analyzed']}\n"
            f"  Formulas: {res['details']['formulas_found']}"
        )
    return (
        f"Archivo PELIGROSO.\n"
        f"  Patrones: {len(res['details']['malicious_patterns_found'])}\n"
        f"  Errores: {', '.join(res['errors'][:3])}"
    )


async def leer_excel_async(args_str: str) -> str:
    """
    Lee el contenido de un Excel previamente validado.
    Uso: ruta del archivo o JSON: {"ruta_archivo": "/ruta/doc.xlsx"}
    """
    args = _parsear(args_str)
    ruta = args.get("ruta_archivo", args.get("valor", ""))
    if not ruta:
        return "No se especifico ruta."
    if not os.path.exists(ruta):
        return f"No existe: '{ruta}'"

    contenido = get_safe_excel_content(ruta)
    if "error" in contenido:
        return f"Error: {contenido['error']}"

    lines = [f"Contenido de '{ruta}':"]
    lines.append(f"  Hojas: {', '.join(contenido['sheets'].keys())}")
    lines.append(f"  Filas: {contenido['metadata']['rows']}, Columnas: {contenido['metadata']['columns']}")

    for hoja, filas in contenido["sheets"].items():
        lines.append(f"\n--- {hoja} ---")
        for i, fila in enumerate(filas[:10]):
            lines.append(f"  Fila {i+1}: {' | '.join(str(c) for c in fila)}")
        if len(filas) > 10:
            lines.append(f"  ... +{len(filas)-10} filas")

    return "\n".join(lines)


# ═══════════════════════════════════════════════════════════════
#  WRAPPERS SINCRONOS (se registran como func= en Tool())
#  Solo para compatibilidad; LangChain usara la version async
#  cuando se ejecute con .ainvoke().
# ═══════════════════════════════════════════════════════════════

def listar_usuarios(args_str: str) -> str:
    return _async_run(listar_usuarios_async(args_str))

def buscar_usuario(args_str: str) -> str:
    return _async_run(buscar_usuario_async(args_str))

def actualizar_usuario(args_str: str) -> str:
    return _async_run(actualizar_usuario_async(args_str))

def validar_excel(args_str: str) -> str:
    return _async_run(validar_excel_async(args_str))

def leer_excel(args_str: str) -> str:
    return _async_run(leer_excel_async(args_str))
