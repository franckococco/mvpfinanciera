"""
Módulo A — Adelanto de Cupones de Tarjeta (Factoring).

Calculadora en vivo, registro de operaciones, historial filtrable
y gestión rápida de estados (activa / cobrada).
"""

from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import Any

import pandas as pd
import plotly.express as px
import streamlit as st

from modules.database import (
    insert_factoring_op,
    list_factoring_ops,
    update_factoring_estado,
)
from modules.ui import badge_estado, fmt_ars, kpi_card, plotly_layout, result_strip


def calcular_factoring(
    monto_bruto: float,
    tasa_comision_pct: float,
    fecha_liquidacion: date,
    fecha_operacion: date | None = None,
) -> dict[str, Any]:
    """
    Calcula los indicadores de una operación de adelanto de cupón.

    Fórmulas:
      - Comisión (ganancia) = monto_bruto * (tasa_comision_pct / 100)
      - Monto neto          = monto_bruto - comisión
      - Días de adelanto    = max(fecha_liquidacion - fecha_operacion, 1)
      - TNA                 = (tasa_comision / días) * 365 * 100   [%]
      - TEA                 = ((1 + tasa_comision)^(365/días) - 1) * 100  [%]
    """
    if monto_bruto <= 0:
        raise ValueError("El monto bruto debe ser mayor a cero.")
    if tasa_comision_pct < 0:
        raise ValueError("La tasa de comisión no puede ser negativa.")

    fecha_op = fecha_operacion or date.today()
    dias = (fecha_liquidacion - fecha_op).days
    if dias < 1:
        dias = 1

    tasa_decimal = tasa_comision_pct / 100.0
    ganancia = round(monto_bruto * tasa_decimal, 2)
    monto_neto = round(monto_bruto - ganancia, 2)
    tna = (tasa_decimal / dias) * 365 * 100
    tea = ((1 + tasa_decimal) ** (365 / dias) - 1) * 100

    return {
        "monto_bruto": round(monto_bruto, 2),
        "tasa_comision": round(tasa_comision_pct, 4),
        "ganancia": ganancia,
        "monto_neto": monto_neto,
        "dias_adelanto": dias,
        "tna": round(tna, 4),
        "tea": round(tea, 4),
        "fecha_liquidacion": fecha_liquidacion.isoformat(),
        "fecha_operacion": fecha_op.isoformat(),
    }


def _render_simulador() -> None:
    """Panel interactivo: los cálculos se actualizan al mover los controles."""
    st.subheader("Nueva operación")
    st.caption("Mové los controles y mirá el resultado al instante. Registrá cuando esté listo.")

    left, right = st.columns([1.15, 1], gap="large")

    with left:
        comercio = st.text_input(
            "Nombre del comercio *",
            placeholder="Ej: Mercado Central SRL",
            key="fac_comercio",
        )
        cuit = st.text_input(
            "CUIT (opcional)",
            placeholder="XX-XXXXXXXX-X",
            key="fac_cuit",
        )

        monto_bruto = st.number_input(
            "Monto total del cupón (ARS) *",
            min_value=0.0,
            value=100_000.0,
            step=5_000.0,
            format="%.2f",
            key="fac_monto",
        )
        # Slider rápido + ajuste fino
        tasa_comision = st.slider(
            "Tasa de comisión (%) *",
            min_value=0.0,
            max_value=20.0,
            value=5.0,
            step=0.1,
            help="Porcentaje descontado sobre el monto bruto del cupón.",
            key="fac_tasa",
        )

        c1, c2 = st.columns(2)
        with c1:
            fecha_operacion = st.date_input(
                "Fecha de la operación",
                value=date.today(),
                key="fac_fecha_op",
            )
        with c2:
            fecha_liquidacion = st.date_input(
                "Fecha de liquidación *",
                value=date.today() + timedelta(days=21),
                help="Fecha en que el adquirente liquidaría el cupón.",
                key="fac_fecha_liq",
            )

    # Preview en vivo (siempre visible)
    try:
        resultado = calcular_factoring(
            monto_bruto=monto_bruto,
            tasa_comision_pct=tasa_comision,
            fecha_liquidacion=fecha_liquidacion,
            fecha_operacion=fecha_operacion,
        )
        calc_ok = True
        calc_error = ""
    except ValueError as exc:
        resultado = None
        calc_ok = False
        calc_error = str(exc)

    with right:
        st.markdown("##### Preview en vivo")
        if not calc_ok or resultado is None:
            st.warning(calc_error or "Ajustá los parámetros.")
        else:
            kpi_card("Neto a transferir", fmt_ars(resultado["monto_neto"]), "Al comercio")
            kpi_card("Ganancia financiera", fmt_ars(resultado["ganancia"]), f"Comisión {resultado['tasa_comision']:.1f}%")
            result_strip(
                [
                    ("Días adelanto", f"{resultado['dias_adelanto']}"),
                    ("TNA", f"{resultado['tna']:.2f}%"),
                    ("TEA", f"{resultado['tea']:.2f}%"),
                ]
            )

            # Mini gráfico: composición bruto = neto + comisión
            fig = px.pie(
                names=["Neto comercio", "Comisión"],
                values=[resultado["monto_neto"], resultado["ganancia"]],
                hole=0.55,
                color_discrete_sequence=["#38bdf8", "#fbbf24"],
            )
            plotly_layout(fig, "Composición del cupón")
            fig.update_traces(textinfo="percent+label", textfont_size=11)
            st.plotly_chart(fig, use_container_width=True)

    st.divider()
    col_btn, col_msg = st.columns([1, 2])
    with col_btn:
        registrar = st.button(
            "Registrar operación",
            type="primary",
            use_container_width=True,
            disabled=not calc_ok,
            key="fac_registrar",
        )

    if registrar:
        if not comercio.strip():
            st.error("El nombre del comercio es obligatorio.")
            return
        if resultado is None:
            st.error("No hay un cálculo válido para registrar.")
            return

        registro = {
            "comercio": comercio.strip(),
            "cuit": cuit.strip(),
            "monto_bruto": resultado["monto_bruto"],
            "tasa_comision": resultado["tasa_comision"],
            "fecha_liquidacion": resultado["fecha_liquidacion"],
            "monto_neto": resultado["monto_neto"],
            "ganancia": resultado["ganancia"],
            "tna": resultado["tna"],
            "tea": resultado["tea"],
            "dias_adelanto": resultado["dias_adelanto"],
            "estado": "activa",
            "creado_en": datetime.now().isoformat(timespec="seconds"),
        }
        op_id = insert_factoring_op(registro)
        st.success(f"Operación #{op_id} registrada · {registro['comercio']} · {fmt_ars(resultado['monto_neto'])} neto")
        st.balloons()


