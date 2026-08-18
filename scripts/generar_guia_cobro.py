"""Genera la guía PDF de cobranza y alta ante el Banco Central."""

from __future__ import annotations

from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY, TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import (
    ListFlowable,
    ListItem,
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

OUT = Path(__file__).resolve().parents[1] / "docs" / "Finan_guia_cobro_BCRA.pdf"

NAVY = colors.HexColor("#0f172a")
GREEN = colors.HexColor("#065f46")
TEAL = colors.HexColor("#0f766e")
AMBER = colors.HexColor("#92400e")
LIGHT = colors.HexColor("#f1f5f9")
ROW = colors.HexColor("#ecfdf5")
HINT = colors.HexColor("#475569")


def styles():
    base = getSampleStyleSheet()
    return {
        "kicker": ParagraphStyle(
            "kicker",
            parent=base["Normal"],
            fontSize=9,
            textColor=TEAL,
            alignment=TA_CENTER,
            spaceAfter=4,
        ),
        "title": ParagraphStyle(
            "title",
            parent=base["Heading1"],
            fontSize=18,
            leading=22,
            textColor=NAVY,
            alignment=TA_CENTER,
            spaceAfter=6,
        ),
        "subtitle": ParagraphStyle(
            "subtitle",
            parent=base["Normal"],
            fontSize=10,
            leading=14,
            textColor=HINT,
            alignment=TA_CENTER,
            spaceAfter=14,
        ),
        "h1": ParagraphStyle(
            "h1",
            parent=base["Heading1"],
            fontSize=13,
            leading=16,
            textColor=NAVY,
            spaceBefore=12,
            spaceAfter=6,
        ),
        "h2": ParagraphStyle(
            "h2",
            parent=base["Heading2"],
            fontSize=11,
            leading=14,
            textColor=TEAL,
            spaceBefore=9,
            spaceAfter=4,
        ),
        "body": ParagraphStyle(
            "body",
            parent=base["Normal"],
            fontSize=9.5,
            leading=13,
            alignment=TA_JUSTIFY,
            textColor=NAVY,
            spaceAfter=6,
        ),
        "bullet": ParagraphStyle(
            "bullet",
            parent=base["Normal"],
            fontSize=9.5,
            leading=13,
            textColor=NAVY,
            leftIndent=4,
        ),
        "note": ParagraphStyle(
            "note",
            parent=base["Normal"],
            fontSize=8.5,
            leading=11.5,
            textColor=AMBER,
            alignment=TA_JUSTIFY,
            spaceBefore=4,
            spaceAfter=8,
        ),
        "small": ParagraphStyle(
            "small",
            parent=base["Normal"],
            fontSize=8,
            leading=11,
            textColor=HINT,
            alignment=TA_LEFT,
        ),
        "cell": ParagraphStyle(
            "cell",
            parent=base["Normal"],
            fontSize=8,
            leading=11,
            textColor=NAVY,
        ),
        "cell_h": ParagraphStyle(
            "cell_h",
            parent=base["Normal"],
            fontSize=8,
            leading=11,
            textColor=colors.white,
        ),
        "center": ParagraphStyle(
            "center",
            parent=base["Normal"],
            fontSize=9,
            alignment=TA_CENTER,
            textColor=NAVY,
        ),
    }


def bullets(s, items: list[str]) -> ListFlowable:
    return ListFlowable(
        [ListItem(Paragraph(t, s["bullet"]), leftIndent=8, bulletColor=TEAL) for t in items],
        bulletType="bullet",
        bulletFontSize=8,
        leftIndent=12,
        spaceAfter=8,
    )


def table(s, header: list[str], rows: list[list[str]], col_widths=None):
    data = [[Paragraph(h, s["cell_h"]) for h in header]]
    for row in rows:
        data.append([Paragraph(c, s["cell"]) for c in row])
    t = Table(data, colWidths=col_widths, repeatRows=1)
    t.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), TEAL),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("BACKGROUND", (0, 1), (-1, -1), colors.white),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, ROW]),
                ("GRID", (0, 0), (-1, -1), 0.35, colors.HexColor("#cbd5e1")),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 5),
                ("RIGHTPADDING", (0, 0), (-1, -1), 5),
                ("TOPPADDING", (0, 0), (-1, -1), 5),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
            ]
        )
    )
    return t


