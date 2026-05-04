"""
Configuración del modelo de lenguaje (LLM) para el agente.
Soporta múltiples proveedores: OpenAI, DeepSeek, y otros compatibles con la API de OpenAI.
"""

import os
from langchain_openai import ChatOpenAI

# ─── Proveedores soportados ────────────────────────────────────────────────
# Se pueden agregar más proveedores compatibles con la API de OpenAI aquí.
PROVEEDORES = {
    "openai": {
        "modelo": "gpt-4o-mini",
        "base_url": None,  # Usa la URL por defecto de OpenAI
        "descripcion": "OpenAI GPT-4o Mini (rápido y económico)",
    },
    "deepseek": {
        "modelo": "deepseek-chat",
        "base_url": "https://api.deepseek.com/v1",
        "descripcion": "DeepSeek Chat (modelo eficiente y económico)",
    },
}


def obtener_llm():
    """
    Configura y retorna el modelo de lenguaje según la variable LLM_PROVIDER.

    Lee del archivo .env:
        LLM_PROVIDER: "openai" (por defecto) o "deepseek"
        OPENAI_API_KEY: clave API de OpenAI (si el proveedor es openai)
        DEEPSEEK_API_KEY: clave API de DeepSeek (si el proveedor es deepseek)

    Returns:
        ChatOpenAI: Instancia configurada del modelo de lenguaje.

    Raises:
        ValueError: Si el proveedor no está soportado o falta la API key.
    """
    proveedor = os.getenv("LLM_PROVIDER", "openai").lower()

    if proveedor not in PROVEEDORES:
        proveedores_validos = ", ".join(PROVEEDORES.keys())
        raise ValueError(
            f"Proveedor LLM no soportado: '{proveedor}'. "
            f"Usa uno de: {proveedores_validos}"
        )

    config = PROVEEDORES[proveedor]
    variable_api_key = f"{proveedor.upper()}_API_KEY"
    api_key = os.getenv(variable_api_key)

    if not api_key:
        raise ValueError(
            f"Falta la variable de entorno {variable_api_key} "
            f"para el proveedor '{proveedor}'"
        )

    print(f"🤖 Inicializando LLM con proveedor: '{proveedor}' "
          f"(modelo: {config['modelo']})")

    return ChatOpenAI(
        model=config["modelo"],
        api_key=api_key,
        base_url=config["base_url"],
        temperature=0.1,   # Baja temperatura = respuestas más precisas
        max_tokens=4096,   # Límite de tokens por respuesta
    )
