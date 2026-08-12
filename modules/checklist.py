"""
Checklist pre-desembolso (gate operativo).

Todo ítem debe estar marcado OK antes de desembolsar.
La firma digital/Signatura se trata aparte (estado listo_desembolso).
"""

from __future__ import annotations

import json
from typing import Any

from modules.database import get_operacion, update_operacion
from modules.traceability import _utc_now, log_event

# id → etiqueta visible
CHECKLIST_ITEMS: list[tuple[str, str]] = [
    ("cuit_activo", "CUIT del comercio verificado (activo / vigente)"),
    ("cbu_titular", "CBU/CVU de destino concuerda con el titular / razón social"),
    ("lote_u_origen", "Cupón/lote o flujo de ventas validado en origen (no solo PDF)"),
    ("contrato_versionado", "Contrato/pagaré generado con plantilla vigente"),
    ("garantias_ok", "Garantías cargadas (pagaré / eCheq / fiador según perfil)"),
    ("capacidad_pago", "Retención o comisión deja margen viable (no alerta bloqueante)"),
    ("sin_alerta_fraude", "Sin alerta abierta de desvío a efectivo / fraude"),
]


def _parse_payload(op: dict[str, Any]) -> dict[str, Any]:
    raw = op.get("payload_json") or "{}"
    if isinstance(raw, dict):
        return dict(raw)
    try:
        return json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        return {}


def get_checklist(operacion_id: int) -> dict[str, Any]:
    op = get_operacion(operacion_id)
    if not op:
        raise ValueError("Operación no encontrada.")
    payload = _parse_payload(op)
    saved = payload.get("checklist") or {}
    items = []
    for key, label in CHECKLIST_ITEMS:
        items.append(
            {
                "id": key,
                "label": label,
                "ok": bool(saved.get(key, False)),
            }
        )
    all_ok = all(i["ok"] for i in items)
    return {
        "operacion_id": operacion_id,
        "items": items,
        "all_ok": all_ok,
        "firma_lista": op.get("estado") == "listo_desembolso",
        "puede_desembolsar": all_ok and op.get("estado") == "listo_desembolso",
    }


def save_checklist(operacion_id: int, checks: dict[str, bool]) -> dict[str, Any]:
    op = get_operacion(operacion_id)
    if not op:
        raise ValueError("Operación no encontrada.")
    payload = _parse_payload(op)
    cleaned = {k: bool(checks.get(k, False)) for k, _ in CHECKLIST_ITEMS}
    payload["checklist"] = cleaned
    payload["checklist_updated_at"] = _utc_now()
    update_operacion(
        operacion_id,
        {
            "payload_json": json.dumps(payload, ensure_ascii=False, default=str),
            "actualizado_en": _utc_now(),
        },
    )
    log_event(operacion_id, "checklist_saved", {"checks": cleaned})
    return get_checklist(operacion_id)
