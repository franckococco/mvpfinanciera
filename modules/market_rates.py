"""
Aranceles y plazos del mercado argentino — datos de fuentes oficiales.

Cada fila incluye `nota` con la condición publicada y `fuente` verificable.
Los % de Getnet/Payway que dicen "Hasta" son techos publicados (el comercio
puede tener una tarifa menor según contrato).
"""

from __future__ import annotations

from datetime import date, timedelta
from typing import Any

ACTUALIZADO = "2026-08-09"

SIGNATURA_COSTO_FIRMA_ARS = 1700.0  # Flex: $1.700 IVA incl. por crédito / firma simple

# ---------------------------------------------------------------------------
# Catálogo oficial / semi-oficial
# ---------------------------------------------------------------------------
MARKET_RATES: list[dict[str, Any]] = [
    # ===== Fiserv (Visa/Mastercard vía POS/QR — Prisma/Fiserv) =====
    {
        "proveedor": "Fiserv",
        "medio": "QR — Pagos con Transferencia (dinero en cuenta)",
        "arancel_pct": 0.8,
        "iva_sobre_arancel": True,
        "dias_habiles": 0,
        "oficial": True,
        "nota": (
            "Oficial Fiserv: 'Tasa de Descuento 0,8% + IVA'. "
            "Dinero disponible en el momento en la cuenta bancaria."
        ),
        "fuente": "https://www.fiserv.com.ar/pagosconqr/",
    },
    {
        "proveedor": "Fiserv",
        "medio": "Débito (Visa/Master y similares)",
        "arancel_pct": 0.8,
        "iva_sobre_arancel": True,
        "dias_habiles": 1,
        "oficial": True,
        "nota": (
            "Oficial Fiserv QR/tarjetas: arancel 0,8% + IVA. "
            "Dinero disponible en 24 horas hábiles."
        ),
        "fuente": "https://www.fiserv.com.ar/pagosconqr/",
    },
    {
        "proveedor": "Fiserv",
        "medio": "Crédito 1 cuota (plazo estándar micro/pyme)",
        "arancel_pct": 1.8,
        "iva_sobre_arancel": True,
        "dias_habiles": 8,
        "oficial": True,
        "nota": (
            "Oficial Fiserv: 1,8% + IVA · 8 días hábiles. "
            "Excepciones publicadas: Planes Ahora 10 DH; Grandes Contribuyentes 18 DH; "
            "cuotas con financiación otorgante 2 DH; 1ª cuota 'cuota a cuota' 18 DH; "
            "tarjeta local no financiera 18 DH."
        ),
        "fuente": "https://www.fiserv.com.ar/pagosconqr/",
    },
    # ===== Payway (ayuda oficial) =====
    {
        "proveedor": "Payway",
        "medio": "Débito",
        "arancel_pct": 1.0,
        "iva_sobre_arancel": True,
        "dias_habiles": 1,
        "oficial": True,
        "nota": (
            "Oficial Payway (ayuda): 'Débito: 1,0% + IVA'. "
            "El depósito va a la CBU registrada. Plazo típico débito ~1 día hábil "
            "(alineado a normativa BCRA / procesadora)."
        ),
        "fuente": "https://ayuda.payway.com.ar/cobros/medios-de-pago/tarjetas",
    },
    {
        "proveedor": "Payway",
        "medio": "Crédito 1 pago (Visa/Master/Cabal u.o.)",
        "arancel_pct": 1.8,
        "iva_sobre_arancel": True,
        "dias_habiles": 8,
        "oficial": True,
        "nota": (
            "Oficial Payway: 'Crédito: hasta 1,8% + IVA'. "
            "Plazos por categoría BCRA (Com. A 7305): "
            "Cat. I micro/pequeños 8 DH; Cat. II medianos + gastronomía/salud/turismo 10 DH; "
            "Cat. III grandes 18 DH; no bancaria/internacional 18 DH."
        ),
        "fuente": "https://ayuda.payway.com.ar/cobros/medios-de-pago/tarjetas",
    },
    {
        "proveedor": "Payway",
        "medio": "American Express — crédito",
        "arancel_pct": 2.9,
        "iva_sobre_arancel": True,
        "dias_habiles": 8,
        "oficial": True,
        "nota": "Oficial Payway: 'American Express: hasta 2,90% + IVA'.",
        "fuente": "https://ayuda.payway.com.ar/cobros/medios-de-pago/tarjetas",
    },
    # ===== Getnet (tabla oficial completa) =====
    {
        "proveedor": "Getnet",
        "medio": "QR dinero en cuenta",
        "arancel_pct": 0.8,
        "iva_sobre_arancel": True,
        "dias_habiles": 0,
        "oficial": True,
        "nota": (
            "Oficial Getnet tabla: 0,80% + IVA · acreditación inmediata. "
            "Según BCRA TO transferencias; primeros 3 meses puede haber bonificación "
            "si cumple punto 6.3.1.1."
        ),
        "fuente": "https://www.getnet.com.ar/beneficios/promociones-para-tus-clientes/comisiones-por-ventas",
    },
    {
        "proveedor": "Getnet",
        "medio": "Débito — plazo estándar",
        "arancel_pct": 1.0,
        "iva_sobre_arancel": True,
        "dias_habiles": 1,
        "oficial": True,
        "nota": "Oficial Getnet: 'Hasta 1% + IVA (1 día hábil)' en columna plazo estándar.",
        "fuente": "https://www.getnet.com.ar/beneficios/promociones-para-tus-clientes/comisiones-por-ventas",
    },
    {
        "proveedor": "Getnet",
        "medio": "Débito — acreditación anticipada 24 hs",
        "arancel_pct": 1.0,
        "iva_sobre_arancel": True,
        "dias_habiles": 1,
        "oficial": True,
        "nota": "Oficial Getnet: 'Hasta 1% + IVA' en acreditación anticipada (24 horas hábiles).",
        "fuente": "https://www.getnet.com.ar/beneficios/promociones-para-tus-clientes/comisiones-por-ventas",
    },
    {
        "proveedor": "Getnet",
        "medio": "Débito — acreditación inmediata",
        "arancel_pct": 1.53,
        "iva_sobre_arancel": True,
        "dias_habiles": 0,
        "oficial": True,
        "nota": (
            "Oficial Getnet: 'Hasta 1,53% + IVA' inmediata. "
            "Nota (4): inmediata solo para acreditaciones en cuenta Santander."
        ),
        "fuente": "https://www.getnet.com.ar/beneficios/promociones-para-tus-clientes/comisiones-por-ventas",
    },
    {
        "proveedor": "Getnet",
        "medio": "Crédito 1 pago — plazo estándar",
        "arancel_pct": 2.0,
        "iva_sobre_arancel": True,
        "dias_habiles": 8,
        "oficial": True,
        "nota": (
            "Oficial Getnet: 'Hasta 2% + IVA (8 días hábiles)'. "
            "Ejemplo publicado: venta $50.000 → arancel $1.210 (2%+IVA). "
            "Visa/Master internacionales: +0,7% adicional. Plazos BCRA Com. A 7305."
        ),
        "fuente": "https://www.getnet.com.ar/beneficios/promociones-para-tus-clientes/comisiones-por-ventas",
    },
    {
        "proveedor": "Getnet",
        "medio": "Crédito 1 pago — anticipada 24 hs",
        "arancel_pct": 6.75,
        "iva_sobre_arancel": True,
        "dias_habiles": 1,
        "oficial": True,
        "nota": (
            "Oficial Getnet: 'Hasta 6,75% + IVA' acreditación anticipada 24 hs hábiles. "
            "El ejemplo oficial separa arancel base + adicional por anticipación "
            "(0,53% × días corridos sobre el neto post-arancel)."
        ),
        "fuente": "https://www.getnet.com.ar/beneficios/promociones-para-tus-clientes/comisiones-por-ventas",
    },
    {
        "proveedor": "Getnet",
        "medio": "Crédito 1 pago — acreditación inmediata",
        "arancel_pct": 7.28,
        "iva_sobre_arancel": True,
        "dias_habiles": 0,
        "oficial": True,
        "nota": (
            "Oficial Getnet: 'Hasta 7,28% + IVA' inmediata. "
            "Solo cuenta Santander (nota 4). Ejemplo: sobre $50.000, además del arancel "
            "estándar suman ~$3.128,90 de anticipación en el caso publicado."
        ),
        "fuente": "https://www.getnet.com.ar/beneficios/promociones-para-tus-clientes/comisiones-por-ventas",
    },
    {
        "proveedor": "Getnet",
        "medio": "Crédito en cuotas — plazo estándar",
        "arancel_pct": 2.0,
        "iva_sobre_arancel": True,
        "dias_habiles": 2,
        "oficial": True,
        "nota": (
            "Oficial Getnet: 'Hasta 2% + IVA (2 días hábiles)' en cuotas. "
            "No incluye CFT del emisor; ver tabla de tasas/coeficientes en la misma página."
        ),
        "fuente": "https://www.getnet.com.ar/beneficios/promociones-para-tus-clientes/comisiones-por-ventas",
    },
    # ===== Mercado Pago (páginas de producto oficiales) =====
    {
        "proveedor": "Mercado Pago",
        "medio": "Point Smart — débito al instante",
        "arancel_pct": 2.99,
        "iva_sobre_arancel": False,
        "dias_habiles": 0,
        "oficial": True,
        "nota": (
            "Oficial MP Point Smart (landing): muestra 'Débito 2,99%' para plata al instante. "
            "Aclara: 'Los costos pueden variar de acuerdo a los impuestos provinciales'. "
            "El plazo/tasa se configuran en la app (Tu negocio → Costos)."
        ),
        "fuente": "https://www.mercadopago.com.ar/herramientas-para-vender/lectores-point/point-smart",
    },
    {
        "proveedor": "Mercado Pago",
        "medio": "Point Smart — crédito al instante",
        "arancel_pct": 5.99,
        "iva_sobre_arancel": False,
        "dias_habiles": 0,
        "oficial": True,
        "nota": (
            "Oficial MP Point Smart (landing): muestra 'Crédito 5,99%' para plata al instante. "
            "Puede variar por impuestos provinciales y por el plazo que elijas en la app."
        ),
        "fuente": "https://www.mercadopago.com.ar/herramientas-para-vender/lectores-point/point-smart",
    },
    {
        "proveedor": "Mercado Pago",
        "medio": "Point Tap — débito al instante",
        "arancel_pct": 3.25,
        "iva_sobre_arancel": False,
        "dias_habiles": 0,
        "oficial": True,
        "nota": (
            "Oficial MP Point Tap: 'Débito* 3,25%' para dinero al instante. "
            "Nota (*): 'Estos costos no incluyen retenciones o impuestos ajenos a Mercado Pago'."
        ),
        "fuente": "https://www.mercadopago.com.ar/herramientas-para-vender/point-tap",
    },
    {
        "proveedor": "Mercado Pago",
        "medio": "Point Tap — crédito al instante",
        "arancel_pct": 6.29,
        "iva_sobre_arancel": False,
        "dias_habiles": 0,
        "oficial": True,
        "nota": (
            "Oficial MP Point Tap: 'Crédito* 6,29%' para dinero al instante. "
            "Sin retenciones/impuestos ajenos a MP. Hay más tasas según plazo ('Mostrar más tasas' en la web)."
        ),
        "fuente": "https://www.mercadopago.com.ar/herramientas-para-vender/point-tap",
    },
    # ===== Banco Galicia (PDF aranceles comercios) =====
    {
        "proveedor": "Banco Galicia",
        "medio": "Visa/Cabal/Master/Amex — débito",
        "arancel_pct": 0.8,
        "iva_sobre_arancel": False,
        "dias_habiles": 1,
        "oficial": True,
        "nota": (
            "PDF oficial Galicia 'Aranceles y fechas de pago': Débito 0,8% · 1 día hábil. "
            "(El PDF no detalla '+IVA' en esa celda; confirmá en tu contrato.)"
        ),
        "fuente": "https://www.galicia.ar/content/dam/galicia/banco-galicia/empresas/comercios/html/comercios-aranceles-fechas-pago.pdf",
    },
    {
        "proveedor": "Banco Galicia",
        "medio": "Visa/Cabal/Master/Amex — crédito 1 pago",
        "arancel_pct": 1.8,
        "iva_sobre_arancel": False,
        "dias_habiles": 8,
        "oficial": True,
        "nota": (
            "PDF oficial Galicia: Crédito 1,8%. Días 8, 10 ó 18 hábiles según Com. A 7305: "
            "8 DH personas humanas/micro/pequeñas; 10 DH medianas y salud/alojamiento/"
            "gastronomía/turismo; resto 18 DH."
        ),
        "fuente": "https://www.galicia.ar/content/dam/galicia/banco-galicia/empresas/comercios/html/comercios-aranceles-fechas-pago.pdf",
    },
    {
        "proveedor": "Banco Galicia",
        "medio": "Adelanto de cupones (TC 1 pago)",
        "arancel_pct": 0.0,
        "tna_adelanto_pct": 42.0,
        "iva_sobre_arancel": False,
        "dias_habiles": 2,
        "oficial": True,
        "nota": (
            "PDF oficial Galicia: los cobros TC 1 pago Visa/Master/Cabal/Amex y Planes Ahora "
            "tienen 'costo adicional de TNA 42%' por servicio Adelanto de Cupones "
            "(se puede dar de baja). Producto web: cobro en ~48 hs hábiles."
        ),
        "fuente": "https://www.galicia.ar/content/dam/galicia/banco-galicia/empresas/comercios/html/comercios-aranceles-fechas-pago.pdf",
    },
]


