"""
Export de legajo de evidencia (paquete descargable).
"""

from __future__ import annotations

import json
import zipfile
from io import BytesIO
from typing import Any

from modules.documents import TEMPLATE_VERSION, generar_pdf_operacion, nombre_plantilla
from modules.traceability import hash_bytes, timeline


def build_legajo_zip(operacion_id: int) -> tuple[bytes, str]:
    """
    Arma ZIP: contrato.pdf + timeline.json + manifest.json.
    Returns: (zip_bytes, filename)
    """
    from modules.database import get_operacion

    op = get_operacion(operacion_id)
    if not op:
        raise ValueError("Operación no encontrada.")

    pdf = generar_pdf_operacion(op)
    events = timeline(operacion_id)
    pdf_hash = hash_bytes(pdf)

    manifest: dict[str, Any] = {
        "operacion_id": op["id"],
        "tipo": op.get("tipo"),
        "comercio": op.get("comercio"),
        "cuit": op.get("cuit"),
        "monto": op.get("monto"),
        "estado": op.get("estado"),
        "template_version": TEMPLATE_VERSION,
        "plantilla": nombre_plantilla(op.get("tipo") or ""),
        "doc_hash_sha256_registrado": op.get("doc_hash_sha256"),
        "pdf_export_sha256": pdf_hash,
        "signatura_doc_id": op.get("signatura_doc_id"),
        "signatura_status": op.get("signatura_status"),
        "eventos": len(events),
        "cadena_ok": _verify_chain(events),
    }

    buf = BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr(f"contrato_op_{op['id']}.pdf", pdf)
        zf.writestr(
            "timeline.json",
            json.dumps(events, ensure_ascii=False, indent=2, default=str),
        )
        zf.writestr(
            "manifest.json",
            json.dumps(manifest, ensure_ascii=False, indent=2, default=str),
        )
        zf.writestr(
            "operacion.json",
            json.dumps(dict(op), ensure_ascii=False, indent=2, default=str),
        )

    name = f"finan_legajo_op_{op['id']}_{TEMPLATE_VERSION}.zip"
    return buf.getvalue(), name


def _verify_chain(events: list[dict[str, Any]]) -> bool:
    if not events:
        return True
    prev = "GENESIS"
    for e in events:
        if e.get("prev_hash") != prev:
            return False
        prev = e.get("event_hash")
    return True
