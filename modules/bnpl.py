"""
Módulo B — Créditos BNPL (Buy Now, Pay Later / Consumo en comercios).

Simulación en vivo con sistema francés, cronograma interactivo,
pagaré digital para WhatsApp y gestión de cobro de cuotas.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Any
from urllib.parse import quote

import pandas as pd
import plotly.express as px
import streamlit as st

from modules.database import (
    get_bnpl_credit,
    get_bnpl_progress,
    insert_bnpl_credit,
    list_bnpl_credits,
    list_bnpl_installments,
    update_installment_estado,
)
from modules.ui import badge_estado, fmt_ars, kpi_card, plotly_layout, result_strip


def calcular_cuota_fija(monto: float, tasa_mensual_pct: float, n_cuotas: int) -> float:
    """
    Calcula la cuota fija del sistema francés.

    cuota = monto * (i * (1+i)^n) / ((1+i)^n - 1)
    Si la tasa es 0, la cuota es monto / n.
    """
    if monto <= 0 or n_cuotas < 1:
        raise ValueError("Monto y cantidad de cuotas deben ser válidos.")

    i = tasa_mensual_pct / 100.0
    if i == 0:
        return round(monto / n_cuotas, 2)

    factor = (1 + i) ** n_cuotas
    cuota = monto * (i * factor) / (factor - 1)
    return round(cuota, 2)


def generar_cronograma(
    monto: float,
    tasa_mensual_pct: float,
    n_cuotas: int,
    fecha_inicio: date | None = None,
) -> tuple[float, list[dict[str, Any]]]:
    """Genera el cronograma de cuotas (sistema francés)."""
    cuota = calcular_cuota_fija(monto, tasa_mensual_pct, n_cuotas)
    i = tasa_mensual_pct / 100.0
    saldo = monto
    inicio = fecha_inicio or date.today()
    filas: list[dict[str, Any]] = []

    for n in range(1, n_cuotas + 1):
        interes = round(saldo * i, 2)
        capital = round(cuota - interes, 2)

        if n == n_cuotas:
            capital = round(saldo, 2)
            cuota_final = round(capital + interes, 2)
            saldo_restante = 0.0
            cuota_fila = cuota_final
        else:
            saldo = round(saldo - capital, 2)
            saldo_restante = saldo
            cuota_fila = cuota

        mes = inicio.month + n
        anio = inicio.year + (mes - 1) // 12
        mes = ((mes - 1) % 12) + 1
        dia = min(inicio.day, _dias_en_mes(anio, mes))
        fecha_venc = date(anio, mes, dia)

        filas.append(
            {
                "nro_cuota": n,
                "fecha_vencimiento": fecha_venc.isoformat(),
                "capital": capital,
                "interes": interes,
                "cuota_total": cuota_fila,
                "saldo_restante": saldo_restante,
                "estado": "pendiente",
            }
        )

    return cuota, filas


def _dias_en_mes(anio: int, mes: int) -> int:
    """Devuelve la cantidad de días del mes indicado."""
    if mes == 12:
        siguiente = date(anio + 1, 1, 1)
    else:
        siguiente = date(anio, mes + 1, 1)
    actual = date(anio, mes, 1)
    return (siguiente - actual).days


def generar_pagare_whatsapp(
    dni: str,
    nombre: str,
    comercio: str,
    monto: float,
    n_cuotas: int,
    cuota: float,
    tasa_mensual: float,
    total_a_pagar: float,
    cronograma: list[dict[str, Any]],
) -> str:
    """Genera el texto plano de un Pagaré Digital para WhatsApp."""
    nombre_mostrar = nombre.strip() if nombre.strip() else "Cliente"
    primera = cronograma[0]["fecha_vencimiento"] if cronograma else "—"
    ultima = cronograma[-1]["fecha_vencimiento"] if cronograma else "—"

    lineas_cuotas = "\n".join(
        f"  • Cuota {f['nro_cuota']:02d}: {fmt_ars(f['cuota_total'])} — vence {f['fecha_vencimiento']}"
        for f in cronograma
    )

    texto = f"""📄 *PAGARÉ DIGITAL — COMPRA EN CUOTAS (BNPL)*

