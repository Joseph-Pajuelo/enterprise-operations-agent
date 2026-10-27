"""
DASHBOARD INTERACTIVO DE OPERACIONES Y TELEMETRÍA EN TIEMPO REAL (STREAMLIT)
============================================================================
Proporciona una interfaz visual dividida en 3 pestañas:
1. Simulador en vivo del Agente LangGraph con trazabilidad Chain-of-Thought.
2. Dashboard de Monitoreo de API (gráficos de latencia, volumen e intenciones).
3. Visor en vivo de las tablas SQL (`orders`, `products`, `support_tickets`).
"""

import os
import sys
import pandas as pd
import plotly.express as px
import streamlit as st

# Asegura que el directorio raíz del proyecto esté en el path de Python
ROOT_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

from src.database.connection import init_db, get_db_context
from src.database.models import Order, Product, SupportTicket
from src.agent.graph import run_operations_agent
from src.monitoring.telemetry import get_telemetry_kpis

# Configuración general de la página de Streamlit
st.set_page_config(
    page_title="Enterprise AI Operations & Telemetry Dashboard",
    page_icon="🤖",
    layout="wide",
)

# Inicializa las tablas y datos semilla si aún no existen
init_db()

st.title("🤖 Enterprise Operations AI Agent & Real-Time Telemetry")
st.caption(
    "Arquitectura Modular con **Python + LangGraph + Google Gemini 3.8 Flash + SQLAlchemy (SQLite/PostgreSQL)** | Desarrollado por **Joseph Pajuelo**"
)

# Consulta en tiempo real los indicadores clave desde la tabla `agent_telemetry`
kpis = get_telemetry_kpis()

# =====================================================================
# BLOQUE 1: Tarjetas Superiores de Indicadores Clave (KPIs)
# =====================================================================
col1, col2, col3, col4, col5 = st.columns(5)
col1.metric("📞 Volumen Llamadas API", f"{kpis['total_calls']}")
col2.metric("⚡ Latencia Promedio", f"{kpis['avg_latency_ms']} ms")
col3.metric("⚠️ Tasa de Error", f"{kpis['error_rate_pct']}%")
col4.metric("🛡️ Escalamiento Humano", f"{kpis['escalation_rate_pct']}%")
col5.metric("🔢 Tokens Procesados", f"{kpis['total_tokens']:,}")

st.divider()

# =====================================================================
# BLOQUE 2: Pestañas de Navegación del Sistema
# =====================================================================
tab_agent, tab_metrics, tab_db = st.tabs(
    [
        "💬 Agente Autónomo (LangGraph Playground)",
        "📊 Dashboard de Telemetría en Tiempo Real",
        "🗄️ Estado de Base de Datos (Pedidos, Stock y Tickets)",
    ]
)

# PESTAÑA 1: Simulador interactivo del Agente y Trazabilidad del Grafo
with tab_agent:
    left_col, right_col = st.columns([1.25, 1])

    with left_col:
        st.subheader("Simulador de Operaciones Postventa & Logística")
        st.markdown(
            "Prueba casos de uso reales o selecciona una consulta rápida para observar cómo **LangGraph** enruta y ejecuta herramientas sobre la base de datos:"
        )

        preset = st.selectbox(
            "Consultas de prueba rápida:",
            [
                "Escribir mi propia consulta...",
                "Hola, ¿cuál es el estado de mi pedido ORD-1001?",
                "¿Tienen stock disponible de laptops y monitores 4K?",
                "Quiero cambiar la dirección de entrega de mi orden ORD-1004 a Av. Javier Prado Este 990, San Isidro",
                "Quiero cambiar la dirección de mi pedido ORD-1002 a Calle Los Pinos 310, Miraflores",
                "Mi pedido ORD-1003 llegó con la pantalla rota, necesito devolución por garantía urgente",
            ],
        )

        default_text = "" if preset == "Escribir mi propia consulta..." else preset
        user_input = st.text_area(
            "Mensaje del cliente:",
            value=default_text,
            height=95,
            placeholder="Ej: ¿Dónde está mi pedido ORD-1002?",
        )

        if st.button(
            "🚀 Ejecutar Agente LangGraph", type="primary", use_container_width=True
        ):
            if user_input.strip():
                with st.spinner("Ejecutando grafo de estados y herramientas SQL..."):
                    state = run_operations_agent(user_input.strip())
                    st.session_state["last_agent_state"] = state
                    st.rerun()

        if "last_agent_state" in st.session_state:
            st.markdown("#### Respuesta del Agente:")
            st.info(st.session_state["last_agent_state"]["final_response"])

    with right_col:
        st.subheader("🔍 Trazabilidad Chain-of-Thought & Estado del Grafo")
        if "last_agent_state" in st.session_state:
            s = st.session_state["last_agent_state"]
            m1, m2, m3 = st.columns(3)
            m1.markdown(f"**Intención:** `{s['intent']}`")
            m2.markdown(f"**Tool:** `{s.get('tool_name') or 'Ninguna'}`")
            m3.markdown(f"**Latencia:** `{s['latency_ms']} ms`")

            st.markdown("**Pasos de Razonamiento (Chain-of-Thought):**")
            for step_str in s.get("reasoning_steps", []):
                st.code(step_str, language="text", wrap_lines=True)

            if s.get("tool_output"):
                st.markdown("**Payload JSON devuelto por la Base de Datos:**")
                st.json(s["tool_output"])
        else:
            st.caption(
                "Ejecuta una consulta a la izquierda para inspeccionar el estado del grafo en vivo."
            )

