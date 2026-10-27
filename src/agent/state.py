"""
MÓDULO DE ESTADO DEL AGENTE (MEMORIA DE TRABAJO EN LANGGRAPH)
=============================================================
Define el diccionario tipado (`OperationsAgentState`) que viaja a través
de todos los nodos del grafo de LangGraph.
Cada nodo lee información de este estado y escribe sus resultados aquí.
"""

from typing import TypedDict, List, Dict, Any, Optional


class OperationsAgentState(TypedDict):
    """Estructura de datos que comparte información entre todos los nodos del grafo."""

    # Identificador único de la sesión del usuario para trazabilidad
    session_id: str

    # Mensaje original escrito por el cliente
    user_query: str

    # Intención detectada: ORDER_STATUS, INVENTORY_CHECK, UPDATE_ADDRESS, RETURN_OR_ESCALATION o GENERAL_POLICY
    intent: str

    # Lista de pasos de razonamiento Chain-of-Thought que se muestran en la interfaz
    reasoning_steps: List[str]

    # Nombre de la herramienta SQL seleccionada y sus argumentos de entrada
    tool_name: Optional[str]
    tool_args: Dict[str, Any]

    # Resultado en formato diccionario devuelto por la base de datos tras ejecutar la herramienta
    tool_output: Optional[Dict[str, Any]]

    # Bandera que indica si el caso requiere intervención de un supervisor humano (Human-in-the-Loop)
    requires_human_escalation: bool

    # Respuesta final redactada para el cliente
    final_response: str

    # Métricas técnicas capturadas para el Dashboard de Monitoreo en Tiempo Real
    model_used: str
    tokens_used: int
    latency_ms: float
    status: str  # Valores posibles: SUCCESS, ERROR, HUMAN_ESCALATED
