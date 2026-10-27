"""
MÓDULO DE ESQUEMAS DE VALIDACIÓN (PYDANTIC)
===========================================
Define la estructura exacta de los datos JSON de entrada (`ChatRequest`)
y de salida (`ChatResponse`) para la API REST en FastAPI.
"""

from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    """Estructura JSON que recibe el endpoint POST /api/v1/chat."""

    query: str = Field(
        ...,
        min_length=2,
        description="Consulta o instrucción del cliente para el agente de operaciones.",
        examples=["¿Cuál es el estado de mi pedido ORD-1001?"],
    )
    session_id: Optional[str] = Field(
        default=None, description="ID de sesión opcional para trazabilidad."
    )


class ChatResponse(BaseModel):
    """Estructura JSON que devuelve la API con la respuesta del agente y sus métricas."""

    session_id: str
    intent: str
    tool_called: Optional[str] = None
    tool_output: Optional[Dict[str, Any]] = None
    reasoning_steps: List[str]
    requires_human_escalation: bool
    response: str
    model_used: str
    latency_ms: float
    tokens_used: int
    status: str