Yo, *{nombre_mostrar}*, DNI *{dni}*, declaro deber y me comprometo a pagar a la orden de la Financiera la suma de *{fmt_ars(total_a_pagar)}*, en concepto de la compra realizada en *{comercio}* por un valor de producto de {fmt_ars(monto)}.

*Condiciones del crédito:*
• Monto del producto: {fmt_ars(monto)}
• Cantidad de cuotas: {n_cuotas}
• Cuota mensual: {fmt_ars(cuota)}
• Tasa de interés mensual: {tasa_mensual:.2f}%
• Total a pagar: {fmt_ars(total_a_pagar)}
• Primera cuota: {primera}
• Última cuota: {ultima}

*Cronograma de vencimientos:*
{lineas_cuotas}

Al aceptar este mensaje, reconozco la deuda y autorizo el débito/cobro de las cuotas en las fechas indicadas.

Fecha de emisión: {date.today().isoformat()}
— Financiera · Pagaré Digital BNPL —
"""
    return texto.strip()


def _render_simulador() -> None:
    """Simulación en vivo: sliders + preview + cronograma + pagaré."""
    st.subheader("Simular crédito")
    st.caption("Ajustá monto, cuotas y tasa: el cronograma se recalcula al instante.")

    left, right = st.columns([1.1, 1], gap="large")

    with left:
        dni = st.text_input("DNI del cliente *", placeholder="12345678", key="bnpl_dni")
        nombre = st.text_input("Nombre del cliente", placeholder="Juan Pérez", key="bnpl_nombre")
        comercio = st.text_input("Comercio *", placeholder="Ej: Electro Hogar SA", key="bnpl_comercio")

        monto = st.number_input(
            "Monto del producto (ARS) *",
            min_value=0.0,
            value=150_000.0,
            step=5_000.0,
            format="%.2f",
            key="bnpl_monto",
        )
        n_cuotas = st.slider("Cantidad de cuotas *", 1, 24, 6, key="bnpl_cuotas")
        tasa_mensual = st.slider(
            "Tasa de interés mensual (%) *",
            min_value=0.0,
            max_value=15.0,
            value=4.5,
            step=0.1,
            help="Sistema francés: interés sobre saldo remanente.",
            key="bnpl_tasa",
        )
        fecha_inicio = st.date_input(
            "Fecha de inicio",
            value=date.today(),
            key="bnpl_fecha",
        )

    try:
        cuota, cronograma = generar_cronograma(
            monto=monto,
            tasa_mensual_pct=tasa_mensual,
            n_cuotas=int(n_cuotas),
            fecha_inicio=fecha_inicio,
        )
        total_a_pagar = round(sum(f["cuota_total"] for f in cronograma), 2)
        interes_total = round(total_a_pagar - monto, 2)
        calc_ok = monto > 0
    except ValueError as exc:
        cuota, cronograma = 0.0, []
        total_a_pagar = interes_total = 0.0
        calc_ok = False
        st.error(str(exc))

    with right:
        st.markdown("##### Preview en vivo")
        if calc_ok:
            kpi_card("Cuota mensual", fmt_ars(cuota), f"{n_cuotas} cuotas")
            kpi_card("Total a pagar", fmt_ars(total_a_pagar), f"Interés {fmt_ars(interes_total)}")
            result_strip(
                [
                    ("Capital", fmt_ars(monto)),
                    ("Interés", fmt_ars(interes_total)),
                    ("Tasa mes", f"{tasa_mensual:.1f}%"),
                ]
            )

            fig = px.pie(
                names=["Capital", "Interés"],
                values=[monto, max(interes_total, 0.01)],
                hole=0.55,
                color_discrete_sequence=["#38bdf8", "#f472b6"],
            )
            plotly_layout(fig, "Capital vs Interés")
            fig.update_traces(textinfo="percent+label", textfont_size=11)
            st.plotly_chart(fig, use_container_width=True)

    if calc_ok and cronograma:
        st.markdown("##### Cronograma de vencimientos")
        df = pd.DataFrame(cronograma)
        fig_bar = px.bar(
            df,
            x="nro_cuota",
            y=["capital", "interes"],
            labels={"nro_cuota": "Cuota", "value": "ARS", "variable": "Concepto"},
            color_discrete_map={"capital": "#38bdf8", "interes": "#f472b6"},
            barmode="stack",
        )
        plotly_layout(fig_bar, "Composición por cuota")
        st.plotly_chart(fig_bar, use_container_width=True)

        st.dataframe(
            df.rename(
                columns={
                    "nro_cuota": "Nº",
                    "fecha_vencimiento": "Vencimiento",
                    "capital": "Capital",
                    "interes": "Interés",
                    "cuota_total": "Cuota",
                    "saldo_restante": "Saldo",
                    "estado": "Estado",
                }
            ),
            use_container_width=True,
            hide_index=True,
            column_config={
                "Capital": st.column_config.NumberColumn(format="$ %.2f"),
                "Interés": st.column_config.NumberColumn(format="$ %.2f"),
                "Cuota": st.column_config.NumberColumn(format="$ %.2f"),
                "Saldo": st.column_config.NumberColumn(format="$ %.2f"),
            },
        )

        pagare = generar_pagare_whatsapp(
            dni=dni.strip() or "00000000",
            nombre=nombre.strip(),
            comercio=comercio.strip() or "Comercio",
            monto=monto,
            n_cuotas=int(n_cuotas),
            cuota=cuota,
            tasa_mensual=tasa_mensual,
            total_a_pagar=total_a_pagar,
            cronograma=cronograma,
        )

        with st.expander("Pagaré Digital (WhatsApp)", expanded=False):
            st.code(pagare, language=None)
            wa_url = f"https://wa.me/?text={quote(pagare)}"
            st.link_button("Abrir en WhatsApp", wa_url, use_container_width=True)
            st.download_button(
                "Descargar pagaré (.txt)",
                data=pagare,
                file_name=f"pagare_bnpl_{dni.strip() or 'cliente'}.txt",
                mime="text/plain",
                use_container_width=True,
            )

        st.divider()
        if st.button("Registrar crédito", type="primary", use_container_width=True, key="bnpl_reg"):
            if not dni.strip():
                st.error("El DNI del cliente es obligatorio.")
            elif not comercio.strip():
                st.error("El nombre del comercio es obligatorio.")
            else:
                credit_data = {
                    "dni_cliente": dni.strip(),
                    "nombre_cliente": nombre.strip(),
                    "comercio": comercio.strip(),
                    "monto_producto": round(monto, 2),
                    "cantidad_cuotas": int(n_cuotas),
                    "tasa_mensual": tasa_mensual,
                    "cuota_mensual": cuota,
                    "total_a_pagar": total_a_pagar,
                    "interes_total": interes_total,
                    "pagare_texto": pagare,
                    "estado": "activa",
                    "creado_en": datetime.now().isoformat(timespec="seconds"),
                }
                credito_id = insert_bnpl_credit(credit_data, cronograma)
                st.success(f"Crédito #{credito_id} registrado · {comercio.strip()} · cuota {fmt_ars(cuota)}")
                st.balloons()


def _render_cartera() -> None:
    """Lista de créditos + cobro interactivo de cuotas."""
    st.subheader("Cartera BNPL")

    filtro = st.segmented_control(
        "Estado",
        options=["Todas", "Activas", "Cerradas"],
        default="Activas",
        key="bnpl_filtro",
    )
    estado_map = {"Todas": None, "Activas": "activa", "Cerradas": "cerrada"}
    credits = list_bnpl_credits(estado=estado_map[filtro])

    if not credits:
        st.info("No hay créditos con ese filtro. Simulá y registrá uno en la otra pestaña.")
        return

    df = pd.DataFrame(credits)[
        [
            "id",
            "dni_cliente",
            "nombre_cliente",
            "comercio",
            "monto_producto",
            "cantidad_cuotas",
            "cuota_mensual",
            "total_a_pagar",
            "tasa_mensual",
            "estado",
        ]
    ].rename(
        columns={
            "id": "ID",
            "dni_cliente": "DNI",
            "nombre_cliente": "Cliente",
            "comercio": "Comercio",
            "monto_producto": "Monto",
            "cantidad_cuotas": "Cuotas",
            "cuota_mensual": "Cuota $",
            "total_a_pagar": "Total",
            "tasa_mensual": "Tasa %",
            "estado": "Estado",
        }
    )
    st.dataframe(
        df,
        use_container_width=True,
        hide_index=True,
        column_config={
            "Monto": st.column_config.NumberColumn(format="$ %.2f"),
            "Cuota $": st.column_config.NumberColumn(format="$ %.2f"),
            "Total": st.column_config.NumberColumn(format="$ %.2f"),
        },
    )

    st.markdown("##### Gestionar cuotas")
    opciones = {
        f"#{c['id']} · {c.get('nombre_cliente') or c['dni_cliente']} · {c['comercio']}": c["id"]
        for c in credits
    }
    label = st.selectbox("Seleccionar crédito", options=list(opciones.keys()), key="bnpl_sel")
    credito_id = opciones[label]
    credit = get_bnpl_credit(credito_id)
    installments = list_bnpl_installments(credito_id)
    progress = get_bnpl_progress(credito_id)

    if credit:
        st.markdown(
            f"**Crédito #{credito_id}** {badge_estado(credit['estado'])} · "
            f"DNI {credit['dni_cliente']} · {fmt_ars(credit['monto_producto'])}",
            unsafe_allow_html=True,
        )

    st.progress(
        min(progress["pct"] / 100.0, 1.0),
        text=f"Cobrado {progress['pagadas']}/{progress['total']} cuotas "
        f"({fmt_ars(progress['cobrado'])} / pendiente {fmt_ars(progress['pendiente'])})",
    )

    df_i = pd.DataFrame(installments)
    st.dataframe(
        df_i.rename(
            columns={
                "id": "ID cuota",
                "nro_cuota": "Nº",
                "fecha_vencimiento": "Vencimiento",
                "capital": "Capital",
                "interes": "Interés",
                "cuota_total": "Cuota",
                "saldo_restante": "Saldo",
                "estado": "Estado",
            }
        )[
            [
                "ID cuota",
                "Nº",
                "Vencimiento",
                "Capital",
                "Interés",
                "Cuota",
                "Saldo",
                "Estado",
            ]
        ],
        use_container_width=True,
        hide_index=True,
        column_config={
            "Capital": st.column_config.NumberColumn(format="$ %.2f"),
            "Interés": st.column_config.NumberColumn(format="$ %.2f"),
            "Cuota": st.column_config.NumberColumn(format="$ %.2f"),
            "Saldo": st.column_config.NumberColumn(format="$ %.2f"),
        },
    )

    pendientes = [i for i in installments if i["estado"] == "pendiente"]
    if pendientes:
        prox = pendientes[0]
        st.write(
            f"Próxima cuota: **#{prox['nro_cuota']}** · {fmt_ars(prox['cuota_total'])} · "
            f"vence {prox['fecha_vencimiento']}"
        )
        b1, b2 = st.columns(2)
        with b1:
            if st.button("Marcar próxima como pagada", type="primary", use_container_width=True):
                update_installment_estado(prox["id"], "pagada")
                st.success(f"Cuota #{prox['nro_cuota']} marcada como pagada.")
                st.rerun()
        with b2:
            if credit and credit.get("pagare_texto"):
                wa = f"https://wa.me/?text={quote(credit['pagare_texto'])}"
                st.link_button("Reenviar pagaré por WhatsApp", wa, use_container_width=True)
    else:
        st.success("Todas las cuotas están pagadas. Crédito cerrado.")


def render_bnpl() -> None:
    """Vista principal del módulo BNPL con pestañas interactivas."""
    st.header("Créditos BNPL")
    st.caption("Consumo en comercios · simulación en vivo · pagaré WhatsApp · cobro de cuotas")

    tab_sim, tab_cart = st.tabs(["Simular & Registrar", "Cartera & Cobros"])
    with tab_sim:
        _render_simulador()
    with tab_cart:
        _render_cartera()
