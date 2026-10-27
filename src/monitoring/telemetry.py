"""
MÓDULO DE TELEMETRÍA Y CÁLCULO DE KPIs EN TIEMPO REAL
=====================================================
Se encarga de insertar los registros de ejecución en la tabla `agent_telemetry`
y calcular las métricas clave del Dashboard (latencia promedio, tasa de error,
tasa de escalamiento humano, volumen de llamadas y tokens procesados).
"""

from typing import Dict, Any, List
from sqlalchemy import func
from src.database.connection import get_db_context
from src.database.models import AgentTelemetry


def log_agent_telemetry(
    session_id: str,
    user_query: str,
    intent: str,
    tool_called: str | None,
    model_name: str,
    latency_ms: float,
    tokens_used: int,
    status: str,
    reasoning_trace: str,
) -> None:
    """Guarda un nuevo registro de telemetría en la base de datos tras cada llamada al agente."""
    with get_db_context() as db:
        record = AgentTelemetry(
            session_id=session_id,
            user_query=user_query,
            intent=intent,
            tool_called=tool_called or "none",
            model_name=model_name,
            latency_ms=round(latency_ms, 2),
            tokens_used=tokens_used,
            status=status,
            reasoning_trace=reasoning_trace,
        )
        db.add(record)
        db.commit()


def get_telemetry_kpis() -> Dict[str, Any]:
    """
    Ejecuta consultas de agregación SQL (COUNT, AVG, SUM, GROUP BY) sobre `agent_telemetry`
    para alimentar las tarjetas de KPIs y los gráficos del Dashboard en tiempo real.
    """
    with get_db_context() as db:
        total_calls = db.query(func.count(AgentTelemetry.id)).scalar() or 0
        if total_calls == 0:
            return {
                "total_calls": 0,
                "avg_latency_ms": 0.0,
                "error_rate_pct": 0.0,
                "escalation_rate_pct": 0.0,
                "total_tokens": 0,
                "by_intent": {},
                "recent_logs": [],
            }

        # Cálculo de promedios y sumatorias directamente en el motor SQL
        avg_latency = db.query(func.avg(AgentTelemetry.latency_ms)).scalar() or 0.0
        total_tokens = db.query(func.sum(AgentTelemetry.tokens_used)).scalar() or 0
        error_count = (
            db.query(func.count(AgentTelemetry.id))
            .filter(AgentTelemetry.status == "ERROR")
            .scalar()
            or 0
        )
        escalated_count = (
            db.query(func.count(AgentTelemetry.id))
            .filter(AgentTelemetry.status == "HUMAN_ESCALATED")
            .scalar()
            or 0
        )

        # Agrupación del volumen de llamadas por tipo de intención operativa
        intent_rows = (
            db.query(AgentTelemetry.intent, func.count(AgentTelemetry.id))
            .group_by(AgentTelemetry.intent)
            .all()
        )
        by_intent = {intent: count for intent, count in intent_rows}

        # Obtiene las últimas 25 ejecuciones para la tabla de monitoreo en vivo
        recent_rows: List[AgentTelemetry] = (
            db.query(AgentTelemetry)
            .order_by(AgentTelemetry.timestamp.desc())
            .limit(25)
            .all()
        )
        recent_logs = [
            {
                "id": r.id,
                "session_id": r.session_id,
                "timestamp": r.timestamp.strftime("%Y-%m-%d %H:%M:%S")
                if r.timestamp
                else "",
                "user_query": r.user_query,
                "intent": r.intent,
                "tool_called": r.tool_called,
                "model_name": r.model_name,
                "latency_ms": round(r.latency_ms, 1),
                "tokens_used": r.tokens_used,
                "status": r.status,
                "reasoning_trace": r.reasoning_trace,
            }
            for r in recent_rows
        ]

        return {
            "total_calls": total_calls,
            "avg_latency_ms": round(float(avg_latency), 1),
            "error_rate_pct": round((error_count / total_calls) * 100, 2),
            "escalation_rate_pct": round((escalated_count / total_calls) * 100, 2),
            "total_tokens": int(total_tokens),
            "by_intent": by_intent,
            "recent_logs": recent_logs,
        }
