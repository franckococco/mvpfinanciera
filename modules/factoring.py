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
from modules.market_rates import (
    ACTUALIZADO,
    add_business_days,
    economia_operacion_finan,
    filas_mercado_para_monto,
    sugerir_comision,
)
from modules.traceability import crear_operacion
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
        email_firmante = st.text_input(
            "Email firmante comercio (Signatura)",
            placeholder="comercio@mail.com",
            key="fac_email",
        )
        telefono_firmante = st.text_input(
            "Teléfono firmante",
            placeholder="+54911...",
            key="fac_tel",
        )
        email_fiador = st.text_input("Email fiador (opcional)", key="fac_email_f")
        cuit_fiador = st.text_input("CUIT/CUIL fiador (opcional)", key="fac_cuit_f")

        monto_bruto = st.number_input(
            "Monto total del cupón (ARS) *",
            min_value=0.0,
            value=300_000.0,
            step=5_000.0,
            format="%.2f",
            key="fac_monto",
        )

        st.markdown("##### Plazo de cobro del cupón (caja)")
        plazo_label = st.radio(
            "¿En cuántos días hábiles vuelve la plata? (BCRA)",
            options=[
                "8 · micro/pyme (caja rápida)",
                "10 · mediana / gastronomía-salud-turismo",
                "18 · grandes comercios (caja lenta)",
            ],
            index=0,
            key="fac_plazo_bcra",
        )
        plazo_dias = int(plazo_label.split("·")[0].strip())

        fecha_operacion = st.date_input(
            "Fecha de la operación",
            value=date.today(),
            key="fac_fecha_op",
        )
        fecha_liquidacion = add_business_days(fecha_operacion, plazo_dias)
        st.caption(
            f"Liquidación estimada: **{fecha_liquidacion.isoformat()}** "
            f"({plazo_dias} días hábiles, sin feriados)."
        )
        override_fecha = st.checkbox("Usar fecha de liquidación manual", key="fac_fecha_manual")
        if override_fecha:
            fecha_liquidacion = st.date_input(
                "Fecha de liquidación *",
                value=fecha_liquidacion,
                key="fac_fecha_liq",
            )

        st.markdown("##### Costos de la operación (vos / Finan)")
        firmantes = st.number_input(
            "Firmantes Signatura",
            min_value=1,
            max_value=4,
            value=2 if (email_fiador.strip() or cuit_fiador.strip()) else 1,
            key="fac_firmantes",
            help="Flex: ~$1.700 ARS por firma simple (crédito).",
        )
        buffer_riesgo = st.number_input(
            "Buffer riesgo (%)",
            min_value=0.0,
            max_value=5.0,
            value=0.3,
            step=0.1,
            key="fac_riesgo",
            help="Reserva sobre el bruto por contracargos / fallas.",
        )
        tna_capital = st.number_input(
            "Tu costo de capital TNA (%)",
            min_value=0.0,
            max_value=120.0,
            value=0.0,
            step=1.0,
            key="fac_tna_cap",
            help="Si financiás con plata cara, cargá tu TNA. 0 = no descontar.",
        )

        sug = sugerir_comision(
            monto_bruto,
            plazo_dias,
            firmantes=int(firmantes),
            buffer_riesgo_pct=float(buffer_riesgo),
        )
        st.info(
            f"**Comisión sugerida: {sug['comision_sugerida_pct']}%** · "
            f"{sug['etiqueta_caja']} · piso break-even {sug['piso_pct']}%"
        )
        if st.button("Usar comisión sugerida", key="fac_usar_sug"):
            st.session_state["fac_tasa"] = float(sug["comision_sugerida_pct"])
            st.rerun()

        if "fac_tasa" not in st.session_state:
            st.session_state["fac_tasa"] = float(sug["comision_sugerida_pct"])

        tasa_comision = st.slider(
            "Tasa de comisión (%) *",
            min_value=0.0,
            max_value=20.0,
            step=0.1,
            help="Porcentaje descontado sobre el monto bruto del cupón.",
            key="fac_tasa",
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
            economia = economia_operacion_finan(
                resultado["monto_bruto"],
                resultado["tasa_comision"],
                resultado["dias_adelanto"],
                firmantes=int(firmantes),
                buffer_riesgo_pct=float(buffer_riesgo),
                costo_capital_tna_pct=float(tna_capital),
            )
            econ_sug = economia_operacion_finan(
                resultado["monto_bruto"],
                sug["comision_sugerida_pct"],
                resultado["dias_adelanto"],
                firmantes=int(firmantes),
                buffer_riesgo_pct=float(buffer_riesgo),
                costo_capital_tna_pct=float(tna_capital),
            )

            st.markdown("##### Proyección de caja")
            result_strip(
                [
                    ("Días hábiles", f"{plazo_dias}"),
                    ("Días corridos", f"{resultado['dias_adelanto']}"),
                    ("Vuelve", fecha_liquidacion.isoformat()),
                ]
            )
            kpi_card(
                "Comisión sugerida",
                f"{sug['comision_sugerida_pct']}%",
                f"Neto Finan est. {fmt_ars(econ_sug['neto_finan'])}",
            )
            kpi_card("Neto a transferir", fmt_ars(resultado["monto_neto"]), "Al comercio (hoy)")
            kpi_card(
                "Tu comisión (slider)",
                fmt_ars(resultado["ganancia"]),
                f"{resultado['tasa_comision']:.1f}%",
            )
            result_strip(
                [
                    ("TNA", f"{resultado['tna']:.2f}%"),
                    ("TEA", f"{resultado['tea']:.2f}%"),
                    ("Piso", f"{sug['piso_pct']}%"),
                ]
            )

            st.markdown("##### ¿Cuánto te queda?")
            kpi_card(
                "Neto Finan",
                fmt_ars(economia["neto_finan"]),
                f"Margen {economia['margen_sobre_bruto_pct']:.2f}% s/ bruto",
            )
            result_strip(
                [
                    ("+ Comisión", fmt_ars(economia["ingreso_comision"])),
                    ("− Signatura", fmt_ars(economia["gasto_signatura"])),
                    ("− Riesgo", fmt_ars(economia["gasto_riesgo"])),
                    ("− Capital", fmt_ars(economia["gasto_capital"])),
                ]
            )
            if economia["neto_finan"] <= 0:
                st.error("Con estos números la operación te deja en cero o negativo.")
            elif economia["neto_finan"] < economia["gasto_signatura"]:
                st.warning("El neto apenas cubre (o poco más) el costo de firma.")

            fig = px.pie(
                names=["Neto comercio", "Comisión"],
                values=[resultado["monto_neto"], resultado["ganancia"]],
                hole=0.55,
                color_discrete_sequence=["#38bdf8", "#fbbf24"],
            )
            plotly_layout(fig, "Composición del cupón")
            fig.update_traces(textinfo="percent+label", textfont_size=11)
            st.plotly_chart(fig, use_container_width=True)

            fig_g = px.bar(
                x=["Comisión", "Signatura", "Riesgo", "Capital", "Neto Finan"],
                y=[
                    economia["ingreso_comision"],
                    -economia["gasto_signatura"],
                    -economia["gasto_riesgo"],
                    -economia["gasto_capital"],
                    economia["neto_finan"],
                ],
                labels={"x": "", "y": "ARS"},
                color_discrete_sequence=["#22c55e"],
            )
            plotly_layout(fig_g, "Ingreso vs gastos")
            st.plotly_chart(fig_g, use_container_width=True)

    if calc_ok and resultado is not None:
        with st.expander(
            f"Mercado oficial: Payway / Fiserv / Getnet / Mercado Pago / Galicia (act. {ACTUALIZADO})",
            expanded=False,
        ):
            st.caption(
                "Números tomados de páginas/PDF oficiales. "
                "Donde dice 'Hasta' es el techo publicado (tu comercio puede pagar menos). "
                "MP aclara que pueden variar impuestos provinciales. "
                "La columna Nota cita la condición real de la fuente."
            )
            df_m = pd.DataFrame(filas_mercado_para_monto(resultado["monto_bruto"]))
            st.dataframe(
                df_m,
                use_container_width=True,
                hide_index=True,
                column_config={
                    "Costo est. ARS": st.column_config.NumberColumn(format="$ %.2f"),
                    "Neto comercio": st.column_config.NumberColumn(format="$ %.2f"),
                    "Fuente": st.column_config.LinkColumn("Fuente"),
                    "Nota": st.column_config.TextColumn("Nota", width="large"),
                },
            )

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
        econ = economia_operacion_finan(
            resultado["monto_bruto"],
            resultado["tasa_comision"],
            resultado["dias_adelanto"],
            firmantes=int(firmantes),
            buffer_riesgo_pct=float(buffer_riesgo),
            costo_capital_tna_pct=float(tna_capital),
        )
        exp_id = crear_operacion(
            "factoring",
            registro["comercio"],
            registro["monto_bruto"],
            cuit=registro.get("cuit", ""),
            email_firmante=email_firmante.strip(),
            telefono_firmante=telefono_firmante.strip(),
            email_fiador=email_fiador.strip(),
            cuit_fiador=cuit_fiador.strip(),
            ref_tabla="factoring_ops",
            ref_id=op_id,
            payload={
                "monto_neto": registro["monto_neto"],
                "ganancia": registro["ganancia"],
                "tasa_comision": registro["tasa_comision"],
                "fecha_liquidacion": registro["fecha_liquidacion"],
                "tna": registro["tna"],
                "tea": registro["tea"],
                "plazo_habiles_bcra": plazo_dias,
                "comision_sugerida_pct": sug["comision_sugerida_pct"],
                "economia_finan": econ,
            },
        )
        st.success(
            f"Operación #{op_id} · expediente #{exp_id} · "
            f"plazo {plazo_dias} DH · "
            f"neto comercio {fmt_ars(resultado['monto_neto'])} · "
            f"neto Finan est. {fmt_ars(econ['neto_finan'])}. "
            "Firmá desde **Trazabilidad**."
        )
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
