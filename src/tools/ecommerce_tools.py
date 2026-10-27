"""
MÓDULO DE HERRAMIENTAS OPERATIVAS (CAPA DE TOOLS / FUNCTION CALLING)
====================================================================
Aquí se definen las funciones en Python ("las manos del agente") que interactúan
con la base de datos SQL y aplican las reglas de negocio de la empresa.
También incluye `GEMINI_TOOLS_DECLARATIONS`, que le explica a Gemini qué herramientas existen.
"""

import random
from typing import Dict, Any, List
from src.database.connection import get_db_context
from src.database.models import Order, Product, Customer, SupportTicket


# =====================================================================
# HERRAMIENTA 1: Consultar estado y tracking de un pedido
# =====================================================================
def get_order_details(order_code: str) -> Dict[str, Any]:
    """Busca un pedido por su código (ej. ORD-1001) y cruza los datos del cliente y producto."""
    clean_code = order_code.strip().upper()
    with get_db_context() as db:
        order = db.query(Order).filter(Order.order_code == clean_code).first()
        if not order:
            return {
                "found": False,
                "order_code": clean_code,
                "message": f"No se encontró ningún pedido con el código {clean_code}.",
            }

        # Cruza con las tablas Customer y Product para entregar información completa
        customer = db.query(Customer).filter(Customer.id == order.customer_id).first()
        product = db.query(Product).filter(Product.sku == order.product_sku).first()
        return {
            "found": True,
            "order_code": order.order_code,
            "customer_name": customer.name if customer else "Cliente",
            "customer_email": customer.email if customer else "",
            "customer_tier": customer.tier if customer else "Standard",
            "product_name": product.name if product else order.product_sku,
            "product_sku": order.product_sku,
            "quantity": order.quantity,
            "total_amount_pen": order.total_amount,
            "status": order.status,
            "shipping_address": order.shipping_address,
            "carrier": order.carrier,
            "tracking_number": order.tracking_number or "Pendiente de asignación",
        }


# =====================================================================
# HERRAMIENTA 2: Consultar stock y precios en el catálogo de inventario
# =====================================================================
def check_product_inventory(search_query: str = "") -> Dict[str, Any]:
    """Filtra productos por nombre, categoría o código SKU y devuelve su stock actual."""
    query_str = search_query.strip().lower()
    with get_db_context() as db:
        products = db.query(Product).all()
        matched: List[Dict[str, Any]] = []
        for p in products:
            if (
                not query_str
                or query_str in p.sku.lower()
                or query_str in p.name.lower()
                or query_str in p.category.lower()
            ):
                matched.append(
                    {
                        "sku": p.sku,
                        "name": p.name,
                        "category": p.category,
                        "price_pen": p.price,
                        "stock": p.stock,
                        "available": p.stock > 0,
                        "warehouse": p.warehouse_location,
                    }
                )
        # Si el término buscado no coincidió exactamente, devuelve el resumen completo del catálogo
        if not matched:
            matched = [
                {
                    "sku": p.sku,
                    "name": p.name,
                    "category": p.category,
                    "price_pen": p.price,
                    "stock": p.stock,
                    "available": p.stock > 0,
                    "warehouse": p.warehouse_location,
                }
                for p in products
            ]
        return {"count": len(matched), "products": matched}


# =====================================================================
# HERRAMIENTA 3: Actualizar dirección de envío (con Regla de Negocio Logística)
# =====================================================================
def update_shipping_address(order_code: str, new_address: str) -> Dict[str, Any]:
    """
    Cambia la dirección de entrega de una orden SOLO si aún está en almacén.
    Regla de negocio:
    - Estados permitidos: PENDING, PROCESSING.
    - Estados bloqueados: IN_TRANSIT, DELIVERED, RETURN_REQUESTED, CANCELLED.
    """
    clean_code = order_code.strip().upper()
    with get_db_context() as db:
        order = db.query(Order).filter(Order.order_code == clean_code).first()
        if not order:
            return {
                "updated": False,
                "order_code": clean_code,
                "reason": f"El pedido {clean_code} no existe en el sistema.",
            }

        # Validación de la regla de negocio logística antes de hacer UPDATE en SQL
        allowed_statuses = {"PENDING", "PROCESSING"}
        if order.status not in allowed_statuses:
            return {
                "updated": False,
                "order_code": clean_code,
                "current_status": order.status,
                "carrier": order.carrier,
                "tracking_number": order.tracking_number,
                "reason": (
                    f"Política de Logística: No se puede modificar la dirección automáticamente "
                    f"porque el pedido {clean_code} ya se encuentra en estado '{order.status}' "
                    f"con el transportista {order.carrier}."
                ),
            }

        # Si cumple la regla, actualiza el registro y guarda el cambio en la base de datos
        old_address = order.shipping_address
        order.shipping_address = new_address.strip()
        db.commit()
        return {
            "updated": True,
            "order_code": clean_code,
            "previous_address": old_address,
            "new_address": order.shipping_address,
            "status": order.status,
            "message": f"Dirección actualizada exitosamente para el pedido {clean_code}.",
        }


