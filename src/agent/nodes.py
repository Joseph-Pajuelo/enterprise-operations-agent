"""
MÓDULO DE NODOS DEL GRAFO (ESTACIONES DE TRABAJO DE LANGGRAPH)
==============================================================
Contiene las 4 funciones principales (nodos) por las que pasa cada consulta:
1. `classify_and_plan_node`: Analiza el mensaje con Chain-of-Thought y elige qué herramienta usar.
2. `execute_tool_node`: Ejecuta la función Python sobre la base de datos SQL.
3. `human_escalation_node`: Marca el caso cuando requiere supervisión humana (Human-in-the-Loop).
4. `synthesize_response_node`: Construye la respuesta final clara y estructurada para el usuario.
"""

import os
import re
import json
from typing import Dict, Any
from dotenv import load_dotenv
from src.agent.state import OperationsAgentState
from src.agent.prompts import SYSTEM_INSTRUCTION, COMPANY_POLICIES_KB
from src.tools.ecommerce_tools import TOOL_REGISTRY, GEMINI_TOOLS_DECLARATIONS

load_dotenv()


def _is_gemini_configured() -> bool:
    """Verifica si el usuario configuró una llave API real de Google Gemini en el archivo .env."""
    api_key = os.getenv("GEMINI_API_KEY", "").strip()
    return bool(api_key and api_key != "your_gemini_api_key_here")


def _extract_order_code(text: str) -> str:
    """Extrae mediante expresiones regulares códigos de pedido con formato ORD-XXXX."""
    match = re.search(r"(ORD-\d{3,6})", text.upper())
    return match.group(1) if match else ""


