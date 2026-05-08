"""
Configuración del modelo de lenguaje (LLM) para el agente.
Soporta múltiples proveedores: OpenAI, DeepSeek, NVIDIA NIM, y otros
compatibles con la API de OpenAI.
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
    "nvidia": {
        "modelo": "meta/llama-3.3-70b-instruct",
        "base_url": "https://integrate.api.nvidia.com/v1",
        "descripcion": "NVIDIA NIM: Llama 3.3 70B (gratuito con rate limit, requiere registro en build.nvidia.com)",
        "alternativos": [
            "meta/llama-3.1-8b-instruct",
            "meta/llama-3.1-70b-instruct",
            "meta/llama-3.2-3b-instruct",
            "google/gemma-3-12b-it",
            "google/gemma-2-2b-it",
            "microsoft/phi-4-mini-instruct",
            "qwen/qwen2.5-coder-32b-instruct",
            "deepseek-ai/deepseek-coder-6.7b-instruct",
            "mistralai/mistral-7b-instruct-v0.3",
            "mistralai/mixtral-8x7b-instruct-v0.1",
        ],
    },
}


def obtener_llm():
    """
    Configura y retorna el modelo de lenguaje según la variable LLM_PROVIDER.

    Lee del archivo .env:
        LLM_PROVIDER: "openai" (por defecto), "deepseek" o "nvidia"
        OPENAI_API_KEY: clave API de OpenAI (si el proveedor es openai)
        DEEPSEEK_API_KEY: clave API de DeepSeek (si el proveedor es deepseek)
        NVIDIA_API_KEY: clave API de NVIDIA NIM (si el proveedor es nvidia)

    Opcionalmente, se puede sobrescribir el modelo con LLM_MODEL:
        LLM_MODEL: "gpt-4o" (para openai) o "mistralai/mistral-large" (para nvidia)

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

    # Permitir sobrescribir el modelo desde variable de entorno
    # LLM_MODEL funciona para cualquier proveedor
    modelo = os.getenv("LLM_MODEL", config["modelo"])

    print(f"Inicializando LLM con proveedor: '{proveedor}' "
          f"(modelo: {modelo})")

    return ChatOpenAI(
        model=modelo,
        api_key=api_key,
        base_url=config["base_url"],
        temperature=0.1,   # Baja temperatura = respuestas más precisas
        max_tokens=4096,   # Límite de tokens por respuesta
    )
