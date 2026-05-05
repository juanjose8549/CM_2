"""
Configuracion del agente AI usando LangChain.
"""

from langchain.agents import create_react_agent, AgentExecutor
from langchain.prompts import PromptTemplate
from langchain.tools import Tool

from agent.config import obtener_llm
from agent.herramientas import (
    actualizar_usuario,
    actualizar_usuario_async,
    validar_excel,
    validar_excel_async,
    leer_excel,
    leer_excel_async,
    buscar_usuario,
    buscar_usuario_async,
    listar_usuarios,
    listar_usuarios_async,
)
from agent.prompts import PROMPT_SISTEMA


def crear_agente() -> AgentExecutor:
    llm = obtener_llm()

    herramientas = [
        Tool(
            name="buscar_usuario",
            func=buscar_usuario,
            coroutine=buscar_usuario_async,
            description=(
                "Busca un usuario por su ID. Input: el ID como numero o JSON. "
                "Ejemplo: '1' o {\"user_id\": 3}"
            ),
        ),
        Tool(
            name="actualizar_usuario",
            func=actualizar_usuario,
            coroutine=actualizar_usuario_async,
            description=(
                "Actualiza datos de un usuario. Input: JSON con campos a modificar. "
                "Ejemplo: {\"user_id\": 1, \"nombre\": \"Juan\"}"
            ),
        ),
        Tool(
            name="validar_excel",
            func=validar_excel,
            coroutine=validar_excel_async,
            description=(
                "Valida si un Excel tiene codigo malicioso. Input: ruta del archivo. "
                "Ejemplo: '/ruta/archivo.xlsx'"
            ),
        ),
        Tool(
            name="leer_excel",
            func=leer_excel,
            coroutine=leer_excel_async,
            description=(
                "Lee contenido de un Excel validado. Input: ruta del archivo. "
                "Ejemplo: '/ruta/archivo.xlsx'"
            ),
        ),
        Tool(
            name="listar_usuarios",
            func=listar_usuarios,
            coroutine=listar_usuarios_async,
            description=(
                "Lista todos los usuarios registrados en la base de datos, "
                "mostrando su ID, nombre, apellido y estado (activo/inactivo). "
                "Tambien devuelve el total de usuarios, activos e inactivos. "
                "Input: cualquier texto (se ignora), ej: 'listar' o 'contar'"
            ),
        ),
    ]

    # Prompt con instrucciones explicitas para DeepSeek
    # DeepSeek necesita ver ejemplos concretos del formato esperado
    template = (
        "Eres un asistente AI. Sigue el formato paso a paso.\n\n"
        "{sistema}\n\n"
        "Herramientas:\n"
        "{tools}\n\n"
        "Debes responder con este formato:\n"
        "Thought: tu razonamiento\n"
        "Action: nombre de la herramienta de [{tool_names}]\n"
        "Action Input: string con los argumentos\n"
        "Observation: resultado de la herramienta\n"
        "... (repite si es necesario)\n"
        "Thought: ya tengo la respuesta\n"
        "Final Answer: tu respuesta\n\n"
        "Ejemplo:\n"
        "Question: Busca el usuario 1\n"
        "Thought: Necesito buscar al usuario con ID 1\n"
        "Action: buscar_usuario\n"
        "Action Input: 1\n"
        "Observation: Datos del usuario...\n"
        "Thought: Ya tengo los datos\n"
        "Final Answer: Aqui esta la informacion...\n\n"
        "Comienza:\n\n"
        "Question: {input}\n"
        "Thought:{agent_scratchpad}"
    )
    prompt = PromptTemplate.from_template(template)
    prompt = prompt.partial(sistema=PROMPT_SISTEMA)

    agente = create_react_agent(llm, herramientas, prompt)

    ejecutor = AgentExecutor(
        agent=agente,
        tools=herramientas,
        verbose=True,
        handle_parsing_errors=True,
        max_iterations=15,
        max_execution_time=60,
    )

    return ejecutor


async def ejecutar_consulta(ejecutor: AgentExecutor, mensaje: str) -> str:
    try:
        resultado = await ejecutor.ainvoke({"input": mensaje})
        return resultado["output"]
    except Exception as e:
        return f"Ocurrio un error al procesar tu solicitud: {str(e)}"
