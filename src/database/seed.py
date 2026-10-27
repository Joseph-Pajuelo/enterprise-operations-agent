"""
MÓDULO DE DATOS SEMILLA (SEEDING)
=================================
Carga datos realistas de E-Commerce y Logística en Perú la primera vez que se inicia el sistema.
Incluye pedidos en distintos estados (PENDING, PROCESSING, IN_TRANSIT, DELIVERED)
para poder probar todas las reglas de negocio del agente.
"""

from datetime import datetime, timedelta, timezone
from sqlalchemy.orm import Session
from src.database.models import Customer, Product, Order, SupportTicket, AgentTelemetry


def seed_initial_data(db: Session) -> None:
    """Puebla las tablas solo si la base de datos está vacía."""
    # Si ya existen clientes registrados, no vuelve a duplicar los datos
    if db.query(Customer).first() is not None:
        return

    now = datetime.now(timezone.utc)

    # 1. Crear clientes de prueba (niveles VIP, Standard y Corporativo)
    customers = [
        Customer(
            name="Carlos Mendoza",
            email="carlos.mendoza@empresa.pe",
            phone="+51 987654321",
            tier="VIP",
        ),
        Customer(
            name="Lucía Fernández",
            email="lucia.fernandez@gmail.com",
            phone="+51 912345678",
            tier="Standard",
        ),
        Customer(
            name="Roberto Vargas",
            email="rvargas@corporacionlima.pe",
            phone="+51 998877665",
            tier="Corporativo",
        ),
        Customer(
            name="Andrea Quispe",
            email="andrea.quispe@outlook.com",
            phone="+51 955443322",
            tier="VIP",
        ),
    ]
    db.add_all(customers)
    db.flush()

    # 2. Crear catálogo de productos con distintos niveles de stock y almacenes en Lima
    products = [
        Product(
            sku="LAP-PRO-16",
            name="Laptop Workstation Pro 16GB RAM NVMe",
            category="Computación",
            price=4250.00,
            stock=14,
            warehouse_location="Almacén Ate - Zona A1",
        ),
        Product(
            sku="MON-4K-27",
            name="Monitor UltraHD 4K 27 Pulgadas IPS",
            category="Periféricos",
            price=1350.00,
            stock=28,
            warehouse_location="Almacén Ate - Zona B2",
        ),
        Product(
            sku="TEC-MEC-RGB",
            name="Teclado Mecánico Inalámbrico Switch Red",
            category="Periféricos",
            price=320.00,
            stock=5,
            warehouse_location="Almacén Surco - Hub Express",
        ),
        Product(
            sku="SIL-ERG-PRO",
            name="Silla Ergonómica Ejecutiva Soporte Lumbar",
            category="Mobiliario",
            price=890.00,
            stock=0,  # Producto agotado para probar alertas de falta de stock
            warehouse_location="Almacén Ate - Zona C4",
        ),
        Product(
            sku="AUD-ANC-BT",
            name="Audífonos Cancelación de Ruido Activa Pro",
            category="Audio",
            price=580.00,
            stock=42,
            warehouse_location="Almacén Miraflores - Locker",
        ),
    ]
    db.add_all(products)
    db.flush()

    # 3. Crear órdenes en estados variados para validar las reglas logísticas del agente
    orders = [
        Order(
            order_code="ORD-1001",
            customer_id=customers[0].id,
            product_sku="LAP-PRO-16",
            quantity=1,
            total_amount=4250.00,
            status="PROCESSING",  # En almacén: SÍ permite cambio de dirección
            shipping_address="Av. Javier Prado Este 2450, San Borja, Lima",
            tracking_number="TRK-PE-88210",
            carrier="DHL Express",
            created_at=now - timedelta(hours=18),
        ),
        Order(
            order_code="ORD-1002",
            customer_id=customers[1].id,
            product_sku="MON-4K-27",
            quantity=2,
            total_amount=2700.00,
            status="IN_TRANSIT",  # En ruta: NO permite cambio automático de dirección
            shipping_address="Calle Las Begonias 415, San Isidro, Lima",
            tracking_number="TRK-PE-88245",
            carrier="Olva Courier",
            created_at=now - timedelta(days=2),
        ),
        Order(
            order_code="ORD-1003",
            customer_id=customers[2].id,
            product_sku="TEC-MEC-RGB",
            quantity=3,
            total_amount=960.00,
            status="DELIVERED",  # Entregado: Ideal para pruebas de garantía / devolución
            shipping_address="Av. La Molina 1120, La Molina, Lima",
            tracking_number="TRK-PE-87901",
            carrier="Schaffen Logística",
            created_at=now - timedelta(days=5),
        ),
        Order(
            order_code="ORD-1004",
            customer_id=customers[3].id,
            product_sku="AUD-ANC-BT",
            quantity=1,
            total_amount=580.00,
            status="PENDING",  # Recién creado: SÍ permite cambio de dirección
            shipping_address="Jr. de la Unión 850, Cercado de Lima",
            tracking_number=None,
            carrier="Olva Courier",
            created_at=now - timedelta(hours=4),
        ),
    ]
    db.add_all(orders)

    # 4. Crear un ticket inicial de soporte como ejemplo de escalamiento humano
    tickets = [
        SupportTicket(
            ticket_code="TCK-5001",
            order_code="ORD-1003",
            customer_email="rvargas@corporacionlima.pe",
            issue_type="DAMAGED_ITEM",
            description="Uno de los 3 teclados llegó con la caja golpeada, solicita cambio por garantía.",
            priority="HIGH",
            status="OPEN",
            created_at=now - timedelta(hours=12),
        )
    ]
    db.add_all(tickets)

    # 5. Cargar registros históricos de telemetría para que el dashboard luzca lleno desde el arranque
    sample_telemetry = [
        AgentTelemetry(
            session_id="sess-demo-01",
            timestamp=now - timedelta(hours=6),
            user_query="Hola, ¿cuál es el estado de mi pedido ORD-1001?",
            intent="ORDER_STATUS",
            tool_called="get_order_details",
            model_name="gemini-3.8-flash",
            latency_ms=342.5,
            tokens_used=285,
            status="SUCCESS",
            reasoning_trace="1. Detectado código ORD-1001 -> 2. Ejecutar tool get_order_details -> 3. Pedido en estado PROCESSING en San Borja.",
        ),
        AgentTelemetry(
            session_id="sess-demo-02",
            timestamp=now - timedelta(hours=5, minutes=20),
            user_query="Quiero cambiar la dirección de entrega de mi orden ORD-1004 a Av. Arequipa 1250, Lince",
            intent="UPDATE_ADDRESS",
            tool_called="update_shipping_address",
            model_name="gemini-3.8-flash",
            latency_ms=418.2,
            tokens_used=340,
            status="SUCCESS",
            reasoning_trace="1. Intención cambio de dirección -> 2. Validar que ORD-1004 está en PENDING -> 3. Actualizar dirección con éxito.",
        ),
        AgentTelemetry(
            session_id="sess-demo-03",
            timestamp=now - timedelta(hours=4, minutes=10),
            user_query="¿Tienen stock disponible del monitor 4K y de la silla ergonómica?",
            intent="INVENTORY_CHECK",
            tool_called="check_product_inventory",
            model_name="gemini-3.8-flash",
            latency_ms=295.8,
            tokens_used=260,
            status="SUCCESS",
            reasoning_trace="1. Consulta de catálogo -> 2. Verificar SKU MON-4K-27 (28 uds) y SIL-ERG-PRO (0 uds).",
        ),
        AgentTelemetry(
            session_id="sess-demo-04",
            timestamp=now - timedelta(hours=3),
            user_query="Mi pedido ORD-1003 llegó con defecto en una tecla, quiero gestionar devolución urgente",
            intent="RETURN_OR_ESCALATION",
            tool_called="create_return_or_support_ticket",
            model_name="gemini-3.8-flash",
            latency_ms=465.0,
            tokens_used=410,
            status="HUMAN_ESCALATED",
            reasoning_trace="1. Reclamo de garantía en orden entregada ORD-1003 -> 2. Generar ticket prioritario y escalar a especialista.",
        ),
        AgentTelemetry(
            session_id="sess-demo-05",
            timestamp=now - timedelta(hours=2),
            user_query="Quiero cambiar la dirección de ORD-1002 que ya está en camino",
            intent="UPDATE_ADDRESS",
            tool_called="update_shipping_address",
            model_name="gemini-3.8-flash",
            latency_ms=380.4,
            tokens_used=315,
            status="SUCCESS",
            reasoning_trace="1. Validar estado de ORD-1002 -> 2. Estado es IN_TRANSIT -> 3. Bloquear cambio automático por regla de negocio e informar al cliente.",
        ),
        AgentTelemetry(
            session_id="sess-demo-06",
            timestamp=now - timedelta(hours=1),
            user_query="Necesito hablar con un supervisor por un cobro duplicado en mi tarjeta corporativa",
            intent="RETURN_OR_ESCALATION",
            tool_called="create_return_or_support_ticket",
            model_name="gemini-3.8-flash",
            latency_ms=390.1,
            tokens_used=330,
            status="HUMAN_ESCALATED",
            reasoning_trace="1. Incidencia financiera crítica -> 2. Escalamiento humano inmediato con ticket de prioridad CRITICAL.",
        ),
    ]
    db.add_all(sample_telemetry)
    db.commit()