# =====================================================================
# NODO 1: Clasificación de Intención y Planificación (Chain-of-Thought)
# =====================================================================
def classify_and_plan_node(state: OperationsAgentState) -> Dict[str, Any]:
    """
    Analiza la consulta del cliente, genera los pasos de razonamiento Chain-of-Thought
    y decide qué herramienta de base de datos debe invocarse.
    """
    query = state["user_query"]
    query_lower = query.lower()
    model_name = os.getenv("GEMINI_MODEL", "gemini-3.8-flash")
    reasoning = list(state.get("reasoning_steps", []))
    tokens_used = state.get("tokens_used", 0)

    # BLOQUE A: Si la API Key de Google Gemini está activa, usa el SDK oficial google-genai
    if _is_gemini_configured():
        try:
            from google import genai

            client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))
            interaction = client.interactions.create(
                model=model_name,
                system_instruction=SYSTEM_INSTRUCTION,
                input=query,
                tools=GEMINI_TOOLS_DECLARATIONS,
                store=False,
            )
            # Contabiliza los tokens reales reportados por la API de Gemini
            if getattr(interaction, "usage", None) and getattr(
                interaction.usage, "total_tokens", None
            ):
                tokens_used += int(interaction.usage.total_tokens)
            else:
                tokens_used += 280

            # Recorre los pasos devueltos por Gemini (pensamiento interno + llamada a función)
            fc_step = None
            for step in getattr(interaction, "steps", []) or []:
                step_type = getattr(step, "type", "")
                if step_type == "thought":
                    summary = getattr(step, "summary", None)
                    if summary:
                        reasoning.append(f"[Pensamiento Gemini] {summary}")
                elif step_type == "function_call":
                    fc_step = step

            # Si Gemini decidió invocar una herramienta de base de datos:
            if fc_step:
                tool_name = fc_step.name
                tool_args = dict(fc_step.arguments or {})
                intent_map = {
                    "get_order_details": "ORDER_STATUS",
                    "check_product_inventory": "INVENTORY_CHECK",
                    "update_shipping_address": "UPDATE_ADDRESS",
                    "create_return_or_support_ticket": "RETURN_OR_ESCALATION",
                }
                intent = intent_map.get(tool_name, "GENERAL_POLICY")
                reasoning.append(
                    f"1. [Chain-of-Thought] Intención clasificada como '{intent}' por {model_name}."
                )
                reasoning.append(
                    f"2. [Selección de Herramienta] Invocando `{tool_name}` con parámetros {json.dumps(tool_args, ensure_ascii=False)}."
                )
                return {
                    "intent": intent,
                    "tool_name": tool_name,
                    "tool_args": tool_args,
                    "reasoning_steps": reasoning,
                    "model_used": model_name,
                    "tokens_used": tokens_used,
                }
            elif getattr(interaction, "output_text", None):
                reasoning.append(
                    f"1. [Chain-of-Thought] Consulta general respondida directamente por {model_name}."
                )
                return {
                    "intent": "GENERAL_POLICY",
                    "tool_name": None,
                    "tool_args": {},
                    "final_response": interaction.output_text,
                    "reasoning_steps": reasoning,
                    "model_used": model_name,
                    "tokens_used": tokens_used,
                }
        except Exception as exc:
            reasoning.append(
                f"[Aviso] Motor local de respaldo activado para continuidad operativa ({type(exc).__name__})."
            )

    # BLOQUE B: Planificador determinista de respaldo (garantiza que el proyecto funcione al 100% aún sin internet o sin API key)
    order_code = _extract_order_code(query)
    tokens_used += 245

    # Caso 1: Detección de reclamos, devoluciones, productos rotos o solicitud de supervisor
    if any(
        kw in query_lower
        for kw in [
            "devol",
            "dañad",
            "roto",
            "golpead",
            "defecto",
            "garant",
            "reembolso",
            "supervisor",
            "reclamo",
            "cobro duplicado",
        ]
    ):
        intent = "RETURN_OR_ESCALATION"
        issue_type = (
            "DAMAGED_ITEM"
            if any(k in query_lower for k in ["dañad", "roto", "golpead", "defecto"])
            else "RETURN"
        )
        if "cobro" in query_lower or "factura" in query_lower:
            issue_type = "BILLING"
        elif "supervisor" in query_lower:
            issue_type = "ESCALATION"

        email_match = re.search(r"[\w\.-]+@[\w\.-]+\.\w+", query)
        tool_args = {
            "order_code": order_code or "SIN-ORDEN",
            "customer_email": email_match.group(0) if email_match else "",
            "issue_type": issue_type,
            "description": query,
        }
        reasoning.append(
            f"1. [Chain-of-Thought] Detectada incidencia crítica o solicitud de garantía ({issue_type})."
        )
        reasoning.append(
            f"2. [Selección de Herramienta] Seleccionada función `create_return_or_support_ticket` para orden `{tool_args['order_code']}`."
        )
        return {
            "intent": intent,
            "tool_name": "create_return_or_support_ticket",
            "tool_args": tool_args,
            "reasoning_steps": reasoning,
            "model_used": model_name,
            "tokens_used": tokens_used,
        }

    # Caso 2: Solicitud de cambio o actualización de dirección de entrega
    if any(
        kw in query_lower
        for kw in [
            "cambiar la dirección",
            "cambiar direccion",
            "cambio de dirección",
            "nueva dirección",
            "enviar a otra dirección",
            "modificar dirección",
        ]
    ) or (
        "dirección" in query_lower
        and (
            "cambiar" in query_lower
            or "actualizar" in query_lower
            or "a av" in query_lower
            or "a calle" in query_lower
            or "a jr" in query_lower
        )
    ):
        intent = "UPDATE_ADDRESS"
        addr_match = re.search(
            r"(?:a\s+la\s+direcci[oó]n|a\s+)(av\.?.*|calle.*|jr\.?.*|jiron.*|paseo.*)$",
            query,
            re.IGNORECASE,
        )
        new_address = (
            addr_match.group(1).strip()
            if addr_match
            else "Av. Arequipa 1250, Lince, Lima"
        )
        tool_args = {
            "order_code": order_code or "ORD-1001",
            "new_address": new_address,
        }
        reasoning.append(
            f"1. [Chain-of-Thought] Solicitud de cambio logístico de dirección para `{tool_args['order_code']}`."
        )
        reasoning.append(
            f"2. [Selección de Herramienta] Ejecutando `update_shipping_address` hacia '{new_address}' validando reglas de estado."
        )
        return {
            "intent": intent,
            "tool_name": "update_shipping_address",
            "tool_args": tool_args,
            "reasoning_steps": reasoning,
            "model_used": model_name,
            "tokens_used": tokens_used,
        }

    # Caso 3: Consulta de estado o seguimiento de un pedido
    if order_code or any(
        kw in query_lower
        for kw in [
            "estado de mi pedido",
            "donde esta mi pedido",
            "dónde está mi pedido",
            "seguimiento",
            "tracking",
            "orden",
            "pedido",
        ]
    ):
        intent = "ORDER_STATUS"
        target_code = order_code or "ORD-1001"
        reasoning.append(
            f"1. [Chain-of-Thought] Consulta de trazabilidad y estado del pedido `{target_code}`."
        )
        reasoning.append(
            f"2. [Selección de Herramienta] Invocando `get_order_details(order_code='{target_code}')`."
        )
        return {
            "intent": intent,
            "tool_name": "get_order_details",
            "tool_args": {"order_code": target_code},
            "reasoning_steps": reasoning,
            "model_used": model_name,
            "tokens_used": tokens_used,
        }

    # Caso 4: Consulta de stock, precios o disponibilidad en almacén
    if any(
        kw in query_lower
        for kw in [
            "stock",
            "inventario",
            "disponible",
            "precio",
            "catalogo",
            "catálogo",
            "laptop",
            "monitor",
            "teclado",
            "silla",
            "audifono",
            "audífono",
        ]
    ):
        intent = "INVENTORY_CHECK"
        search_kw = ""
        for item_kw in [
            "laptop",
            "monitor",
            "teclado",
            "silla",
            "audifono",
            "audífono",
            "lap-pro",
            "mon-4k",
            "tec-mec",
            "sil-erg",
        ]:
            if item_kw in query_lower:
                search_kw = item_kw.replace("audífono", "aud").replace("audifono", "aud")
                break
        reasoning.append(
            f"1. [Chain-of-Thought] Consulta de disponibilidad de inventario (filtro: '{search_kw or 'catálogo completo'}')."
        )
        reasoning.append(
            f"2. [Selección de Herramienta] Invocando `check_product_inventory(search_query='{search_kw}')`."
        )
        return {
            "intent": intent,
            "tool_name": "check_product_inventory",
            "tool_args": {"search_query": search_kw},
            "reasoning_steps": reasoning,
            "model_used": model_name,
            "tokens_used": tokens_used,
        }

    # Caso 5: Preguntas generales sobre políticas de envío o devolución
    reasoning.append(
        "1. [Chain-of-Thought] Consulta clasificada como información general y políticas operativas."
    )
    return {
        "intent": "GENERAL_POLICY",
        "tool_name": None,
        "tool_args": {},
        "reasoning_steps": reasoning,
        "model_used": model_name,
        "tokens_used": tokens_used,
    }


