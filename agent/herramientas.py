"""
Herramientas (tools) del agente AI.
Cada herramienta es una funcion decorada con @tool que el agente LangChain
puede invocar segun lo que decida el LLM.
"""

import os
import asyncio
from typing import Optional

from langchain.tools import tool

from excel_validator import validate_excel_safety, get_safe_excel_content
from models import User
from database import get_db, audit_collection
from sqlalchemy import select
from datetime import datetime
import bcrypt


# ─── Herramienta: buscar_usuario ───────────────────────────────────────────

@tool
def buscar_usuario(user_id: int) -> str:
    """
    Busca un usuario por su ID y devuelve su informacion.

    Args:
        user_id: ID numerico del usuario a buscar.

    Returns:
        str: Datos del usuario formateados o mensaje de no encontrado.
    """
    async def _buscar():
        async for db in get_db():
            resultado = await db.execute(select(User).where(User.id == user_id))
            usuario = resultado.scalar_one_or_none()
            if not usuario:
                return f"Usuario con ID {user_id} no encontrado."

            return (
                f"Datos del usuario #{usuario.id}:\n"
                f"  - Nombre: {usuario.name}\n"
                f"  - Apellido: {usuario.surname}\n"
                f"  - Activo: {'Si' if usuario.is_active else 'No'}\n"
                f"  - Actualizado por: {usuario.updated_by or 'Nunca'}\n"
                f"  - Ultima actualizacion: {usuario.updated_at or 'Nunca'}"
            )

    return asyncio.run(_buscar())


# ─── Herramienta: actualizar_usuario ───────────────────────────────────────

@tool
def actualizar_usuario(
    user_id: int,
    nombre: Optional[str] = None,
    apellido: Optional[str] = None,
    password: Optional[str] = None,
    activo: Optional[bool] = None,
    updater_id: int = 1,
) -> str:
    """
    Actualiza los datos de un usuario existente en la base de datos.

    Args:
        user_id: ID numerico del usuario a actualizar.
        nombre: Nuevo nombre del usuario (opcional).
        apellido: Nuevo apellido del usuario (opcional).
        password: Nueva contrasena del usuario (opcional).
        activo: Nuevo estado activo/inactivo (opcional).
        updater_id: ID del usuario que realiza la actualizacion (por defecto: 1).

    Returns:
        str: Mensaje con el resultado de la operacion.
    """
    async def _actualizar():
        async for db in get_db():
            # Buscar el usuario
            resultado = await db.execute(select(User).where(User.id == user_id))
            usuario = resultado.scalar_one_or_none()

            if not usuario:
                return f"Usuario con ID {user_id} no encontrado."

            # Construir registro de cambios
            cambios = {}
            if nombre is not None:
                usuario.name = nombre
                cambios["name"] = nombre
            if apellido is not None:
                usuario.surname = apellido
                cambios["surname"] = apellido
            if password is not None:
                if not password.strip():
                    return "La contrasena no puede estar vacia."
                hashed = await asyncio.to_thread(
                    bcrypt.hashpw, password.encode(), bcrypt.gensalt()
                )
                usuario.password_hash = hashed.decode()
                cambios["password_updated"] = True
            if activo is not None:
                if not isinstance(activo, bool):
                    return "El campo 'activo' debe ser verdadero o falso."
                usuario.is_active = activo
                cambios["is_active"] = activo

            if not cambios:
                return "No se especificaron campos para actualizar."

            usuario.updated_by = updater_id
            usuario.updated_at = datetime.utcnow()

            # Guardar en BD
            await db.flush()

            # Registrar auditoria en MongoDB
            registro_auditoria = {
                "user_id": user_id,
                "updated_by": updater_id,
                "updated_at": usuario.updated_at.isoformat(),
                "changes": cambios,
            }
            await audit_collection.insert_one(registro_auditoria)

            campos = ", ".join(cambios.keys())
            return (
                f"Usuario #{user_id} actualizado correctamente. "
                f"Campos modificados: {campos}"
            )

    return asyncio.run(_actualizar())


# ─── Herramienta: validar_excel ────────────────────────────────────────────

@tool
def validar_excel(ruta_archivo: str) -> str:
    """
    Valida si un archivo Excel contiene codigo malicioso (macros, scripts, etc.).
    Usala SIEMPRE antes de leer el contenido de un archivo Excel.

    Args:
        ruta_archivo: Ruta completa al archivo .xlsx en el sistema.

    Returns:
        str: Resultado de la validacion indicando si es seguro o no.
    """
    if not os.path.exists(ruta_archivo):
        return f"El archivo '{ruta_archivo}' no existe en la ruta especificada."

    if not ruta_archivo.endswith(".xlsx"):
        return f"El archivo '{ruta_archivo}' no es un archivo .xlsx valido."

    resultado = validate_excel_safety(ruta_archivo)

    if resultado["safe"]:
        celdas = resultado["details"]["cells_analyzed"]
        hojas = resultado["details"]["sheets"]
        formulas = resultado["details"]["formulas_found"]
        return (
            f"Archivo seguro.\n"
            f"  - Hojas analizadas: {hojas}\n"
            f"  - Celdas revisadas: {celdas}\n"
            f"  - Formulas encontradas: {formulas}\n"
            f"  - No se detecto codigo malicioso."
        )
    else:
        errores = "\n".join(resultado["errors"][:5])  # Maximo 5 errores
        patrones = len(resultado["details"]["malicious_patterns_found"])
        return (
            f"Archivo potencialmente peligroso.\n"
            f"  - Patrones maliciosos detectados: {patrones}\n"
            f"  - Errores:\n{errores}"
        )


# ─── Herramienta: leer_excel ───────────────────────────────────────────────

@tool
def leer_excel(ruta_archivo: str) -> str:
    """
    Lee el contenido de un archivo Excel previamente validado como seguro.
    SOLO usar despues de haber validado el archivo con la herramienta validar_excel.

    Args:
        ruta_archivo: Ruta completa al archivo .xlsx en el sistema.

    Returns:
        str: Contenido del archivo Excel formateado para mostrar al usuario.
    """
    if not os.path.exists(ruta_archivo):
        return f"El archivo '{ruta_archivo}' no existe en la ruta especificada."

    contenido = get_safe_excel_content(ruta_archivo)

    if "error" in contenido:
        return f"Error al leer el archivo: {contenido['error']}"

    hojas = list(contenido["sheets"].keys())
    total_filas = contenido["metadata"]["rows"]
    total_columnas = contenido["metadata"]["columns"]

    # Formatear el contenido para mostrarlo de forma legible
    resultado = (
        f"Contenido del archivo:\n"
        f"  - Hojas: {', '.join(hojas)}\n"
        f"  - Total filas: {total_filas}\n"
        f"  - Total columnas: {total_columnas}\n\n"
    )

    for nombre_hoja, datos in contenido["sheets"].items():
        resultado += f"Hoja: '{nombre_hoja}'\n"
        if not datos:
            resultado += "  (Hoja vacia)\n"
            continue

        # Mostrar las primeras 10 filas como vista previa
        filas_mostrar = datos[:10]
        for i, fila in enumerate(filas_mostrar):
            fila_texto = " | ".join(str(c) for c in fila)
            resultado += f"  Fila {i+1}: {fila_texto}\n"

        if len(datos) > 10:
            resultado += f"  ... y {len(datos) - 10} filas mas.\n"
        resultado += "\n"

    return resultado