# =====================================================================
# HERRAMIENTA 4: Crear Ticket de Soporte / Devolución (Human-in-the-Loop)
# =====================================================================
def create_return_or_support_ticket(
    order_code: str, customer_email: str, issue_type: str, description: str
) -> Dict[str, Any]:
    """
    Registra un ticket prioritario en la tabla `support_tickets` cuando el cliente
    reporta un producto dañado, solicita garantía o pide hablar con un supervisor.
    """
    clean_code = order_code.strip().upper() if order_code else "SIN-ORDEN"
    ticket_code = f"TCK-{random.randint(5100, 9999)}"
    with get_db_context() as db:
        order = db.query(Order).filter(Order.order_code == clean_code).first()
        resolved_email = customer_email
        if order and not resolved_email:
            cust = db.query(Customer).filter(Customer.id == order.customer_id).first()
            resolved_email = cust.email if cust else "cliente@pendiente.pe"

        # Si el reclamo es por devolución o daño físico, actualiza el estado de la orden
        if order and issue_type.upper() in {"RETURN", "DAMAGED_ITEM"}:
            order.status = "RETURN_REQUESTED"

        ticket = SupportTicket(
            ticket_code=ticket_code,
            order_code=clean_code if order else None,
            customer_email=resolved_email or "cliente@pendiente.pe",
            issue_type=issue_type.upper(),
            description=description,
            priority="HIGH",
            status="OPEN",
        )
        db.add(ticket)
        db.commit()
        return {
            "created": True,
            "ticket_code": ticket_code,
            "order_code": clean_code,
            "issue_type": issue_type.upper(),
            "priority": "HIGH",
            "status": "OPEN",
            "message": (
                f"Ticket {ticket_code} generado y asignado a un especialista humano "
                f"con prioridad ALTA."
            ),
        }


# Diccionario que mapea el nombre de cada herramienta con su función real en Python
TOOL_REGISTRY = {
    "get_order_details": get_order_details,
    "check_product_inventory": check_product_inventory,
    "update_shipping_address": update_shipping_address,
    "create_return_or_support_ticket": create_return_or_support_ticket,
}

# Esquemas JSON (OpenAPI) que le indican al modelo Gemini 3.8 Flash qué argumentos recibe cada función
GEMINI_TOOLS_DECLARATIONS = [
    {
        "type": "function",
        "name": "get_order_details",
        "description": "Consulta el estado actual, transportista, número de seguimiento y detalles de un pedido usando su código (ej. ORD-1001).",
        "parameters": {
            "type": "object",
            "properties": {
                "order_code": {
                    "type": "string",
                    "description": "Código único del pedido, por ejemplo ORD-1001, ORD-1002.",
                }
            },
            "required": ["order_code"],
        },
    },
    {
        "type": "function",
        "name": "check_product_inventory",
        "description": "Consulta el stock disponible, precio en soles (PEN), SKU y almacén de productos en el catálogo.",
        "parameters": {
            "type": "object",
            "properties": {
                "search_query": {
                    "type": "string",
                    "description": "Nombre, categoría o SKU del producto a buscar (ej. 'laptop', 'monitor', 'silla', 'LAP-PRO-16'). Vacío para listar todo el catálogo.",
                }
            },
            "required": ["search_query"],
        },
    },
    {
        "type": "function",
        "name": "update_shipping_address",
        "description": "Actualiza la dirección de envío de un pedido siempre que su estado sea PENDING o PROCESSING.",
        "parameters": {
            "type": "object",
            "properties": {
                "order_code": {
                    "type": "string",
                    "description": "Código del pedido a modificar (ej. ORD-1001).",
                },
                "new_address": {
                    "type": "string",
                    "description": "Nueva dirección completa de entrega indicada por el cliente.",
                },
            },
            "required": ["order_code", "new_address"],
        },
    },
    {
        "type": "function",
        "name": "create_return_or_support_ticket",
        "description": "Crea un ticket de soporte prioritario, devolución por garantía o escalamiento a un supervisor humano.",
        "parameters": {
            "type": "object",
            "properties": {
                "order_code": {
                    "type": "string",
                    "description": "Código del pedido relacionado (ej. ORD-1003) o 'SIN-ORDEN' si no aplica.",
                },
                "customer_email": {
                    "type": "string",
                    "description": "Correo electrónico del cliente si lo proporcionó, o cadena vacía.",
                },
                "issue_type": {
                    "type": "string",
                    "enum": ["RETURN", "DAMAGED_ITEM", "BILLING", "ESCALATION"],
                    "description": "Tipo de incidencia reportada.",
                },
                "description": {
                    "type": "string",
                    "description": "Resumen detallado del problema reportado por el usuario.",
                },
            },
            "required": ["order_code", "issue_type", "description"],
        },
    },
]