def costo_arancel(monto_bruto: float, arancel_pct: float, con_iva: bool = True) -> float:
    base = monto_bruto * (arancel_pct / 100.0)
    return round(base * 1.21, 2) if con_iva else round(base, 2)


def costo_adelanto_tna(monto_bruto: float, tna_pct: float, dias: int) -> float:
    if dias < 1:
        dias = 1
    return round(monto_bruto * (tna_pct / 100.0) * (dias / 365.0), 2)


def filas_mercado_para_monto(monto_bruto: float) -> list[dict[str, Any]]:
    filas = []
    for r in MARKET_RATES:
        if r.get("tna_adelanto_pct"):
            dias_std = 8
            dias_adv = int(r.get("dias_habiles") or 2)
            dias_financiados = max(dias_std - dias_adv, 1)
            costo = costo_adelanto_tna(monto_bruto, float(r["tna_adelanto_pct"]), dias_financiados)
            neto = round(monto_bruto - costo, 2)
            arancel_txt = f"TNA {r['tna_adelanto_pct']}%"
        else:
            con_iva = bool(r.get("iva_sobre_arancel", True))
            costo = costo_arancel(monto_bruto, float(r["arancel_pct"]), con_iva)
            neto = round(monto_bruto - costo, 2)
            arancel_txt = (
                f"{r['arancel_pct']}% + IVA"
                if con_iva
                else f"{r['arancel_pct']}%"
            )

        filas.append(
            {
                "Proveedor": r["proveedor"],
                "Medio": r["medio"],
                "Arancel/TNA": arancel_txt,
                "Días": r["dias_habiles"],
                "Costo est. ARS": costo,
                "Neto comercio": neto,
                "Oficial": "Sí" if r.get("oficial") else "No",
                "Nota": r["nota"],
                "Fuente": r["fuente"],
            }
        )
    return filas


