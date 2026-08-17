"""
Plantillas contractuales PDF (borrador operativo para firma Signatura).

IMPORTANTE: texto marco para operación. Debe revisarlo un abogado antes de
usar con dinero real. Versionado vía TEMPLATE_VERSION.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from io import BytesIO
from typing import Any

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import (
    HRFlowable,
    ListFlowable,
    ListItem,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

TEMPLATE_VERSION = "v1.0-2026-08"


def _styles():
    base = getSampleStyleSheet()
    return {
        "title": ParagraphStyle(
            "FinanTitle",
            parent=base["Heading1"],
            fontSize=14,
            alignment=TA_CENTER,
            spaceAfter=8,
        ),
        "h2": ParagraphStyle(
            "FinanH2",
            parent=base["Heading2"],
            fontSize=11,
            spaceBefore=10,
            spaceAfter=6,
        ),
        "body": ParagraphStyle(
            "FinanBody",
            parent=base["Normal"],
            fontSize=9,
            leading=12,
            alignment=TA_JUSTIFY,
            spaceAfter=4,
        ),
        "small": ParagraphStyle(
            "FinanSmall",
            parent=base["Normal"],
            fontSize=8,
            leading=10,
            textColor=colors.HexColor("#444444"),
        ),
        "center": ParagraphStyle(
            "FinanCenter",
            parent=base["Normal"],
            fontSize=9,
            alignment=TA_CENTER,
        ),
    }


def _payload(op: dict[str, Any]) -> dict[str, Any]:
    raw = op.get("payload_json") or "{}"
    if isinstance(raw, dict):
        return raw
    try:
        return json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        return {}


def _header_block(styles, titulo: str, op: dict[str, Any]) -> list:
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    story = [
        Paragraph("FINAN", styles["title"]),
        Paragraph(titulo, styles["center"]),
        Spacer(1, 0.2 * cm),
        Paragraph(
            f"Plantilla <b>{TEMPLATE_VERSION}</b> · Expediente <b>#{op.get('id')}</b> · "
            f"Generado {now}",
            styles["small"],
        ),
        HRFlowable(width="100%", thickness=1, color=colors.HexColor("#334155")),
        Spacer(1, 0.3 * cm),
    ]
    return story


def _parties_table(op: dict[str, Any], styles) -> Table:
    data = [
        [Paragraph("<b>Parte</b>", styles["small"]), Paragraph("<b>Datos</b>", styles["small"])],
        [
            Paragraph("Comercio / Cedente / Deudor", styles["small"]),
            Paragraph(
                f"{op.get('comercio') or '—'}<br/>CUIT: {op.get('cuit') or '—'}<br/>"
                f"Email: {op.get('email_firmante') or '—'} · Tel: {op.get('telefono_firmante') or '—'}",
                styles["small"],
            ),
        ],
        [
            Paragraph("Fiador / Codeudor (si aplica)", styles["small"]),
            Paragraph(
                f"CUIT/CUIL: {op.get('cuit_fiador') or '—'}<br/>"
                f"Email: {op.get('email_fiador') or '—'} · Tel: {op.get('telefono_fiador') or '—'}",
                styles["small"],
            ),
        ],
        [
            Paragraph("Financiera / Cesionaria", styles["small"]),
            Paragraph(
                "FINAN (préstamos al comercio y créditos al cliente del comercio) — "
                "datos a completar en contrato marco.",
                styles["small"],
            ),
        ],
    ]
    t = Table(data, colWidths=[5 * cm, 12 * cm])
    t.setStyle(
        TableStyle(
            [
                ("GRID", (0, 0), (-1, -1), 0.4, colors.grey),
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#e2e8f0")),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 4),
                ("RIGHTPADDING", (0, 0), (-1, -1), 4),
            ]
        )
    )
    return t


def _clausulas_comunes(styles) -> list:
    items = [
        "Firma electrónica: las Partes aceptan firmar este instrumento mediante plataforma de firma electrónica (Signatura u equivalente), con validez conforme Ley 25.506 y Art. 288 CCCN.",
        "Desembolso condicionado: FINAN no está obligada a transferir fondos hasta la firma completa de todos los firmantes y la verificación de checklist interno.",
        "Domicilio electrónico: las notificaciones a los emails indicados se tendrán por válidas.",
        "Ley aplicable: República Argentina. Jurisdicción de los tribunales ordinarios del domicilio de FINAN, sin perjuicio de fueros especiales.",
        "Aviso: este documento es plantilla operativa versionada; el texto definitivo debe ser validado por asesoramiento jurídico profesional.",
    ]
    return [
        Paragraph("Cláusulas generales", styles["h2"]),
        ListFlowable(
            [ListItem(Paragraph(t, styles["body"]), leftIndent=8, bulletColor=colors.black) for t in items],
            bulletType="1",
        ),
    ]


def _pagare_section(styles, op: dict[str, Any], monto: float, detalle: str) -> list:
    return [
        Paragraph("ANEXO — PAGARÉ DIGITAL", styles["h2"]),
        Paragraph(
            f"Por el presente, el firmante se constituye en deudor por la suma de "
            f"<b>$ {monto:,.2f} ARS</b> ({detalle}), pagadera a la vista o a la fecha "
            f"de vencimiento que resulte de la operación <b>#{op.get('id')}</b>, "
            f"a la orden de FINAN o quien sus derechos represente.",
            styles["body"],
        ),
        Paragraph(
            "Este pagaré se emite en el marco de la operación descripta en el contrato principal. "
            "El fiador solidario, de existir, se obliga como principal pagador, renunciando a los "
            "beneficios de excusión y división en los términos del Código Civil y Comercial.",
            styles["body"],
        ),
        Paragraph(
            f"Lugar y fecha de emisión: {datetime.now().strftime('%d/%m/%Y')}.",
            styles["body"],
        ),
    ]


def _build_cesion_factoring(op: dict[str, Any], extra: dict[str, Any]) -> list:
    styles = _styles()
    p = {**_payload(op), **extra}
    monto = float(op.get("monto") or 0)
    neto = float(p.get("monto_neto") or monto)
    comision = float(p.get("ganancia") or p.get("tasa_comision") or 0)
    tasa = p.get("tasa_comision", "—")
    liq = p.get("fecha_liquidacion", "—")

    story = _header_block(styles, "CONTRATO DE CESIÓN DE CRÉDITOS / ADELANTO DE CUPÓN", op)
    story.append(Paragraph("Partes", styles["h2"]))
    story.append(_parties_table(op, styles))
    story.append(Spacer(1, 0.35 * cm))

    story.append(Paragraph("Objeto", styles["h2"]))
    story.append(
        Paragraph(
            f"El Comercio cede a FINAN, con <b>recurso (pro solvendo)</b>, los derechos de cobro "
            f"derivados del/los cupón/es de medios de pago electrónicos por un monto bruto de "
            f"<b>$ {monto:,.2f} ARS</b>, con fecha de liquidación estimada <b>{liq}</b>. "
            f"FINAN abonará al Comercio un neto estimado de <b>$ {neto:,.2f} ARS</b> "
            f"(comisión / descuento: {tasa}% · ganancia estimada $ {float(comision) if isinstance(comision, (int, float)) else 0:,.2f}).",
            styles["body"],
        )
    )

    story.append(Paragraph("Cláusulas innegociables de la cesión", styles["h2"]))
    cesion_items = [
        "Cesión con recurso: la cesión no extingue la obligación del Comercio hasta que FINAN perciba el 100% de los fondos de la procesadora / adquirente.",
        "Garantía de legitimidad: el Comercio declara que los cupones provienen de ventas reales, sin contracargos previsibles ni duplicaciones, y garantiza la existencia y legitimidad del crédito cedido.",
        "Reemplazo / reembolso: ante contracargo, rechazo o falta de liquidación, el Comercio repondrá fondos o cederá cupón equivalente en 24/48 horas hábiles.",
        "CBU de liquidación: el Comercio se obliga a mantener la cuenta de acreditación cedida / informada a FINAN hasta el cobro efectivo; el cambio no autorizado constituye incumplimiento grave.",
        "Fiador solidario: de intervenir fiador, responde como principal pagador de todas las obligaciones emergentes.",
        "Caída de plazos: el incumplimiento habilita a FINAN a exigir la totalidad adeudada y ejecutar el pagaré anexo.",
    ]
    story.append(
        ListFlowable(
            [ListItem(Paragraph(t, styles["body"]), leftIndent=8) for t in cesion_items],
            bulletType="1",
        )
    )
    story.extend(_clausulas_comunes(styles))
    story.extend(_pagare_section(styles, op, monto, "monto bruto del cupón cedido / saldo deudor por recurso"))
    story.append(Spacer(1, 0.4 * cm))
    story.append(
        Paragraph(
            "El firmante declara haber leído y aceptado el contrato de cesión y el pagaré anexo.",
            styles["body"],
        )
    )
    return story


def _build_rbf(op: dict[str, Any], extra: dict[str, Any]) -> list:
    styles = _styles()
    p = {**_payload(op), **extra}
    monto = float(op.get("monto") or 0)
    rate = p.get("monthly_rate", p.get("tasa_mensual", "—"))
    months = p.get("term_months", p.get("cuotas", "—"))
    calc = p.get("calc_type", "FRENCH")
    freq = p.get("frequency", "DAILY")
    total = p.get("total_a_cobrar", "—")
    cuota = p.get("cuota_mensual", "—")
    garant = p.get("garantias") or {}

    story = _header_block(styles, "CONTRATO DE PRÉSTAMO AL COMERCIO", op)
    story.append(Paragraph("Partes", styles["h2"]))
    story.append(_parties_table(op, styles))
    story.append(Spacer(1, 0.35 * cm))

    story.append(Paragraph("Objeto", styles["h2"]))
    story.append(
        Paragraph(
            f"FINAN otorga al Comercio un préstamo por capital "
            f"<b>$ {monto:,.2f} ARS</b>, a tasa mensual <b>{rate}%</b>, plazo <b>{months}</b> mes(es), "
            f"método de cálculo <b>{calc}</b>, frecuencia de cobro <b>{freq}</b>. "
            f"Cuota mensual objetivo: <b>{cuota}</b> · Total a cobrar estimado: <b>{total}</b>. "
            f"El Comercio se obliga a restituir el capital y accesorios mediante retenciones "
            f"sobre sus ventas electrónicas.",
            styles["body"],
        )
    )

    story.append(Paragraph("Cobro por barridos", styles["h2"]))
    rbf_items = [
        "El Comercio autoriza a FINAN a percibir cobros mediante retenciones/barridos sobre el flujo de pagos electrónicos (POS/QR/tarjetas) según la frecuencia pactada.",
        "La falta de venta en hasta 3 días por mes puede ser absorbida internamente por la plataforma sin perjuicio de la obligación total; ello no implica condonación de deuda.",
        "Si al avance del mes existe atraso, FINAN podrá incrementar temporalmente el porcentaje de retención (auto-recuperación) para alcanzar el objetivo mensual.",
        "Caída de plazos: si la facturación digital cae más del 40% durante 10 días hábiles consecutivos, la deuda vence anticipadamente (IN_DEFAULT).",
        "Mora: tras 24 hs de gracia sobre un barrido impago, podrá aplicarse interés punitorio diario configurable (referencia base 0,5% diario sobre suma impaga).",
        f"Garantías previstas: principal {garant.get('principal', 'PAGARE')} · respaldo {garant.get('respaldo', 'FIANZA/CODEUDOR')}.",
    ]
    story.append(
        ListFlowable(
            [ListItem(Paragraph(t, styles["body"]), leftIndent=8) for t in rbf_items],
            bulletType="1",
        )
    )
    story.extend(_clausulas_comunes(styles))
    total_num = float(total) if isinstance(total, (int, float)) else monto
    story.extend(
        _pagare_section(
            styles,
            op,
            total_num,
            "total adeudado del préstamo al comercio (capital + intereses según método pactado)",
        )
    )
    return story


def _build_bnpl(op: dict[str, Any], extra: dict[str, Any]) -> list:
    styles = _styles()
    p = {**_payload(op), **extra}
    monto = float(op.get("monto") or 0)
    story = _header_block(styles, "CONTRATO / PAGARÉ — CRÉDITO AL CLIENTE DEL COMERCIO", op)
    story.append(Paragraph("Partes", styles["h2"]))
    story.append(_parties_table(op, styles))
    story.append(Spacer(1, 0.35 * cm))
    story.append(
        Paragraph(
            f"Crédito al cliente del comercio por capital <b>$ {monto:,.2f} ARS</b>. "
            f"Cliente DNI: {p.get('dni_cliente', '—')} · {p.get('nombre_cliente', '')}. "
            f"Cuotas: {p.get('cuotas', '—')} · Cuota: {p.get('cuota_mensual', '—')} · "
            f"Total: {p.get('total_a_pagar', '—')}. "
            f"El crédito opera dentro de la red del comercio (tarjeta cerrada / compra en cuotas en el local).",
            styles["body"],
        )
    )
    story.append(
        Paragraph(
            "El deudor se obliga al pago de las cuotas en las fechas del cronograma. "
            "La mora habilita intereses punitorios y acciones de cobro. "
            "Se informa que aplica régimen de defensa del consumidor cuando corresponda.",
            styles["body"],
        )
    )
    story.extend(_clausulas_comunes(styles))
    total = float(p.get("total_a_pagar") or monto)
    story.extend(_pagare_section(styles, op, total, "total del crédito al cliente del comercio"))
    return story


def _build_generico(op: dict[str, Any], extra: dict[str, Any]) -> list:
    styles = _styles()
    story = _header_block(styles, "DOCUMENTO DE OPERACIÓN FINAN", op)
    story.append(_parties_table(op, styles))
    story.append(Spacer(1, 0.3 * cm))
    story.append(
        Paragraph(
            f"Tipo: {op.get('tipo')} · Monto: $ {float(op.get('monto') or 0):,.2f} ARS.",
            styles["body"],
        )
    )
    if extra:
        story.append(Paragraph(f"Detalle: {extra}", styles["small"]))
    story.extend(_clausulas_comunes(styles))
    story.extend(_pagare_section(styles, op, float(op.get("monto") or 0), "monto de la operación"))
    return story


def generar_pdf_operacion(op: dict[str, Any], extra: dict[str, Any] | None = None) -> bytes:
    """Genera el PDF contractual según tipo de expediente."""
    extra = extra or {}
    tipo = (op.get("tipo") or "").lower()
    if tipo == "factoring":
        story = _build_cesion_factoring(op, extra)
    elif tipo in ("rbf", "credito_comercio"):
        story = _build_rbf(op, extra)
    elif tipo == "bnpl":
        story = _build_bnpl(op, extra)
    else:
        story = _build_generico(op, extra)

    buf = BytesIO()
    doc = SimpleDocTemplate(
        buf,
        pagesize=A4,
        leftMargin=1.8 * cm,
        rightMargin=1.8 * cm,
        topMargin=1.5 * cm,
        bottomMargin=1.5 * cm,
        title=f"Finan op {op.get('id')} {TEMPLATE_VERSION}",
        author="Finan",
    )
    doc.build(story)
    return buf.getvalue()


def nombre_plantilla(tipo: str) -> str:
    return {
        "factoring": f"Cesión + Pagaré ({TEMPLATE_VERSION})",
        "rbf": f"Préstamo al comercio + Pagaré ({TEMPLATE_VERSION})",
        "credito_comercio": f"Préstamo al comercio + Pagaré ({TEMPLATE_VERSION})",
        "bnpl": f"Crédito al cliente + Pagaré ({TEMPLATE_VERSION})",
    }.get(tipo, f"Documento ({TEMPLATE_VERSION})")
