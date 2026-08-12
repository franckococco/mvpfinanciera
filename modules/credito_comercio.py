"""
Crédito directo al comercio (no BNPL consumidor).

Alta en el expediente unificado `operaciones` (tipo credito_comercio).
"""

from __future__ import annotations

from datetime import date

import streamlit as st

from modules.traceability import TIPOS, crear_operacion
from modules.ui import fmt_ars, kpi_card


def render_credito_comercio() -> None:
    st.header("Crédito al comercio")
    st.caption("Préstamo / línea al local · entra al mismo expediente de trazabilidad y firma Signatura")

    c1, c2 = st.columns(2)
    with c1:
        comercio = st.text_input("Comercio *", key="cc_comercio")
        cuit = st.text_input("CUIT comercio", key="cc_cuit")
        monto = st.number_input(
            "Monto a desembolsar (ARS) *",
            min_value=0.0,
            value=500_000.0,
            step=10_000.0,
            format="%.2f",
            key="cc_monto",
        )
        tasa = st.number_input(
            "Tasa interés mensual (%)",
            min_value=0.0,
            value=4.0,
            step=0.1,
            key="cc_tasa",
        )
        cuotas = st.number_input("Cuotas", min_value=1, value=6, step=1, key="cc_cuotas")
    with c2:
        email = st.text_input("Email firmante comercio *", key="cc_email")
        telefono = st.text_input("Teléfono comercio", key="cc_tel")
        email_fiador = st.text_input("Email fiador", key="cc_email_f")
        tel_fiador = st.text_input("Teléfono fiador", key="cc_tel_f")
        cuit_fiador = st.text_input("CUIT/CUIL fiador", key="cc_cuit_f")
        destino = st.text_input("CBU/CVU destino", key="cc_cbu")
        venc = st.date_input("Primera cuota", value=date.today(), key="cc_venc")

    if monto > 0 and cuotas >= 1:
        # Cuota simple (sistema francés se puede alinear después con BNPL)
        i = tasa / 100.0
        if i == 0:
            cuota = round(monto / cuotas, 2)
        else:
            f = (1 + i) ** int(cuotas)
            cuota = round(monto * (i * f) / (f - 1), 2)
        total = round(cuota * int(cuotas), 2)
        kpi_card("Cuota estimada", fmt_ars(cuota), f"{int(cuotas)} cuotas")
        kpi_card("Total estimado", fmt_ars(total), f"Interés ~ {fmt_ars(total - monto)}")

    if st.button("Crear expediente (borrador)", type="primary", key="cc_crear"):
        if not comercio.strip():
            st.error("Comercio obligatorio.")
            return
        if not email.strip():
            st.error("Email del firmante obligatorio (Signatura).")
            return
        if monto <= 0:
            st.error("Monto inválido.")
            return

        op_id = crear_operacion(
            "credito_comercio",
            comercio.strip(),
            float(monto),
            cuit=cuit.strip(),
            email_firmante=email.strip(),
            telefono_firmante=telefono.strip(),
            email_fiador=email_fiador.strip(),
            telefono_fiador=tel_fiador.strip(),
            cuit_fiador=cuit_fiador.strip(),
            payload={
                "tasa_mensual": tasa,
                "cuotas": int(cuotas),
                "cbu": destino.strip(),
                "primera_cuota": venc.isoformat(),
                "producto": TIPOS["credito_comercio"],
            },
        )
        st.success(
            f"Expediente #{op_id} creado en borrador. "
            "Andá a **Trazabilidad** para generar PDF y enviar a Signatura."
        )