def economia_operacion_finan(
    monto_bruto: float,
    comision_pct: float,
    dias_adelanto: int,
    *,
    firmantes: int = 2,
    costo_firma_ars: float = SIGNATURA_COSTO_FIRMA_ARS,
    buffer_riesgo_pct: float = 0.0,
    costo_capital_tna_pct: float = 0.0,
) -> dict[str, Any]:
    ingreso = round(monto_bruto * (comision_pct / 100.0), 2)
    gasto_signatura = round(max(firmantes, 1) * costo_firma_ars, 2)
    gasto_riesgo = round(monto_bruto * (buffer_riesgo_pct / 100.0), 2)
    gasto_capital = (
        costo_adelanto_tna(monto_bruto - ingreso, costo_capital_tna_pct, dias_adelanto)
        if costo_capital_tna_pct > 0
        else 0.0
    )
    gastos = round(gasto_signatura + gasto_riesgo + gasto_capital, 2)
    neto = round(ingreso - gastos, 2)
    margen_pct = round((neto / monto_bruto) * 100, 4) if monto_bruto else 0.0

    return {
        "monto_bruto": round(monto_bruto, 2),
        "comision_pct": comision_pct,
        "ingreso_comision": ingreso,
        "gasto_signatura": gasto_signatura,
        "gasto_riesgo": gasto_riesgo,
        "gasto_capital": gasto_capital,
        "gastos_totales": gastos,
        "neto_finan": neto,
        "margen_sobre_bruto_pct": margen_pct,
        "dias_adelanto": dias_adelanto,
        "firmantes": firmantes,
    }


