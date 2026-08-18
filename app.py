"""
Finan — préstamo al comercio y crédito al cliente del comercio.

Punto de entrada principal (Streamlit). Navegación por sidebar:
  1. Dashboard
  2. Préstamo al comercio
  3. Crédito al cliente del comercio
  4. Trazabilidad (contratos, firma, desembolso)
"""

from __future__ import annotations

import pandas as pd
import plotly.express as px
import streamlit as st

from modules.bnpl import render_bnpl
from modules.database import get_dashboard_metrics, init_db
from modules.mercadopago import consume_oauth_if_present
from modules.rbf_ui import render_rbf
from modules.trazabilidad_ui import render_trazabilidad
from modules.ui import fmt_ars, inject_styles, kpi_card, plotly_layout


st.set_page_config(
    page_title="Finan · Préstamos y créditos",
    page_icon="💰",
    layout="wide",
    initial_sidebar_state="expanded",
)


def render_dashboard() -> None:
    """Dashboard: cartera de los dos productos y vencimientos."""
    st.header("Dashboard")
    st.caption(
        "Préstamo al comercio · crédito al cliente del comercio · ingresos del mes. "
        "El desembolso se habilita en Trazabilidad después de firmar."
    )

    metrics = get_dashboard_metrics()

    k1, k2, k3, k4 = st.columns(4)
    with k1:
        kpi_card(
            "Cartera activa",
            fmt_ars(metrics["cartera_activa_total"]),
            "Comercio + cliente",
        )
    with k2:
        kpi_card(
            "Ingresos del mes",
            fmt_ars(metrics["ingresos_mes"]),
            f"Mes {metrics['mes_referencia']}",
        )
    with k3:
        kpi_card(
            "Préstamos al comercio",
            f"{metrics.get('rbf_activos', 0)} activos",
            fmt_ars(metrics.get("cartera_activa_rbf", 0)),
        )
    with k4:
        kpi_card(
            "Créditos a clientes",
            f"{metrics['creditos_activos']} activos",
            fmt_ars(metrics["cartera_activa_bnpl"]),
        )

    st.divider()

    g1, g2 = st.columns(2)

    with g1:
        st.subheader("Composición de cartera")
        if metrics["cartera_activa_total"] <= 0:
            st.info(
                "Todavía no hay cartera activa. Registrá un préstamo al comercio "
                "o un crédito al cliente desde el menú."
            )
        else:
            fig = px.pie(
                names=["Préstamo al comercio", "Crédito al cliente"],
                values=[
                    metrics.get("cartera_activa_rbf", 0),
                    metrics["cartera_activa_bnpl"],
                ],
                hole=0.55,
                color_discrete_sequence=["#34d399", "#f472b6"],
            )
            plotly_layout(fig)
            fig.update_traces(textinfo="percent+label", textfont_size=12)
            st.plotly_chart(fig, use_container_width=True)

        m1, m2 = st.columns(2)
        m1.metric("Cobros préstamo comercio (mes)", fmt_ars(metrics.get("cobros_rbf_mes", 0)))
        m2.metric("Intereses crédito cliente (mes)", fmt_ars(metrics["intereses_bnpl_mes"]))

    with g2:
        st.subheader("Ingresos históricos cobrados")
        hist_vals = [
            metrics.get("cobrado_hist_rbf", 0),
            metrics["interes_cobrado_bnpl"],
        ]
        if sum(hist_vals) <= 0:
            st.info("Aún no hay ingresos históricos registrados.")
        else:
            fig_h = px.bar(
                x=["Barridos comercio", "Intereses cliente"],
                y=hist_vals,
                color=["Barridos comercio", "Intereses cliente"],
                color_discrete_sequence=["#34d399", "#f472b6"],
                labels={"x": "", "y": "ARS"},
            )
            plotly_layout(fig_h)
            fig_h.update_layout(showlegend=False)
            st.plotly_chart(fig_h, use_container_width=True)
        st.metric("Capital colocado al comercio", fmt_ars(metrics.get("cartera_rbf_capital", 0)))

    st.divider()

    v1, v2 = st.columns(2)

    with v1:
        st.subheader("Barridos del préstamo al comercio")
        barridos = metrics.get("barridos_por_fecha") or []
        if not barridos:
            st.info("Sin barridos pendientes.")
        else:
            df_c = pd.DataFrame(barridos)
            fig_c = px.bar(
                df_c,
                x="fecha",
                y="total",
                text="cantidad",
                labels={"fecha": "Vencimiento", "total": "ARS", "cantidad": "Barridos"},
                color_discrete_sequence=["#34d399"],
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
        st.subheader("Cuotas del crédito al cliente")
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
        st.info("Sin operaciones todavía. Empezá por un préstamo o un crédito desde el menú.")
    else:
        rows = []
        for a in actividad:
            tipo = a["tipo"]
            label = {
                "bnpl": "Crédito al cliente",
                "rbf": "Préstamo al comercio",
            }.get(tipo, tipo)
            rows.append(
                {
                    "Tipo": label,
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
    mp_msg = consume_oauth_if_present()
    if mp_msg:
        st.session_state["mp_flash"] = mp_msg

    with st.sidebar:
        st.markdown('<p class="finan-brand">Finan</p>', unsafe_allow_html=True)
        st.markdown(
            '<p class="finan-sub">Préstamo al comercio · Crédito al cliente</p>',
            unsafe_allow_html=True,
        )
        st.divider()

        pagina = st.radio(
            "Menú",
            options=[
                "Dashboard",
                "Préstamo al comercio",
                "Crédito al cliente del comercio",
                "Trazabilidad",
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

    flash = st.session_state.pop("mp_flash", None)
    if flash:
        st.success(flash)

    if pagina == "Dashboard":
        render_dashboard()
    elif pagina == "Préstamo al comercio":
        render_rbf()
    elif pagina == "Crédito al cliente del comercio":
        render_bnpl()
    elif pagina == "Trazabilidad":
        render_trazabilidad()


if __name__ == "__main__":
    main()
