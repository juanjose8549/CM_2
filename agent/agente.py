"""
Configuracion del agente AI usando LangChain.
Crea un agente ReAct (Reasoning + Acting) que puede usar herramientas
para interactuar con el sistema.
"""

from langchain.agents import create_react_agent, AgentExecutor
from langchain.prompts import PromptTemplate
from langchain.tools import Tool

from agent.config import obtener_llm
from agent.herramientas import (
    actualizar_usuario,
    validar_excel,
    leer_excel,
    buscar_usuario,
)
from agent.prompts import PROMPT_REACT


def crear_agente() -> AgentExecutor:
    """
    Crea y configura el agente LangChain con el LLM seleccionado.

    El agente usa el patron ReAct (Reasoning + Acting) donde:
    1. Recibe un mensaje del usuario
    2. El LLM razona que accion tomar
    3. Ejecuta la herramienta correspondiente
    4. Analiza el resultado y responde al usuario

    Returns:
        AgentExecutor: Ejecutor del agente listo para procesar consultas.
    """
    # Obtener el modelo de lenguaje configurado
    llm = obtener_llm()

    # Lista de herramientas disponibles para el agente
    herramientas = [
        Tool(
            name=actualizar_usuario.name,
            func=actualizar_usuario,
            description=(
                "Actualiza los datos de un usuario existente. "
                "Recibe user_id (int), nombre (str, opcional), apellido (str, opcional), "
                "password (str, opcional), activo (bool, opcional), updater_id (int, opcional). "
                "Usa esta herramienta cuando el usuario quiera modificar datos de un usuario."
            ),
        ),
        Tool(
            name=validar_excel.name,
            func=validar_excel,
            description=(
                "Valida si un archivo Excel contiene codigo malicioso. "
                "Recibe ruta_archivo (str) - la ruta completa al archivo .xlsx. "
                "Usa SIEMPRE esta herramienta antes de leer un archivo Excel."
            ),
        ),
        Tool(
            name=leer_excel.name,
            func=leer_excel,
            description=(
                "Lee el contenido de un archivo Excel previamente validado. "
                "Recibe ruta_archivo (str) - la ruta completa al archivo .xlsx. "
                "SOLO usar despues de validar el archivo con validar_excel."
            ),
        ),
        Tool(
            name=buscar_usuario.name,
            func=buscar_usuario,
            description=(
                "Busca un usuario por su ID y devuelve su informacion. "
                "Recibe user_id (int). "
                "Usa esta herramienta cuando el usuario pregunte por datos de un usuario."
            ),
        ),
    ]

    # Crear el prompt del agente en formato ReAct
    # create_react_agent requiere que el template contenga
    # {tools}, {tool_names} y {agent_scratchpad} como variables
    prompt = PromptTemplate.from_template(PROMPT_REACT)

    # Crear el agente ReAct
    agente = create_react_agent(llm, herramientas, prompt)

    # Crear el ejecutor del agente
    ejecutor = AgentExecutor(
        agent=agente,
        tools=herramientas,
        verbose=True,  # Muestra el razonamiento del agente en consola
        handle_parsing_errors=True,
        max_iterations=5,  # Limite para evitar loops infinitos
        max_execution_time=60,  # Timeout de 60 segundos
    )

    return ejecutor


async def ejecutar_consulta(ejecutor: AgentExecutor, mensaje: str) -> str:
    """
    Envia un mensaje al agente y retorna su respuesta.

    Args:
        ejecutor: AgentExecutor creado con crear_agente().
        mensaje: Consulta del usuario en lenguaje natural.

    Returns:
        str: Respuesta generada por el agente.
    """
    try:
        resultado = await ejecutor.ainvoke({"input": mensaje})
        return resultado["output"]
    except Exception as e:
        return f"Ocurrio un error al procesar tu solicitud: {str(e)}"