def add_business_days(start: date, n: int) -> date:
    """Suma n días hábiles (lun–vie), sin feriados."""
    d = start
    added = 0
    step = 1 if n >= 0 else -1
    target = abs(n)
    while added < target:
        d += timedelta(days=step)
        if d.weekday() < 5:
            added += 1
    return d


def piso_comision_break_even(
    monto_bruto: float,
    *,
    firmantes: int = 2,
    buffer_riesgo_pct: float = 0.3,
    costo_firma_ars: float = SIGNATURA_COSTO_FIRMA_ARS,
) -> float:
    """% mínimo para no perder (Signatura + buffer)."""
    if monto_bruto <= 0:
        return 0.0
    fijo = max(firmantes, 1) * costo_firma_ars + monto_bruto * (buffer_riesgo_pct / 100.0)
    return round(100.0 * fijo / monto_bruto, 2)


def sugerir_comision(
    monto_bruto: float,
    dias_habiles: int,
    *,
    firmantes: int = 2,
    buffer_riesgo_pct: float = 0.3,
) -> dict[str, Any]:
    """
    Comisión sugerida según ticket + plazo BCRA (8 / 10 / 18).

    Prioriza caja rápida: más días => más %.
    Siempre respeta el piso de break-even.
    """
    piso = piso_comision_break_even(
        monto_bruto, firmantes=firmantes, buffer_riesgo_pct=buffer_riesgo_pct
    )

    # Base por ticket (punto medio de la guía comercial)
    if monto_bruto < 150_000:
        base = 5.0
    elif monto_bruto < 400_000:
        base = 3.25
    elif monto_bruto < 800_000:
        base = 2.75
    else:
        base = 2.5

    # Extra por días de caja trabada
    if dias_habiles <= 8:
        extra = 0.0
        etiqueta = "8 días hábiles · caja más rápida"
    elif dias_habiles <= 10:
        extra = 0.5
        etiqueta = "10 días hábiles · caja media"
    else:
        extra = 1.0
        etiqueta = "18 días hábiles · caja más lenta"

    sugerida = round(base + extra, 2)
    if sugerida < piso:
        sugerida = piso
    # Tope útil vs inmediata mercado (~7–8%)
    if sugerida > 6.5:
        sugerida = 6.5

    return {
        "comision_sugerida_pct": sugerida,
        "piso_pct": piso,
        "dias_habiles": dias_habiles,
        "etiqueta_caja": etiqueta,
        "base_pct": base,
        "extra_dias_pct": extra,
    }