def box(s, title: str, body: str, color=GREEN):
    inner = Table(
        [[Paragraph(f"<b>{title}</b><br/>{body}", s["cell"])]],
        colWidths=[16.5 * cm],
    )
    inner.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), LIGHT),
                ("BOX", (0, 0), (-1, -1), 1.2, color),
                ("LEFTPADDING", (0, 0), (-1, -1), 8),
                ("RIGHTPADDING", (0, 0), (-1, -1), 8),
                ("TOPPADDING", (0, 0), (-1, -1), 7),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
            ]
        )
    )
    return inner


def footer(canvas, doc):
    canvas.saveState()
    canvas.setFillColor(HINT)
    canvas.setFont("Helvetica", 8)
    canvas.drawString(2 * cm, 1.2 * cm, "Finan · guía operativa · agosto 2026 · no es dictamen legal")
    canvas.drawRightString(19.7 * cm, 1.2 * cm, f"Página {doc.page}")
    canvas.setStrokeColor(TEAL)
    canvas.setLineWidth(1.5)
    canvas.line(2 * cm, 1.55 * cm, 19.7 * cm, 1.55 * cm)
    canvas.restoreState()


def build():
    s = styles()
    story = []

    story.append(Paragraph("FINAN", s["kicker"]))
    story.append(Paragraph("Cómo cobrar y cómo entrar al Banco Central", s["title"]))
    story.append(
        Paragraph(
            "Préstamo al comercio y crédito al cliente del local · "
            "hasta el alta y después · 17 de agosto de 2026",
            s["subtitle"],
        )
    )
    story.append(
        box(
            s,
            "En una frase",
            "Hasta que el Banco Central te habilite, cobrás con un procesador que se queda un porcentaje. "
            "Eso es legal si usás un cobrador de pagos (Mercado Pago, un banco, Pay per TIC). "
            "No es legal inventar un débito automático de préstamos ni revender Cobro con Transferencia. "
            "Cuando te den el alta, el mismo banco o procesador puede pasarte a Cobro con Transferencia "
            "y ahí el piso de comisión ronda el 0,6% por cuota.",
        )
    )

    story.append(Paragraph("1. Dos roles distintos (no los mezcles)", s["h1"]))
    story.append(
        Paragraph(
            "El Banco Central, en la comunicación A 8406 (2 de marzo de 2026), separó quién debita "
            "la cuenta de quién presta la plata. El Cobro con Transferencia para cuotas de préstamos "
            "está disponible a partir del 31 de agosto de 2026.",
            s["body"],
        )
    )
    story.append(
        table(
            s,
            ["Rol", "Quién es", "Qué hace", "Qué trámite"],
            [
                [
                    "Aceptador de cobro con transferencia",
                    "Un banco, un administrador de transferencias o un aceptador de pago con transferencia ya inscripto como proveedor de servicios de pago.",
                    "Ofrece el tubo: pide el consentimiento y debita la cuenta del cliente.",
                    "Registro de Proveedores de Servicios de Pago + habilitación extra por mail.",
                ],
                [
                    "Quien cobra el préstamo (ordenante)",
                    "Tu financiera (Finan), siempre persona jurídica.",
                    "Presta y contrata al aceptador para que le recaude las cuotas.",
                    "Registro de Otros Proveedores no Financieros de Crédito + habilitación extra por mail.",
                ],
            ],
            col_widths=[3.4 * cm, 4.3 * cm, 4.4 * cm, 4.4 * cm],
        )
    )
    story.append(Spacer(1, 0.25 * cm))
    story.append(
        Paragraph(
            "Finan hoy debería ser lo segundo: la que presta. El aceptador es Mercado Pago, un banco "
            "o un procesador. El banco dice que Cobro con Transferencia solo lo ofrecen aceptadores "
            "habilitados: no se puede contratar ni ofrecer por intermediarios sueltos. "
            "Eso no te impide, mientras tanto, usar un procesador de pagos (link, tarjeta, cupón, split).",
            s["body"],
        )
    )

    story.append(Paragraph("2. Qué te conviene pedir ahora (para cobrar préstamos)", s["h1"]))
    story.append(
        Paragraph(
            "El Banco Central inscribe personas jurídicas, no a vos como individuo. Primero SAS, SRL o SA "
            "con CUIT, estatuto que permita prestar dinero y Clave Fiscal nivel 3.",
            s["body"],
        )
    )
    story.append(
        bullets(
            s,
            [
                "Inscripción en ARCA → servicio <b>BCRA – Proveedores No Financieros de Crédito – Registro de Proveedores No Financieros de Crédito</b>.",
                "Papeles: nota firmada por el representante, estatuto, último balance auditado si ya cerraron un ejercicio, socios, responsable de seguridad y responsable del régimen informativo.",
                "Si el aplicativo todavía no tiene el tilde de Cobro con Transferencia, un mail a <b>subgcia.autorizacion.enof@bcra.gob.ar</b> pidiendo usar ese servicio.",
                "Después, contrato con un aceptador (banco o procesador habilitado) para que debite las cuotas de tus clientes.",
            ],
        )
    )
    story.append(
        Paragraph(
            "Si todavía no llegás a $10 millones de financiaciones en el último balance, la inscripción "
            "no es obligatoria, pero sí la necesitás para este cobro. El Banco Central deja inscribirse "
            "igual, de forma optativa. Consultas: gerencia.autorizaciones@bcra.gob.ar.",
            s["body"],
        )
    )
    story.append(
        Paragraph(
            "Trámite: https://www.bcra.gob.ar/solicitar-inscripcion-actualizacion-o-dar-de-baja-para-otros-proveedores-no-financieros-de-credito/",
            s["small"],
        )
    )

    story.append(Paragraph("3. Si igual querés ser aceptador (el tubo)", s["h1"]))
    story.append(
        Paragraph(
            "Eso es armar una empresa de pagos, no solo de créditos. Lleva banco sponsor, conexión al "
            "sistema nacional de pagos, alta como aceptador de pago con transferencia y después otra "
            "habilitación para cobro con transferencia. Tenés 6 meses desde el certificado para empezar "
            "a operar o te dan de baja. No entra en dos semanas.",
            s["body"],
        )
    )
    story.append(
        bullets(
            s,
            [
                "ARCA → <b>BCRA – Proveedores de Servicios de Pago</b>, función Aceptador.",
                "Conexión al sistema de pagos a través de un banco.",
                "Alta operativa de pago con transferencia (QR / transferencias) con el administrador del esquema.",
                "Habilitación extra de cobro con transferencia por mail a <b>sdep_vigilancia_estadisticas@bcra.gob.ar</b> hasta que el aplicativo esté listo.",
            ],
        )
    )
    story.append(
        Paragraph(
            "Trámite: https://www.bcra.gob.ar/inscripcion-registro-proveedores-servicios-de-pago/<br/>"
            "Norma: https://www.bcra.gob.ar/archivos/Pdfs/comytexord/A8406.pdf",
            s["small"],
        )
    )

    story.append(PageBreak())
    story.append(Paragraph("4. Hasta el alta: usar un procesador que cobre un porcentaje", s["h1"]))
    story.append(
        Paragraph(
            "Sí se puede. La clave es no pedirle a un desconocido que “te debite el CBU del préstamo”. "
            "Le pedís a un procesador ya habilitado que recaude cada pago (tarjeta, dinero en cuenta, "
            "transferencia, Rapipago) y se quede su comisión. Vos cobrás el resto.",
            s["body"],
        )
    )

    story.append(
        table(
            s,
            ["Qué sí", "Qué no"],
            [
                [
                    "Contratar a Mercado Pago, un banco o Pay per TIC para que procesen cada cobro y te acrediten, cobrándote un %.",
                    "Que un “intermediario” te venda Cobro con Transferencia o DEBIN automático de préstamos sin ser aceptador habilitado.",
                ],
                [
                    "Split de Mercado Pago: cada venta del local se parte sola. Mercado Pago se lleva su comisión de cobro; vos te llevás tu parte.",
                    "Esperar que el local o el cliente te transfieran “cuando puedan”.",
                ],
                [
                    "Link de pago o cupón por cada cuota del cliente. Si paga, entra. Si no, el local lo persigue.",
                    "Inventar un débito mensual a la cuenta del cliente por tu cuenta. El Banco Central lo restringe para préstamos.",
                ],
            ],
            col_widths=[8.25 * cm, 8.25 * cm],
        )
    )

    story.append(Paragraph("4.1 Comercio: la mejor vía mientras tanto", s["h2"]))
    story.append(
        Paragraph(
            "<b>Mercado Pago split (marketplace).</b> El local vincula su cuenta (OAuth). Las ventas "
            "pasan por tu checkout (QR, link o Point conectado). En cada cobro:",
            s["body"],
        )
    )
    story.append(
        bullets(
            s,
            [
                "Primero Mercado Pago se queda su comisión de procesamiento (la paga el vendedor).",
                "Después te acreditan a vos el monto que pusiste como comisión de marketplace (<i>marketplace_fee</i> o <i>application_fee</i>).",
                "El resto va al local. Él no te transfiere. Si vende, cobrás.",
            ],
        )
    )
    story.append(
        Paragraph(
            "Mercado Pago no te cobra un extra por partir el pago: cobra la comisión de cobro de siempre. "
            "Documentación: https://www.mercadopago.com.ar/developers/es/docs/split-payments/landing",
            s["body"],
        )
    )
    story.append(
        Paragraph(
            "<b>Condición:</b> el local tiene que cobrar por tu circuito. Si usa su Point suelto, Payway "
            "propio o pasa todo a efectivo, no hay descuento. No desembolses hasta ver la cuenta vinculada "
            "y una prueba de venta.",
            s["note"],
        )
    )
    story.append(
        Paragraph(
            "<b>Ejemplo.</b> Prestás $1.000.000. El local vende ~$80.000 por día con Mercado Pago. "
            "Pactás 15% de cada cobro. Un cliente paga $10.000 con QR. Mercado Pago se lleva su comisión "
            "(orden de magnitud: débito al instante ~3,25% + IVA; crédito al instante ~6,29% + IVA). "
            "Vos te llevás ~$1.500. Al local le llega el resto. En unos tres meses, si sigue vendiendo, "
            "recuperás el préstamo sin que él te deposite.",
            s["body"],
        )
    )

    story.append(Paragraph("4.2 Cliente del local: procesadores que cobran un %", s["h2"]))
    story.append(
        Paragraph(
            "Acá no hay caja diaria. Hasta Cobro con Transferencia, lo más barato y efectivo es que pague "
            "<b>en el propio local</b>. El procesador es el plan B: cada cuota un link o un cupón.",
            s["body"],
        )
    )
    story.append(
        table(
            s,
            ["Procesador", "Cómo se usa", "Qué te cobra (referencia)", "Cuándo sirve"],
            [
                [
                    "Caja del local",
                    "La cuota se paga en el negocio o no se le vuelve a fiar.",
                    "Cero de procesamiento.",
                    "Siempre. Es la primera capa.",
                ],
                [
                    "Mercado Pago · link de pago",
                    "Mandás un link por WhatsApp o mail por cada cuota. El cliente paga con tarjeta, dinero en cuenta, transferencia, Rapipago o Pago Fácil.",
                    "Link / checkout (página oficial, varía por provincia y plazo): al instante ~6,29% + IVA; 10 días ~4,39% + IVA; 18 días ~3,39% + IVA; 35 días ~1,49% + IVA.",
                    "Arrancar ya, sin ser aceptador. Alta de cuenta comercial y listo.",
                ],
                [
                    "Pay per TIC (Pago TIC)",
                    "Ellos recaudan por tu cuenta: link, cupón, tarjeta, débito de servicios. Contacto: 0810-220-7777 · info@pagotic.com · pagotic.com",
                    "Publican hasta ~0,9% y solo si el cobro sale (volumen).",
                    "Cuando tengas sociedad. Preguntá explícito que sea cobro de cuota de compra / link, no débito de préstamo hasta el alta del Banco Central.",
                ],
                [
                    "Banco (Galicia, Macro, Santander, etc.)",
                    "Área comercial de recaudaciones o aceptador. Cuando estés inscripto, te conectan a Cobro con Transferencia.",
                    "Para préstamos, el piso del Banco Central es 0,6% por cuota, sin techo. El banco puede cobrarte más.",
                    "Después del alta. Hoy pedí reunión para quedar en la fila.",
                ],
            ],
            col_widths=[3.2 * cm, 5.0 * cm, 4.2 * cm, 4.1 * cm],
        )
    )
    story.append(Spacer(1, 0.15 * cm))
    story.append(
        Paragraph(
            "Costos Mercado Pago: https://www.mercadopago.com.ar/herramientas-para-vender/link-de-pago "
            "— se actualizan y cambian por provincia. Confirmá en tu cuenta el día que operes.",
            s["small"],
        )
    )

    story.append(Paragraph("4.3 Ejemplo con una heladera", s["h2"]))
    story.append(
        Paragraph(
            "Producto $600.000 en 6 cuotas de $120.000. El cliente le debe al local. Vos le adelantás "
            "al local y cobrás con el split. Además, si el cliente te paga a vos la cuota:",
            s["body"],
        )
    )
    story.append(
        table(
            s,
            ["Cómo paga esa cuota de $120.000", "Qué se lleva el procesador (aprox.)", "Qué te queda"],
            [
                ["En la caja del local", "$0", "$120.000 (si te lo rinde el local)"],
                [
                    "Link Mercado Pago, plata al instante (~6,29% + IVA ≈ 7,6%)",
                    "~$9.120",
                    "~$110.880",
                ],
                [
                    "Link Mercado Pago a 18 días (~3,39% + IVA ≈ 4,1%)",
                    "~$4.920",
                    "~$115.080",
                ],
                ["Pay per TIC ~0,9% (si te toman)", "~$1.080", "~$118.920"],
                [
                    "Cobro con Transferencia, piso 0,6% (después del alta)",
                    "~$720",
                    "~$119.280",
                ],
            ],
            col_widths=[6.5 * cm, 5.0 * cm, 5.0 * cm],
        )
    )
    story.append(Spacer(1, 0.2 * cm))
    story.append(
        Paragraph(
            "Mientras más caro el procesador, más tenés que cargar esa pérdida en la tasa que le cobrás "
            "al local o al cliente. No prestés como si el cobro fuera gratis.",
            s["note"],
        )
    )

    story.append(Paragraph("5. Respaldo si dejan de pagar", s["h1"]))
    story.append(
        Paragraph(
            "El procesador cobra el día a día. Si el local deja de vender o el cliente no paga, hace falta el papel:",
            s["body"],
        )
    )
    story.append(
        bullets(
            s,
            [
                "<b>Pagaré</b> firmado en Signatura (juicio más rápido que un contrato suelto).",
                "<b>Cheque electrónico</b> si el local tiene chequera: lo emite él en su banco, vos guardás el número.",
                "Firma primero, desembolso después. Sin expediente firmado, no hay plata.",
            ],
        )
    )

    story.append(Paragraph("6. Plan de esta semana", s["h1"]))
    story.append(
        table(
            s,
            ["Orden", "Acción"],
            [
                ["1", "Sociedad con objeto de crédito (y de pagos solo si más adelante querés ser el tubo)."],
                ["2", "Clave Fiscal nivel 3 de esa sociedad."],
                ["3", "Alta de cuenta Mercado Pago de la sociedad e ir al split (OAuth del primer comercio)."],
                ["4", "Para el cliente: cuota en el local + link de pago Mercado Pago por cada vencimiento."],
                ["5", "Mail a Pay per TIC (info@pagotic.com) y a un banco pidiendo recaudar cuotas con su comisión."],
                ["6", "Inscripción de proveedor no financiero de crédito en ARCA."],
                ["7", "Mail a subgcia.autorizacion.enof@bcra.gob.ar para usar Cobro con Transferencia."],
                ["8", "Dejar “ser aceptador” para cuando ya prestás en serio."],
            ],
            col_widths=[2.2 * cm, 14.3 * cm],
        )
    )

    story.append(Spacer(1, 0.4 * cm))
    story.append(
        Paragraph(
            "Esta guía es operativa para armar el negocio. No reemplaza abogado ni el texto vigente el día "
            "del trámite. Tarifas de Mercado Pago y Pay per TIC son públicas o periodísticas: cada uno "
            "te cotiza la suya al firmar.",
            s["small"],
        )
    )
    story.append(
        Paragraph(
            "Mails Banco Central: subgcia.autorizacion.enof@bcra.gob.ar · "
            "gerencia.autorizaciones@bcra.gob.ar · sdep_vigilancia_estadisticas@bcra.gob.ar",
            s["small"],
        )
    )

    OUT.parent.mkdir(parents=True, exist_ok=True)
    doc = SimpleDocTemplate(
        str(OUT),
        pagesize=A4,
        leftMargin=2 * cm,
        rightMargin=2 * cm,
        topMargin=1.6 * cm,
        bottomMargin=2 * cm,
        title="Finan — Cómo cobrar y cómo entrar al Banco Central",
        author="Finan",
    )
    doc.build(story, onFirstPage=footer, onLaterPages=footer)
    return OUT


if __name__ == "__main__":
    path = build()
    print(path)
