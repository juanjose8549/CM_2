"""
Tests unitarios para el modulo del agente AI.
Verifica la configuracion de proveedores LLM y la creacion del agente.
"""

import os
import pytest
from unittest.mock import patch, MagicMock

from agent.config import obtener_llm, PROVEEDORES


# ─── Tests de configuracion de proveedores ─────────────────────────────────

def test_proveedores_soportados():
    """Verifica que los proveedores configurados sean validos."""
    assert "openai" in PROVEEDORES
    assert "deepseek" in PROVEEDORES
    assert "modelo" in PROVEEDORES["openai"]
    assert "modelo" in PROVEEDORES["deepseek"]
    assert "base_url" in PROVEEDORES["openai"]
    assert "base_url" in PROVEEDORES["deepseek"]


def test_obtener_llm_openai(monkeypatch):
    """Verifica que se configure OpenAI correctamente."""
    monkeypatch.setenv("LLM_PROVIDER", "openai")
    monkeypatch.setenv("OPENAI_API_KEY", "test-key-openai")

    with patch("agent.config.ChatOpenAI") as mock_chat:
        mock_instance = MagicMock()
        mock_chat.return_value = mock_instance

        llm = obtener_llm()

        mock_chat.assert_called_once_with(
            model="gpt-4o-mini",
            api_key="test-key-openai",
            base_url=None,
            temperature=0.1,
            max_tokens=4096,
        )
        assert llm == mock_instance


def test_obtener_llm_deepseek(monkeypatch):
    """Verifica que se configure DeepSeek correctamente."""
    monkeypatch.setenv("LLM_PROVIDER", "deepseek")
    monkeypatch.setenv("DEEPSEEK_API_KEY", "test-key-deepseek")

    with patch("agent.config.ChatOpenAI") as mock_chat:
        mock_instance = MagicMock()
        mock_chat.return_value = mock_instance

        llm = obtener_llm()

        mock_chat.assert_called_once_with(
            model="deepseek-chat",
            api_key="test-key-deepseek",
            base_url="https://api.deepseek.com/v1",
            temperature=0.1,
            max_tokens=4096,
        )
        assert llm == mock_instance


def test_proveedor_no_soportado(monkeypatch):
    """Verifica que lanza error con proveedor invalido."""
    monkeypatch.setenv("LLM_PROVIDER", "proveedor_invalido")

    with pytest.raises(ValueError, match="Proveedor LLM no soportado"):
        obtener_llm()


def test_falta_api_key(monkeypatch):
    """Verifica que lanza error si falta la API key."""
    monkeypatch.setenv("LLM_PROVIDER", "openai")
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    with pytest.raises(ValueError, match="Falta la variable de entorno"):
        obtener_llm()


def test_falta_api_key_deepseek(monkeypatch):
    """Verifica que lanza error si falta la API key de DeepSeek."""
    monkeypatch.setenv("LLM_PROVIDER", "deepseek")
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)

    with pytest.raises(ValueError, match="Falta la variable de entorno"):
        obtener_llm()


# ─── Tests del agente ──────────────────────────────────────────────────────

def test_crear_agente(monkeypatch):
    """Verifica que se crea el agente correctamente."""
    monkeypatch.setenv("LLM_PROVIDER", "openai")
    monkeypatch.setenv("OPENAI_API_KEY", "test-key-openai")

    with patch("agent.agente.obtener_llm") as mock_obtener_llm, \
         patch("agent.agente.create_react_agent") as mock_create_agent, \
         patch("agent.agente.AgentExecutor") as mock_executor:

        # Configurar mocks
        mock_llm = MagicMock()
        mock_obtener_llm.return_value = mock_llm

        mock_agent = MagicMock()
        mock_create_agent.return_value = mock_agent

        mock_executor_instance = MagicMock()
        mock_executor.return_value = mock_executor_instance

        # Importar y ejecutar
        from agent.agente import crear_agente
        resultado = crear_agente()

        # Verificar que se crearon los componentes
        mock_obtener_llm.assert_called_once()
        mock_create_agent.assert_called_once()
        mock_executor.assert_called_once()

        assert resultado == mock_executor_instance


@pytest.mark.asyncio
async def test_ejecutar_consulta_exitosa(monkeypatch):
    """Verifica que ejecutar_consulta retorna la respuesta del agente."""
    monkeypatch.setenv("LLM_PROVIDER", "openai")
    monkeypatch.setenv("OPENAI_API_KEY", "test-key-openai")

    mock_ejecutor = MagicMock()
    # ainvoke debe ser una coroutine para que await funcione
    async def mock_ainvoke(*args, **kwargs):
        return {"output": "Respuesta del agente"}
    mock_ejecutor.ainvoke = mock_ainvoke

    from agent.agente import ejecutar_consulta
    respuesta = await ejecutar_consulta(mock_ejecutor, "Hola")

    assert respuesta == "Respuesta del agente"


@pytest.mark.asyncio
async def test_ejecutar_consulta_error(monkeypatch):
    """Verifica que ejecutar_consulta maneja errores."""
    monkeypatch.setenv("LLM_PROVIDER", "openai")
    monkeypatch.setenv("OPENAI_API_KEY", "test-key-openai")

    mock_ejecutor = MagicMock()
    mock_ejecutor.ainvoke.side_effect = Exception("Error de prueba")

    from agent.agente import ejecutar_consulta
    respuesta = await ejecutar_consulta(mock_ejecutor, "Hola")

    assert "Error de prueba" in respuesta


# ─── Tests del endpoint /agent/chat ────────────────────────────────────────

@pytest.mark.asyncio
async def test_chat_agente_mensaje_valido():
    """Verifica que el endpoint /agent/chat responde correctamente."""
    from main import app
    import main as main_module

    # Simular que el agente ya esta inicializado
    mock_agente = MagicMock()
    async def mock_ainvoke(*args, **kwargs):
        return {"output": "Respuesta de prueba"}
    mock_agente.ainvoke = mock_ainvoke
    main_module.agente_ejecutor = mock_agente

    # Usar TestClient de Starlette directamente
    from starlette.testclient import TestClient
    client = TestClient(app)
    response = client.post("/agent/chat", json={"mensaje": "Hola"})

    assert response.status_code == 200
    assert "respuesta" in response.json()


@pytest.mark.asyncio
async def test_chat_agente_mensaje_vacio():
    """Verifica que el endpoint rechaza mensajes vacios."""
    from main import app
    import main as main_module

    mock_agente = MagicMock()
    main_module.agente_ejecutor = mock_agente

    from starlette.testclient import TestClient
    client = TestClient(app)
    response = client.post("/agent/chat", json={"mensaje": ""})

    assert response.status_code == 400


@pytest.mark.asyncio
async def test_chat_agente_sin_agente():
    """Verifica que el endpoint da error 503 si el agente no esta inicializado."""
    from main import app
    import main as main_module

    main_module.agente_ejecutor = None

    from starlette.testclient import TestClient
    client = TestClient(app)
    response = client.post("/agent/chat", json={"mensaje": "Hola"})

    assert response.status_code == 503
    data = response.json()
    # FastAPI usa "detail" para los errores HTTPException
    assert "detail" in data