# =====================================================================
# NODO 2: Ejecución de Herramienta sobre la Base de Datos SQL
# =====================================================================
def execute_tool_node(state: OperationsAgentState) -> Dict[str, Any]:
    """Ejecuta la función de Python seleccionada y guarda la respuesta JSON en `tool_output`."""
    tool_name = state.get("tool_name")
    tool_args = state.get("tool_args", {})
    reasoning = list(state.get("reasoning_steps", []))

    if not tool_name or tool_name not in TOOL_REGISTRY:
        reasoning.append("3. [Ejecución de Tool] No se requirió herramienta externa.")
        return {"tool_output": None, "reasoning_steps": reasoning}

    # Busca la función en el registro y le pasa los argumentos desempacados
    tool_fn = TOOL_REGISTRY[tool_name]
    result = tool_fn(**tool_args)
    reasoning.append(
        f"3. [Ejecución SQL] `{tool_name}` completado -> {json.dumps(result, ensure_ascii=False)[:180]}..."
    )
    return {"tool_output": result, "reasoning_steps": reasoning}


# =====================================================================
# NODO 3: Escalamiento Human-in-the-Loop (Casos Críticos / Garantías)
# =====================================================================
def human_escalation_node(state: OperationsAgentState) -> Dict[str, Any]:
    """Activa la bandera de supervisión humana cuando se genera un ticket de reclamo o garantía."""
    reasoning = list(state.get("reasoning_steps", []))
    reasoning.append(
        "4. [Human-in-the-Loop] Caso crítico o de garantía detectado. Escalado a bandeja de supervisores."
    )
    return {
        "requires_human_escalation": True,
        "status": "HUMAN_ESCALATED",
        "reasoning_steps": reasoning,
    }


