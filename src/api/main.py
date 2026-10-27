"""
SERVIDOR DE API REST MODULAR (FASTAPI)
======================================
Expone el agente de LangGraph y las métricas de telemetría a través de endpoints HTTP
para que puedan conectarse aplicaciones externas (React, WhatsApp, sistemas ERP).
"""

from contextlib import asynccontextmanager
from fastapi import FastAPI, Depends
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session

from src.database.connection import init_db, get_db
from src.database.models import Order, Product, SupportTicket
from src.api.schemas import ChatRequest, ChatResponse
from src.agent.graph import run_operations_agent
from src.monitoring.telemetry import get_telemetry_kpis


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Al encender el servidor FastAPI, inicializa la base de datos automáticamente."""
    init_db()
    yield


app = FastAPI(
    title="Enterprise Operations AI Agent API",
    description=(
        "API REST modular con LangGraph, Google Gemini 3.8 Flash, PostgreSQL/SQLite "
        "y telemetría operativa en tiempo real."
    ),
    version="1.0.0",
    lifespan=lifespan,
)

# Configuración de CORS para permitir consumo desde cualquier frontend web
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health", tags=["Sistema"])
def health_check():
    """Verifica que el servicio de API se encuentre activo."""
    return {
        "status": "healthy",
        "service": "enterprise-operations-agent",
        "engine": "LangGraph + Gemini 3.8 Flash",
    }


@app.post("/api/v1/chat", response_model=ChatResponse, tags=["Agente IA"])
def chat_with_agent(payload: ChatRequest):
    """Ejecuta el grafo de estados de LangGraph y retorna la respuesta junto con su traza Chain-of-Thought."""
    state = run_operations_agent(user_query=payload.query, session_id=payload.session_id)
    return ChatResponse(
        session_id=state["session_id"],
        intent=state["intent"],
        tool_called=state.get("tool_name"),
        tool_output=state.get("tool_output"),
        reasoning_steps=state.get("reasoning_steps", []),
        requires_human_escalation=state.get("requires_human_escalation", False),
        response=state["final_response"],
        model_used=state.get("model_used", "gemini-3.8-flash"),
        latency_ms=state.get("latency_ms", 0.0),
        tokens_used=state.get("tokens_used", 0),
        status=state.get("status", "SUCCESS"),
    )


@app.get("/api/v1/metrics", tags=["Monitoreo"])
def get_metrics():
    """Devuelve los indicadores operativos en tiempo real (latencia, tasa de error, llamadas y tokens)."""
    return get_telemetry_kpis()


@app.get("/api/v1/orders", tags=["Datos Operativos"])
def list_orders(db: Session = Depends(get_db)):
    """Lista todos los pedidos registrados en la base de datos."""
    orders = db.query(Order).all()
    return [
        {
            "order_code": o.order_code,
            "product_sku": o.product_sku,
            "quantity": o.quantity,
            "total_amount": o.total_amount,
            "status": o.status,
            "shipping_address": o.shipping_address,
            "carrier": o.carrier,
            "tracking_number": o.tracking_number,
        }
        for o in orders
    ]


@app.get("/api/v1/inventory", tags=["Datos Operativos"])
def list_inventory(db: Session = Depends(get_db)):
    """Lista el catálogo completo de productos y niveles de stock."""
    products = db.query(Product).all()
    return [
        {
            "sku": p.sku,
            "name": p.name,
            "category": p.category,
            "price": p.price,
            "stock": p.stock,
            "warehouse_location": p.warehouse_location,
        }
        for p in products
    ]


@app.get("/api/v1/tickets", tags=["Datos Operativos"])
def list_tickets(db: Session = Depends(get_db)):
    """Lista los tickets de soporte y garantía escalados a especialistas humanos."""
    tickets = db.query(SupportTicket).order_by(SupportTicket.created_at.desc()).all()
    return [
        {
            "ticket_code": t.ticket_code,
            "order_code": t.order_code,
            "customer_email": t.customer_email,
            "issue_type": t.issue_type,
            "description": t.description,
            "priority": t.priority,
            "status": t.status,
        }
        for t in tickets
    ]
