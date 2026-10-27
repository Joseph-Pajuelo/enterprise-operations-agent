"""
MÓDULO DE MODELOS DE BASE DE DATOS (CAPA DE DATOS - ORM SQLAlchemy)
===================================================================
Este archivo define la estructura de las tablas relacionales de la base de datos.
Cada clase de Python representa una tabla SQL real (tanto para SQLite como para PostgreSQL).
"""

from datetime import datetime, timezone
from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey, Text
from sqlalchemy.orm import declarative_base, relationship

# Clase base de SQLAlchemy de la cual heredan todas las tablas del sistema
Base = declarative_base()


def utc_now() -> datetime:
    """Devuelve la fecha y hora actual en formato UTC estándar para auditoría."""
    return datetime.now(timezone.utc)


# =====================================================================
# 1. TABLA DE CLIENTES (customers)
# Guarda la información maestra del comprador y su categoría (Standard, VIP, Corporativo)
# =====================================================================
class Customer(Base):
    __tablename__ = "customers"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(120), nullable=False)
    email = Column(String(120), unique=True, index=True, nullable=False)
    phone = Column(String(40), nullable=False)
    tier = Column(String(30), default="Standard")  # Nivel: Standard, VIP, Corporativo

    # Relación 1 a Muchos: Un cliente puede tener múltiples pedidos asociados
    orders = relationship("Order", back_populates="customer")


# =====================================================================
# 2. TABLA DE PRODUCTOS / INVENTARIO (products)
# Permite al agente consultar stock en tiempo real, precios en Soles y almacén
# =====================================================================
class Product(Base):
    __tablename__ = "products"

    id = Column(Integer, primary_key=True, index=True)
    sku = Column(String(50), unique=True, index=True, nullable=False)  # Código único de producto
    name = Column(String(150), nullable=False)
    category = Column(String(80), nullable=False)
    price = Column(Float, nullable=False)
    stock = Column(Integer, default=0, nullable=False)
    warehouse_location = Column(String(80), default="Almacén Central Ate - Lima")


# =====================================================================
# 3. TABLA DE PEDIDOS / ÓRDENES (orders)
# Es la tabla transaccional principal que el agente consulta y modifica
# =====================================================================
class Order(Base):
    __tablename__ = "orders"

    id = Column(Integer, primary_key=True, index=True)
    order_code = Column(String(40), unique=True, index=True, nullable=False)  # Ej: ORD-1001
    customer_id = Column(Integer, ForeignKey("customers.id"), nullable=False)
    product_sku = Column(String(50), ForeignKey("products.sku"), nullable=False)
    quantity = Column(Integer, default=1, nullable=False)
    total_amount = Column(Float, nullable=False)

    # Estado logístico del pedido:
    # PENDING o PROCESSING -> Aún en almacén (sí permite cambio de dirección)
    # IN_TRANSIT o DELIVERED -> Ya salió con el courier (bloquea cambio automático)
    status = Column(String(40), default="PROCESSING", nullable=False)

    shipping_address = Column(String(250), nullable=False)
    tracking_number = Column(String(80), nullable=True)
    carrier = Column(String(80), default="Olva Courier")
    created_at = Column(DateTime, default=utc_now)
    updated_at = Column(DateTime, default=utc_now, onupdate=utc_now)

    # Relaciones ORM para navegar fácilmente al cliente y al producto desde el pedido
    customer = relationship("Customer", back_populates="orders")
    product = relationship("Product")


# =====================================================================
# 4. TABLA DE TICKETS DE SOPORTE Y GARANTÍA (support_tickets)
# Registra los casos críticos que el agente escala a un supervisor humano
# =====================================================================
class SupportTicket(Base):
    __tablename__ = "support_tickets"

    id = Column(Integer, primary_key=True, index=True)
    ticket_code = Column(String(40), unique=True, index=True, nullable=False)  # Ej: TCK-5001
    order_code = Column(String(40), nullable=True)
    customer_email = Column(String(120), nullable=False)
    issue_type = Column(String(60), nullable=False)  # RETURN, ESCALATION, DAMAGED_ITEM, BILLING
    description = Column(Text, nullable=False)
    priority = Column(String(30), default="HIGH")  # Prioridad: LOW, MEDIUM, HIGH, CRITICAL
    status = Column(String(30), default="OPEN")  # Estado: OPEN, IN_REVIEW, RESOLVED
    created_at = Column(DateTime, default=utc_now)


# =====================================================================
# 5. TABLA DE TELEMETRÍA Y MONITOREO DEL AGENTE (agent_telemetry)
# Guarda las métricas operativas de cada llamada (latencia, tokens, errores)
# para alimentar el Dashboard de Monitoreo en Tiempo Real.
# =====================================================================
class AgentTelemetry(Base):
    __tablename__ = "agent_telemetry"

    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(String(80), index=True, nullable=False)
    timestamp = Column(DateTime, default=utc_now, index=True)
    user_query = Column(Text, nullable=False)
    intent = Column(String(60), index=True, nullable=False)
    tool_called = Column(String(80), nullable=True)
    model_name = Column(String(60), default="gemini-3.8-flash")
    latency_ms = Column(Float, nullable=False)  # Tiempo de respuesta en milisegundos
    tokens_used = Column(Integer, default=0)  # Volumen de tokens consumidos
    status = Column(String(30), index=True, nullable=False)  # SUCCESS, ERROR, HUMAN_ESCALATED
    reasoning_trace = Column(Text, nullable=True)  # Traza completa Chain-of-Thought
