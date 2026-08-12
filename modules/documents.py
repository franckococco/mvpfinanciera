"""
Generación mínima de PDF contractual (placeholder hasta plantillas legales finales).

Usa reportlab. El contenido es operativo: no reemplaza revisión de abogado.
"""

from __future__ import annotations

from datetime import datetime, timezone
from io import BytesIO
from typing import Any

from reportlab.lib.pagesizes import A4
from reportlab.lib.units import cm
from reportlab.pdfgen import canvas


def generar_pdf_operacion(op: dict[str, Any], extra: dict[str, Any] | None = None) -> bytes:
    """PDF simple de cesión/crédito/BNPL para enviar a Signatura."""
    extra = extra or {}
    buf = BytesIO()
    c = canvas.Canvas(buf, pagesize=A4)
    width, height = A4
    y = height - 2 * cm

    def line(text: str, size: int = 11, gap: float = 0.55) -> None:
        nonlocal y
        c.setFont("Helvetica", size)
        c.drawString(2 * cm, y, text[:110])
        y -= gap * cm
        if y < 2 * cm:
            c.showPage()
            y = height - 2 * cm

    tipo = op.get("tipo", "")
    titulo = {
        "factoring": "CONTRATO DE CESIÓN / ADELANTO DE CUPÓN",
        "credito_comercio": "CONTRATO DE CRÉDITO AL COMERCIO",
        "bnpl": "CONTRATO / PAGARÉ BNPL",
    }.get(tipo, "DOCUMENTO FINAN · OPERACIÓN")

    c.setFont("Helvetica-Bold", 14)
    c.drawString(2 * cm, y, "FINAN")
    y -= 0.8 * cm
    c.setFont("Helvetica-Bold", 12)
    c.drawString(2 * cm, y, titulo)
    y -= 1.0 * cm

    line(f"Operación ID: {op.get('id')}")
    line(f"Tipo: {tipo}")
    line(f"Comercio: {op.get('comercio', '')}")
    line(f"CUIT comercio: {op.get('cuit') or '—'}")
    line(f"Monto: {op.get('monto')} {op.get('moneda', 'ARS')}")
    line(f"Estado al generar: {op.get('estado')}")
    line(f"Generado UTC: {datetime.now(timezone.utc).isoformat(timespec='seconds')}")
    y -= 0.3 * cm

    line("Firmantes previstos:", size=11)
    line(f"  Comercio email: {op.get('email_firmante') or '—'}")
    line(f"  Comercio tel: {op.get('telefono_firmante') or '—'}")
    line(f"  Fiador email: {op.get('email_fiador') or '—'}")
    line(f"  Fiador tel: {op.get('telefono_fiador') or '—'}")
    line(f"  Fiador CUIT: {op.get('cuit_fiador') or '—'}")
    y -= 0.4 * cm

    if extra:
        line("Detalle operativo:", size=11)
        for k, v in extra.items():
            line(f"  {k}: {v}")

    y -= 0.5 * cm
    line("Cláusulas marco (borrador — pendiente texto legal definitivo):")
    line("1) Cesión / crédito con recurso hasta cobro efectivo.")
    line("2) Garantía de legitimidad de los créditos cedidos.")
    line("3) Fiador solidario (si se indica) como principal pagador.")
    line("4) El desembolso queda condicionado a firma electrónica completa.")
    y -= 0.5 * cm
    line("Este PDF se firma vía Signatura. La evidencia de firma la custodia Signatura.")
    line("Finan conserva la trazabilidad de estados y el hash SHA-256 del documento.")

    c.showPage()
    c.save()
    return buf.getvalue()
