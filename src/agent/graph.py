"""
MÓDULO ORQUESTADOR DEL GRAFO DE ESTADOS (LANGGRAPH STATEGRAPH)
==============================================================
Este archivo ensambla los nodos y define las aristas condicionales (`add_conditional_edges`)
que deciden por qué camino debe avanzar el agente en tiempo de ejecución.
Además, cronometra la latencia en milisegundos y guarda la telemetría en la base de datos.
"""

import time
import uuid
from typing import Dict, Any
from langgraph.graph import StateGraph, START, END
from src.agent.state import OperationsAgentState
from src.agent.nodes import (
    classify_and_plan_node,
    execute_tool_node,
    human_escalation_node,
    synthesize_response_node,
)
from src.monitoring.telemetry import log_agent_telemetry


def _route_after_planning(state: OperationsAgentState) -> str:
    """
    Primera decisión condicional:
    - Si el clasificador seleccionó una herramienta SQL (`tool_name`), va al nodo `execute_tool`.
    - Si es una consulta general que no requiere tocar la base de datos, salta a `synthesize_response`.
    """
    if state.get("tool_name"):
        return "execute_tool"
    return "synthesize_response"


def _route_after_tool(state: OperationsAgentState) -> str:
    """
    Segunda decisión condicional:
    - Si la intención es un reclamo o garantía (`RETURN_OR_ESCALATION`), pasa por `human_escalation`.
    - En caso contrario, va directo a redactar la respuesta final (`synthesize_response`).
    """
    if state.get("intent") == "RETURN_OR_ESCALATION":
        return "human_escalation"
    return "synthesize_response"


def build_operations_graph():
    """Construye y compila la máquina de estados (`StateGraph`) de LangGraph."""
    workflow = StateGraph(OperationsAgentState)

    # 1. Registrar los 4 nodos de procesamiento
    workflow.add_node("classify_and_plan", classify_and_plan_node)
    workflow.add_node("execute_tool", execute_tool_node)
    workflow.add_node("human_escalation", human_escalation_node)
    workflow.add_node("synthesize_response", synthesize_response_node)

    # 2. Conectar el flujo inicial y las bifurcaciones condicionales
    workflow.add_edge(START, "classify_and_plan")
    workflow.add_conditional_edges(
        "classify_and_plan",
        _route_after_planning,
        {
            "execute_tool": "execute_tool",
            "synthesize_response": "synthesize_response",
        },
    )
    workflow.add_conditional_edges(
        "execute_tool",
        _route_after_tool,
        {
            "human_escalation": "human_escalation",
            "synthesize_response": "synthesize_response",
        },
    )
    workflow.add_edge("human_escalation", "synthesize_response")
    workflow.add_edge("synthesize_response", END)

    return workflow.compile()


# Instancia compilada del grafo lista para ser invocada desde la API o el Dashboard
compiled_graph = build_operations_graph()


def run_operations_agent(
    user_query: str, session_id: str | None = None
) -> Dict[str, Any]:
    """
    Función principal que ejecuta el agente de principio a fin:
    1. Inicia un cronómetro de alta precisión (`time.perf_counter()`).
    2. Ejecuta el grafo de estados de LangGraph.
    3. Calcula cuántos milisegundos tardó (`latency_ms`) y guarda la métrica en `agent_telemetry`.
    """
    sess_id = session_id or f"sess-{uuid.uuid4().hex[:8]}"
    start_ts = time.perf_counter()

    # Estado inicial limpio antes de entrar al primer nodo
    initial_state: OperationsAgentState = {
        "session_id": sess_id,
        "user_query": user_query,
        "intent": "GENERAL_POLICY",
        "reasoning_steps": [],
        "tool_name": None,
        "tool_args": {},
        "tool_output": None,
        "requires_human_escalation": False,
        "final_response": "",
        "model_used": "gemini-3.8-flash",
        "tokens_used": 0,
        "latency_ms": 0.0,
        "status": "SUCCESS",
    }

    try:
        # Invoca la máquina de estados de LangGraph
        final_state = compiled_graph.invoke(initial_state)
        elapsed_ms = (time.perf_counter() - start_ts) * 1000.0
        final_state["latency_ms"] = round(elapsed_ms, 2)

        # Registra la telemetría en la base de datos para actualizar el dashboard en tiempo real
        log_agent_telemetry(
            session_id=sess_id,
            user_query=user_query,
            intent=final_state.get("intent", "GENERAL_POLICY"),
            tool_called=final_state.get("tool_name"),
            model_name=final_state.get("model_used", "gemini-3.8-flash"),
            latency_ms=elapsed_ms,
            tokens_used=final_state.get("tokens_used", 250),
            status=final_state.get("status", "SUCCESS"),
            reasoning_trace=" -> ".join(final_state.get("reasoning_steps", [])),
        )
        return final_state

    except Exception as exc:
        elapsed_ms = (time.perf_counter() - start_ts) * 1000.0
        log_agent_telemetry(
            session_id=sess_id,
            user_query=user_query,
            intent="ERROR",
            tool_called="none",
            model_name="gemini-3.8-flash",
            latency_ms=elapsed_ms,
            tokens_used=0,
            status="ERROR",
            reasoning_trace=f"Excepción: {str(exc)}",
        )
        raise
