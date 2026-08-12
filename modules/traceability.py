"""
Motor de trazabilidad de operaciones Finan.

Tipos:
  - factoring: adelanto / cesión de cupón
  - credito_comercio: línea o préstamo al comercio
  - bnpl: crédito al consumidor en comercio

Estados (firma Signatura + ciclo de cobro):
  borrador → pendiente_firma → firmado → listo_desembolso
  → desembolsado → cobrado | en_mora | chargeback | cancelado
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from typing import Any, Optional

from modules import signatura
from modules.database import (
    append_audit_event,
    get_operacion,
    insert_operacion,
    list_audit_events,
    list_operaciones,
    update_operacion,
)

# ---------------------------------------------------------------------------
# Catálogo
# ---------------------------------------------------------------------------

TIPOS = {
    "factoring": "Factoring (cupón / cesión)",
    "credito_comercio": "Crédito al comercio",
    "rbf": "Adelanto de Flujo (RBF)",
    "bnpl": "BNPL (consumo)",
}

ESTADOS = [
    "borrador",
    "pendiente_firma",
    "firmado",
    "listo_desembolso",
    "desembolsado",
    "cobrado",
    "en_mora",
    "chargeback",
    "cancelado",
]

TRANSICIONES: dict[str, set[str]] = {
    "borrador": {"pendiente_firma", "cancelado"},
    "pendiente_firma": {"firmado", "cancelado", "borrador"},
    "firmado": {"listo_desembolso", "cancelado"},
    "listo_desembolso": {"desembolsado", "cancelado"},
    "desembolsado": {"cobrado", "en_mora", "chargeback"},
    "en_mora": {"cobrado", "chargeback"},
    "cobrado": set(),
    "chargeback": set(),
    "cancelado": set(),
}


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def hash_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _event_hash(prev_hash: str, event_type: str, payload: dict[str, Any], ts: str) -> str:
    blob = json.dumps(payload, sort_keys=True, default=str, ensure_ascii=False)
    return _sha256_text(f"{prev_hash}|{event_type}|{blob}|{ts}")


def log_event(
    operacion_id: int,
    event_type: str,
    payload: Optional[dict[str, Any]] = None,
) -> dict[str, Any]:
    """Append-only: cada evento referencia el hash del anterior."""
    payload = payload or {}
    prev = list_audit_events(operacion_id)
    prev_hash = prev[-1]["event_hash"] if prev else "GENESIS"
    ts = _utc_now()
    event_hash = _event_hash(prev_hash, event_type, payload, ts)
    return append_audit_event(
        {
            "operacion_id": operacion_id,
            "event_type": event_type,
            "payload_json": json.dumps(payload, ensure_ascii=False, default=str),
            "prev_hash": prev_hash,
            "event_hash": event_hash,
            "created_at_utc": ts,
        }
    )


def crear_operacion(
    tipo: str,
    comercio: str,
    monto: float,
    *,
    cuit: str = "",
    email_firmante: str = "",
    telefono_firmante: str = "",
    email_fiador: str = "",
    telefono_fiador: str = "",
    cuit_fiador: str = "",
    ref_tabla: str = "",
    ref_id: Optional[int] = None,
    payload: Optional[dict[str, Any]] = None,
) -> int:
    if tipo not in TIPOS:
        raise ValueError(f"Tipo inválido: {tipo}")
    if not comercio.strip():
        raise ValueError("Comercio obligatorio.")
    if monto <= 0:
        raise ValueError("Monto debe ser > 0.")

    now = _utc_now()
    op_id = insert_operacion(
        {
            "tipo": tipo,
            "ref_tabla": ref_tabla,
            "ref_id": ref_id,
            "comercio": comercio.strip(),
            "cuit": cuit.strip(),
            "email_firmante": email_firmante.strip(),
            "telefono_firmante": telefono_firmante.strip(),
            "email_fiador": email_fiador.strip(),
            "telefono_fiador": telefono_fiador.strip(),
            "cuit_fiador": cuit_fiador.strip(),
            "monto": round(monto, 2),
            "estado": "borrador",
            "payload_json": json.dumps(payload or {}, ensure_ascii=False, default=str),
            "creado_en": now,
            "actualizado_en": now,
        }
    )
    log_event(
        op_id,
        "op_created",
        {"tipo": tipo, "comercio": comercio.strip(), "monto": round(monto, 2)},
    )
    return op_id


def transicionar(operacion_id: int, nuevo_estado: str, nota: str = "") -> dict[str, Any]:
    op = get_operacion(operacion_id)
    if not op:
        raise ValueError("Operación no encontrada.")
    actual = op["estado"]
    permitidos = TRANSICIONES.get(actual, set())
    if nuevo_estado not in permitidos:
        raise ValueError(f"No se puede pasar de '{actual}' a '{nuevo_estado}'.")

    update_operacion(
        operacion_id,
        {"estado": nuevo_estado, "actualizado_en": _utc_now()},
    )
    log_event(
        operacion_id,
        "state_change",
        {"from": actual, "to": nuevo_estado, "nota": nota},
    )
    return get_operacion(operacion_id) or {}


def registrar_pdf(operacion_id: int, pdf_bytes: bytes, nombre: str = "contrato.pdf") -> str:
    digest = hash_bytes(pdf_bytes)
    update_operacion(
        operacion_id,
        {
            "doc_hash_sha256": digest,
            "actualizado_en": _utc_now(),
        },
    )
    log_event(
        operacion_id,
        "pdf_generated",
        {"nombre": nombre, "sha256": digest, "bytes": len(pdf_bytes)},
    )
    return digest


def enviar_a_firmar(
    operacion_id: int,
    pdf_bytes: bytes,
    *,
    title: Optional[str] = None,
    use_afip_comercio: bool = False,
    use_afip_fiador: bool = False,
    biometric: bool = False,
) -> dict[str, Any]:
    """Sube el PDF a Signatura y pasa a pendiente_firma."""
    op = get_operacion(operacion_id)
    if not op:
        raise ValueError("Operación no encontrada.")
    if op["estado"] not in ("borrador", "pendiente_firma"):
        raise ValueError(f"Estado '{op['estado']}' no admite envío a firma.")

    digest = registrar_pdf(operacion_id, pdf_bytes)

    signatures: list[dict[str, Any]] = []
    # Firmante principal (comercio)
    signatures.append(
        signatura.build_signer(
            email=op.get("email_firmante") or None,
            phone=op.get("telefono_firmante") or None,
            cuit_afip=(op.get("cuit") if use_afip_comercio else None),
            invite_email=bool(op.get("email_firmante")),
            invite_sms=bool(op.get("telefono_firmante")) and not op.get("email_firmante"),
            biometric=biometric,
        )
    )
    # Fiador (opcional)
    if op.get("email_fiador") or op.get("telefono_fiador") or (use_afip_fiador and op.get("cuit_fiador")):
        signatures.append(
            signatura.build_signer(
                email=op.get("email_fiador") or None,
                phone=op.get("telefono_fiador") or None,
                cuit_afip=(op.get("cuit_fiador") if use_afip_fiador else None),
                invite_email=bool(op.get("email_fiador")),
                invite_sms=bool(op.get("telefono_fiador")) and not op.get("email_fiador"),
                biometric=biometric,
            )
        )

    doc_title = title or f"Finan {op['tipo']} #{operacion_id} · {op['comercio']}"
    resp = signatura.create_document(doc_title, pdf_bytes, signatures)
    doc_id = signatura.extract_document_id(resp)

    update_operacion(
        operacion_id,
        {
            "estado": "pendiente_firma",
            "doc_hash_sha256": digest,
            "signatura_doc_id": doc_id,
            "signatura_status": "pending",
            "actualizado_en": _utc_now(),
        },
    )
    log_event(
        operacion_id,
        "sent_to_signatura",
        {"signatura_doc_id": doc_id, "sha256": digest, "firmantes": len(signatures)},
    )
    return {"operacion_id": operacion_id, "signatura_doc_id": doc_id, "response": resp}


def sincronizar_firma(operacion_id: int) -> dict[str, Any]:
    """Consulta Signatura y, si está completo, marca firmado + listo_desembolso."""
    op = get_operacion(operacion_id)
    if not op:
        raise ValueError("Operación no encontrada.")
    doc_id = op.get("signatura_doc_id")
    if not doc_id:
        raise ValueError("La operación no tiene document_id de Signatura.")

    remote = signatura.get_document(doc_id)
    status = str(
        remote.get("status")
        or remote.get("document_status")
        or remote.get("state")
        or ""
    ).upper()

    update_operacion(
        operacion_id,
        {
            "signatura_status": status or json.dumps(remote, default=str)[:200],
            "actualizado_en": _utc_now(),
        },
    )
    log_event(operacion_id, "signatura_sync", {"status": status, "raw_keys": list(remote.keys())})

    # Signatura usa "CO" = completed en webhooks; la API puede devolver variantes.
    completed = status in {"CO", "COMPLETED", "COMPLETE", "SIGNED", "DONE"}
    if not completed:
        # Heurística: si todas las firmas están done
        sigs = remote.get("signatures") or remote.get("signers") or []
        if isinstance(sigs, list) and sigs:
            completed = all(
                str(s.get("status", s.get("state", ""))).upper()
                in {"CO", "COMPLETED", "SIGNED", "DONE"}
                for s in sigs
            )

    if completed and op["estado"] == "pendiente_firma":
        transicionar(operacion_id, "firmado", nota="sync Signatura")
        transicionar(operacion_id, "listo_desembolso", nota="auto post-firma")
        log_event(operacion_id, "signed", {"signatura_doc_id": doc_id})

    return get_operacion(operacion_id) or {}


def marcar_desembolsado(operacion_id: int, referencia: str = "") -> dict[str, Any]:
    op = get_operacion(operacion_id)
    if not op:
        raise ValueError("Operación no encontrada.")
    if op["estado"] != "listo_desembolso":
        raise ValueError("Solo se desembolsa en estado listo_desembolso (firma completa).")
    transicionar(operacion_id, "desembolsado", nota=referencia)
    log_event(operacion_id, "disbursed", {"referencia": referencia})
    return get_operacion(operacion_id) or {}


def timeline(operacion_id: int) -> list[dict[str, Any]]:
    events = list_audit_events(operacion_id)
    out = []
    for e in events:
        try:
            payload = json.loads(e.get("payload_json") or "{}")
        except json.JSONDecodeError:
            payload = {}
        out.append(
            {
                "id": e["id"],
                "event_type": e["event_type"],
                "payload": payload,
                "prev_hash": e["prev_hash"],
                "event_hash": e["event_hash"],
                "created_at_utc": e["created_at_utc"],
            }
        )
    return out


def resumen_cartera_trazabilidad() -> dict[str, Any]:
    ops = list_operaciones()
    by_estado: dict[str, int] = {}
    by_tipo: dict[str, int] = {}
    monto_pendiente_firma = 0.0
    monto_listo = 0.0
    for o in ops:
        by_estado[o["estado"]] = by_estado.get(o["estado"], 0) + 1
        by_tipo[o["tipo"]] = by_tipo.get(o["tipo"], 0) + 1
        if o["estado"] == "pendiente_firma":
            monto_pendiente_firma += float(o["monto"])
        if o["estado"] == "listo_desembolso":
            monto_listo += float(o["monto"])
    return {
        "total": len(ops),
        "by_estado": by_estado,
        "by_tipo": by_tipo,
        "monto_pendiente_firma": monto_pendiente_firma,
        "monto_listo_desembolso": monto_listo,
    }