def _render_historial() -> None:
    """Tabla interactiva de operaciones + acciones de estado."""
    st.subheader("Historial de operaciones")

    filtro = st.segmented_control(
        "Estado",
        options=["Todas", "Activas", "Cobradas"],
        default="Todas",
        key="fac_filtro_estado",
    )
    estado_map = {"Todas": None, "Activas": "activa", "Cobradas": "cobrada"}
    ops = list_factoring_ops(estado=estado_map[filtro])

    if not ops:
        st.info("No hay operaciones con ese filtro. Registrá una en la pestaña Simular.")
        return

    df = pd.DataFrame(ops)
    df_view = df[
        [
            "id",
            "comercio",
            "monto_bruto",
            "ganancia",
            "monto_neto",
            "tasa_comision",
            "tna",
            "tea",
            "fecha_liquidacion",
            "dias_adelanto",
            "estado",
        ]
    ].rename(
        columns={
            "id": "ID",
            "comercio": "Comercio",
            "monto_bruto": "Bruto",
            "ganancia": "Comisión",
            "monto_neto": "Neto",
            "tasa_comision": "Tasa %",
            "tna": "TNA %",
            "tea": "TEA %",
            "fecha_liquidacion": "Liquidación",
            "dias_adelanto": "Días",
            "estado": "Estado",
        }
    )

    st.dataframe(
        df_view,
        use_container_width=True,
        hide_index=True,
        column_config={
            "Bruto": st.column_config.NumberColumn(format="$ %.2f"),
            "Comisión": st.column_config.NumberColumn(format="$ %.2f"),
            "Neto": st.column_config.NumberColumn(format="$ %.2f"),
            "Tasa %": st.column_config.NumberColumn(format="%.2f"),
            "TNA %": st.column_config.NumberColumn(format="%.2f"),
            "TEA %": st.column_config.NumberColumn(format="%.2f"),
        },
    )

    # Resumen rápido
    activas = [o for o in ops if o["estado"] == "activa"]
    c1, c2, c3 = st.columns(3)
    c1.metric("Operaciones listadas", len(ops))
    c2.metric("Bruto activo", fmt_ars(sum(o["monto_bruto"] for o in activas)))
    c3.metric("Comisiones (lista)", fmt_ars(sum(o["ganancia"] for o in ops)))

    st.markdown("##### Gestión rápida")
    activas_opts = {f"#{o['id']} · {o['comercio']} · {fmt_ars(o['monto_bruto'])}": o["id"] for o in activas}
    if activas_opts:
        seleccion = st.selectbox("Marcar como cobrada", options=list(activas_opts.keys()))
        if st.button("Confirmar cobro", type="primary", key="fac_cobrar"):
            update_factoring_estado(activas_opts[seleccion], "cobrada")
            st.success("Operación marcada como cobrada.")
            st.rerun()
    else:
        st.caption("No hay operaciones activas para cobrar.")

    # Badge preview de la última
    ultima = ops[0]
    st.markdown(
        f"Última operación: **#{ultima['id']}** {ultima['comercio']} "
        f"{badge_estado(ultima['estado'])}",
        unsafe_allow_html=True,
    )


def render_factoring() -> None:
    """Vista principal del módulo Factoring con pestañas interactivas."""
    st.header("Adelanto de Cupones")
    st.caption("Factoring de cupones de tarjeta · calculadora en vivo · gestión de cartera")

    tab_sim, tab_hist = st.tabs(["Simular & Registrar", "Historial & Cobros"])
    with tab_sim:
        _render_simulador()
    with tab_hist:
        _render_historial()
