"""
Finan — Plataforma MVP de Factoring y Créditos BNPL.

Punto de entrada principal (Streamlit). Navegación por sidebar:
  1. Dashboard / Admin
  2. Adelanto de Cupones (Factoring)
  3. Créditos BNPL
"""

from __future__ import annotations

import pandas as pd
import plotly.express as px
import streamlit as st

from modules.bnpl import render_bnpl
from modules.database import get_dashboard_metrics, init_db
from modules.factoring import render_factoring
from modules.ui import fmt_ars, inject_styles, kpi_card, plotly_layout


st.set_page_config(
    page_title="Finan · Factoring & BNPL",
    page_icon="💰",
    layout="wide",
    initial_sidebar_state="expanded",
)


def render_dashboard() -> None:
    """Dashboard gráfico: KPIs, composición de cartera, vencimientos y actividad."""
    st.header("Dashboard")
    st.caption("Cartera activa · ingresos del mes · cupones y cuotas por fecha")

    metrics = get_dashboard_metrics()

    # --- KPI strip ---
    k1, k2, k3, k4 = st.columns(4)
    with k1:
        kpi_card(
            "Cartera activa",
            fmt_ars(metrics["cartera_activa_total"]),
            "Factoring + BNPL pendiente",
        )
    with k2:
        kpi_card(
            "Ingresos del mes",
            fmt_ars(metrics["ingresos_mes"]),
            f"Mes {metrics['mes_referencia']}",
        )
    with k3:
        kpi_card(
            "Factoring activo",
            f"{metrics['ops_factoring_activas']} ops",
            fmt_ars(metrics["cartera_activa_factoring"]),
        )
    with k4:
        kpi_card(
            "BNPL activo",
            f"{metrics['creditos_activos']} créditos",
            fmt_ars(metrics["cartera_activa_bnpl"]),
        )

    st.divider()

    # --- Gráficos principales ---
    g1, g2 = st.columns(2)

    with g1:
        st.subheader("Composición de cartera")
        if metrics["cartera_activa_total"] <= 0:
            st.info("Todavía no hay cartera activa. Registrá operaciones en Factoring o BNPL.")
        else:
            fig = px.pie(
                names=["Factoring", "BNPL"],
                values=[
                    metrics["cartera_activa_factoring"],
                    metrics["cartera_activa_bnpl"],
                ],
                hole=0.55,
                color_discrete_sequence=["#38bdf8", "#f472b6"],
            )
            plotly_layout(fig)
            fig.update_traces(textinfo="percent+label", textfont_size=12)
            st.plotly_chart(fig, use_container_width=True)

        m1, m2 = st.columns(2)
        m1.metric("Comisiones factoring (mes)", fmt_ars(metrics["comisiones_mes"]))
        m2.metric("Intereses BNPL (mes)", fmt_ars(metrics["intereses_bnpl_mes"]))

    with g2:
        st.subheader("Ingresos históricos cobrados")
        hist_vals = [
            metrics["ganancia_hist_factoring"],
            metrics["interes_cobrado_bnpl"],
        ]
        if sum(hist_vals) <= 0:
            st.info("Aún no hay ingresos históricos registrados.")
        else:
            fig_h = px.bar(
                x=["Comisiones Factoring", "Intereses BNPL"],
                y=hist_vals,
                color=["Comisiones Factoring", "Intereses BNPL"],
                color_discrete_sequence=["#fbbf24", "#f472b6"],
                labels={"x": "", "y": "ARS"},
            )
            plotly_layout(fig_h)
            fig_h.update_layout(showlegend=False)
            st.plotly_chart(fig_h, use_container_width=True)

    st.divider()

    # --- Vencimientos ---
    v1, v2 = st.columns(2)

    with v1:
        st.subheader("Cupones a cobrar por fecha")
        cupones = metrics["cupones_por_fecha"]
        if not cupones:
            st.info("Sin cupones activos.")
        else:
            df_c = pd.DataFrame(cupones)
            fig_c = px.bar(
                df_c,
                x="fecha",
                y="total",
                text="cantidad",
                labels={"fecha": "Liquidación", "total": "ARS", "cantidad": "Ops"},
                color_discrete_sequence=["#38bdf8"],
            )
            plotly_layout(fig_c)
            fig_c.update_traces(textposition="outside")
            st.plotly_chart(fig_c, use_container_width=True)
            st.dataframe(
                df_c.rename(
                    columns={
                        "fecha": "Fecha",
                        "cantidad": "Cantidad",
                        "total": "Total ARS",
                    }
                ),
                use_container_width=True,
                hide_index=True,
                column_config={
                    "Total ARS": st.column_config.NumberColumn(format="$ %.2f"),
                },
            )

    with v2:
        st.subheader("Cuotas BNPL a vencer")
        cuotas = metrics["cuotas_por_fecha"]
        if not cuotas:
            st.info("Sin cuotas pendientes.")
        else:
            df_q = pd.DataFrame(cuotas)
            fig_q = px.bar(
                df_q,
                x="fecha",
                y="total",
                text="cantidad",
                labels={"fecha": "Vencimiento", "total": "ARS", "cantidad": "Cuotas"},
                color_discrete_sequence=["#f472b6"],
            )
            plotly_layout(fig_q)
            fig_q.update_traces(textposition="outside")
            st.plotly_chart(fig_q, use_container_width=True)
            st.dataframe(
                df_q.rename(
                    columns={
                        "fecha": "Fecha",
                        "cantidad": "Cantidad",
                        "total": "Total ARS",
                    }
                ),
                use_container_width=True,
                hide_index=True,
                column_config={
                    "Total ARS": st.column_config.NumberColumn(format="$ %.2f"),
                },
            )

    st.divider()
    st.subheader("Actividad reciente")
    actividad = metrics["actividad_reciente"]
    if not actividad:
        st.info("Sin operaciones todavía. Empezá por Factoring o BNPL desde el menú.")
    else:
        rows = []
        for a in actividad:
            rows.append(
                {
                    "Tipo": "Factoring" if a["tipo"] == "factoring" else "BNPL",
                    "ID": a["id"],
                    "Comercio": a["comercio"],
                    "Monto": a["monto"],
                    "Estado": a["estado"],
                    "Fecha": a["creado_en"],
                }
            )
        st.dataframe(
            pd.DataFrame(rows),
            use_container_width=True,
            hide_index=True,
            column_config={
                "Monto": st.column_config.NumberColumn(format="$ %.2f"),
            },
        )


def main() -> None:
    """Inicializa la DB, aplica estilos y renderiza la navegación."""
    inject_styles()
    init_db()

    with st.sidebar:
        st.markdown('<p class="finan-brand">Finan</p>', unsafe_allow_html=True)
        st.markdown(
            '<p class="finan-sub">Factoring & BNPL · MVP interactivo</p>',
            unsafe_allow_html=True,
        )
        st.divider()

        pagina = st.radio(
            "Menú",
            options=[
                "Dashboard",
                "Adelanto de Cupones",
                "Créditos BNPL",
            ],
            index=0,
            label_visibility="collapsed",
        )

        st.divider()
        metrics = get_dashboard_metrics()
        st.caption("Resumen rápido")
        st.metric("Cartera", fmt_ars(metrics["cartera_activa_total"]))
        st.metric("Ingresos mes", fmt_ars(metrics["ingresos_mes"]))
        st.caption("Datos locales · `finan.db`")

    if pagina == "Dashboard":
        render_dashboard()
    elif pagina == "Adelanto de Cupones":
        render_factoring()
    elif pagina == "Créditos BNPL":
        render_bnpl()


if __name__ == "__main__":
    main()