# PESTAÑA 2: Gráficos de Monitoreo en Tiempo Real
with tab_metrics:
    st.subheader("Monitoreo de Rendimiento, Latencia y Distribución de Intenciones")
    logs = kpis.get("recent_logs", [])
    if logs:
        df_logs = pd.DataFrame(logs)
        c_chart1, c_chart2 = st.columns(2)

        with c_chart1:
            fig_lat = px.bar(
                df_logs.iloc[::-1],
                x="id",
                y="latency_ms",
                color="intent",
                title="Latencia por Llamada al Agente (ms)",
                labels={
                    "id": "ID Ejecución",
                    "latency_ms": "Latencia (ms)",
                    "intent": "Intención",
                },
            )
            st.plotly_chart(fig_lat, use_container_width=True)

        with c_chart2:
            intent_counts = pd.DataFrame(
                list(kpis["by_intent"].items()), columns=["Intención", "Volumen"]
            )
            fig_pie = px.pie(
                intent_counts,
                names="Intención",
                values="Volumen",
                hole=0.45,
                title="Distribución de Llamadas por Intención Operativa",
            )
            st.plotly_chart(fig_pie, use_container_width=True)

        st.markdown("#### Registro de Telemetría en Tiempo Real (`agent_telemetry`)")
        st.dataframe(
            df_logs[
                [
                    "id",
                    "timestamp",
                    "session_id",
                    "intent",
                    "tool_called",
                    "latency_ms",
                    "tokens_used",
                    "status",
                    "user_query",
                ]
            ],
            use_container_width=True,
            hide_index=True,
        )

# PESTAÑA 3: Visor de Tablas Relacionales SQL
with tab_db:
    with get_db_context() as db:
        orders_data = [
            {
                "Código": o.order_code,
                "SKU": o.product_sku,
                "Cant.": o.quantity,
                "Total (S/)": o.total_amount,
                "Estado": o.status,
                "Dirección de Entrega": o.shipping_address,
                "Courier": o.carrier,
                "Tracking": o.tracking_number,
            }
            for o in db.query(Order).all()
        ]
        products_data = [
            {
                "SKU": p.sku,
                "Producto": p.name,
                "Categoría": p.category,
                "Precio (S/)": p.price,
                "Stock": p.stock,
                "Ubicación Almacén": p.warehouse_location,
            }
            for p in db.query(Product).all()
        ]
        tickets_data = [
            {
                "Ticket": t.ticket_code,
                "Orden": t.order_code,
                "Email Cliente": t.customer_email,
                "Tipo": t.issue_type,
                "Prioridad": t.priority,
                "Estado": t.status,
                "Descripción": t.description,
            }
            for t in db.query(SupportTicket)
            .order_by(SupportTicket.created_at.desc())
            .all()
        ]

    st.markdown("#### 📦 Tabla de Pedidos (`orders`)")
    st.dataframe(pd.DataFrame(orders_data), use_container_width=True, hide_index=True)

    st.markdown("#### 🏭 Tabla de Inventario (`products`)")
    st.dataframe(pd.DataFrame(products_data), use_container_width=True, hide_index=True)

    st.markdown("#### 🛡️ Tickets Escalados a Supervisores (`support_tickets`)")
    st.dataframe(pd.DataFrame(tickets_data), use_container_width=True, hide_index=True)
