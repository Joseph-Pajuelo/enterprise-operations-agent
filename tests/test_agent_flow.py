"""
SUITE DE PRUEBAS AUTOMATIZADAS (PYTEST)
=======================================
Verifica que todos los nodos del grafo de LangGraph, las reglas de negocio logísticas,
el escalamiento Human-in-the-Loop y los endpoints de FastAPI funcionen correctamente.
"""

from fastapi.testclient import TestClient
from src.database.connection import init_db
from src.agent.graph import run_operations_agent
from src.api.main import app


def setup_module():
    """Inicializa la base de datos antes de ejecutar las pruebas."""
    init_db()


def test_order_status_flow():
    """Prueba 1: Consulta del estado del pedido ORD-1001."""
    state = run_operations_agent("¿Cuál es el estado de mi pedido ORD-1001?")
    assert state["intent"] == "ORDER_STATUS"
    assert state["tool_name"] == "get_order_details"
    assert state["tool_output"]["found"] is True
    assert state["tool_output"]["order_code"] == "ORD-1001"
    assert state["status"] == "SUCCESS"


def test_inventory_check_flow():
    """Prueba 2: Consulta de stock disponible en el inventario."""
    state = run_operations_agent("¿Tienen stock disponible del monitor 4K?")
    assert state["intent"] == "INVENTORY_CHECK"
    assert state["tool_name"] == "check_product_inventory"
    assert state["tool_output"]["count"] >= 1


def test_address_update_business_rules():
    """Prueba 3: Verifica que un pedido en ruta (IN_TRANSIT) bloquee el cambio y uno en almacén lo permita."""
    # ORD-1002 está IN_TRANSIT -> debe bloquear el cambio automático de dirección
    blocked = run_operations_agent(
        "Quiero cambiar la dirección de mi pedido ORD-1002 a Av. Javier Prado 500"
    )
    assert blocked["intent"] == "UPDATE_ADDRESS"
    assert blocked["tool_output"]["updated"] is False

    # ORD-1001 está PROCESSING -> debe permitir el cambio automático de dirección
    allowed = run_operations_agent(
        "Quiero cambiar la dirección de ORD-1001 a Av. Primavera 1520, Surco"
    )
    assert allowed["intent"] == "UPDATE_ADDRESS"
    assert allowed["tool_output"]["updated"] is True


def test_return_human_in_the_loop_escalation():
    """Prueba 4: Verifica que un reclamo por producto dañado genere ticket y escale a humano."""
    state = run_operations_agent(
        "Mi pedido ORD-1003 llegó dañado con una tecla rota, solicito garantía urgente"
    )
    assert state["intent"] == "RETURN_OR_ESCALATION"
    assert state["requires_human_escalation"] is True
    assert state["status"] == "HUMAN_ESCALATED"
    assert state["tool_output"]["created"] is True


def test_fastapi_endpoints():
    """Prueba 5: Verifica los endpoints REST (/health, /api/v1/chat y /api/v1/metrics)."""
    with TestClient(app) as client:
        health = client.get("/health")
        assert health.status_code == 200

        chat_res = client.post(
            "/api/v1/chat",
            json={"query": "¿Dónde está mi pedido ORD-1002?"},
        )
        assert chat_res.status_code == 200
        body = chat_res.json()
        assert body["intent"] == "ORDER_STATUS"
        assert body["latency_ms"] >= 0

        metrics_res = client.get("/api/v1/metrics")
        assert metrics_res.status_code == 200
        assert metrics_res.json()["total_calls"] >= 1