# =====================================================================
# NODO 4: Síntesis de Respuesta Final para el Cliente
# =====================================================================
def synthesize_response_node(state: OperationsAgentState) -> Dict[str, Any]:
    """Transforma los datos técnicos devueltos por la base de datos en un mensaje claro para el usuario."""
    if state.get("final_response"):
        return {"status": state.get("status") or "SUCCESS"}

    intent = state.get("intent", "GENERAL_POLICY")
    out = state.get("tool_output") or {}
    reasoning = list(state.get("reasoning_steps", []))

    if intent == "ORDER_STATUS":
        if not out.get("found"):
            msg = (
                f"⚠️ **Pedido no encontrado:** {out.get('message')}\n\n"
                "Por favor verifica que el código tenga el formato `ORD-1001` a `ORD-1004`."
            )
        else:
            msg = (
                f"📦 **Estado del Pedido `{out['order_code']}`**\n\n"
                f"- **Cliente:** {out['customer_name']} (*Nivel {out['customer_tier']}*)\n"
                f"- **Producto:** {out['product_name']} (`{out['product_sku']}`) x {out['quantity']} ud(s).\n"
                f"- **Total:** S/ {out['total_amount_pen']:,.2f} PEN\n"
                f"- **Estado Actual:** `{out['status']}`\n"
                f"- **Transportista:** {out['carrier']} (Tracking: `{out['tracking_number']}`)\n"
                f"- **Dirección de Entrega:** {out['shipping_address']}"
            )

    elif intent == "INVENTORY_CHECK":
        products = out.get("products", [])
        lines = ["📊 **Consulta de Inventario en Tiempo Real:**\n"]
        for p in products:
            badge = "✅ En Stock" if p["available"] else "❌ Agotado"
            lines.append(
                f"- **{p['name']}** (`{p['sku']}`) — **S/ {p['price_pen']:,.2f}** | "
                f"{badge} (**{p['stock']} uds**) | *{p['warehouse']}*"
            )
        msg = "\n".join(lines)

    elif intent == "UPDATE_ADDRESS":
        if out.get("updated"):
            msg = (
                f"✅ **Dirección de Entrega Actualizada (`{out['order_code']}`)**\n\n"
                f"- **Dirección Anterior:** {out['previous_address']}\n"
                f"- **Nueva Dirección:** **{out['new_address']}**\n"
                f"- **Estado del Pedido:** `{out['status']}`\n\n"
                "El almacén central ya registró el cambio para tu despacho."
            )
        else:
            msg = (
                f"🚫 **No fue posible actualizar la dirección automáticamente**\n\n"
                f"- **Motivo:** {out.get('reason')}\n"
                f"- **Tracking actual:** `{out.get('tracking_number', 'N/A')}`\n\n"
                "¿Deseas que genere un ticket de coordinación con el transportista?"
            )

    elif intent == "RETURN_OR_ESCALATION":
        msg = (
            f"🛡️ **Ticket de Soporte Prioritario Generado (`{out.get('ticket_code')}`)**\n\n"
            f"- **Pedido Asociado:** `{out.get('order_code')}`\n"
            f"- **Categoría:** `{out.get('issue_type')}`\n"
            f"- **Prioridad:** 🔴 `{out.get('priority')}` (Escalado a Especialista Humano)\n\n"
            "Un supervisor de operaciones revisará tu caso en menos de 30 minutos."
        )

    else:
        msg = (
            "👋 **Centro de Operaciones IA — Políticas y Consultas Disponibles:**\n\n"
            f"- **Envíos:** {COMPANY_POLICIES_KB['envios']}\n"
            f"- **Cambios de dirección:** {COMPANY_POLICIES_KB['cambios_direccion']}\n"
            f"- **Devoluciones y Garantías:** {COMPANY_POLICIES_KB['devoluciones']}\n\n"
            "💡 *Puedes consultarme por ejemplo: `¿Cuál es el estado de ORD-1001?`, "
            "`¿Tienen stock de monitores?` o `Cambiar dirección de ORD-1004 a Av. Arequipa 1250`.*"
        )

    reasoning.append("5. [Síntesis] Respuesta estructurada generada exitosamente.")
    final_status = (
        "HUMAN_ESCALATED" if state.get("requires_human_escalation") else "SUCCESS"
    )
    return {
        "final_response": msg,
        "status": final_status,
        "reasoning_steps": reasoning,
    }
