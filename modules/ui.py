"""
Utilidades de interfaz compartidas: estilos CSS, formato de moneda y
componentes visuales reutilizables (KPI cards, badges de estado).
"""

from __future__ import annotations

import streamlit as st


def inject_styles() -> None:
    """Inyecta CSS global para una interfaz más limpia e interactiva."""
    st.markdown(
        """
        <style>
        /* Tipografía y fondo */
        .stApp {
            background: linear-gradient(165deg, #0b1220 0%, #121a2b 45%, #0e1624 100%);
            color: #e8edf5;
        }
        [data-testid="stSidebar"] {
            background: linear-gradient(180deg, #0a101c 0%, #101827 100%);
            border-right: 1px solid rgba(255,255,255,0.06);
        }
        [data-testid="stSidebar"] * { color: #d7deea !important; }

        /* Títulos */
        h1, h2, h3 { color: #f3f6fb !important; letter-spacing: -0.02em; }
        .finan-brand {
            font-size: 1.65rem; font-weight: 750; color: #7dd3fc !important;
            margin: 0 0 0.15rem 0;
        }
        .finan-sub {
            color: #94a3b8 !important; font-size: 0.85rem; margin-bottom: 0.8rem;
        }

        /* KPI cards */
        .kpi-card {
            background: linear-gradient(145deg, rgba(30,41,59,0.9), rgba(15,23,42,0.95));
            border: 1px solid rgba(125,211,252,0.18);
            border-radius: 14px;
            padding: 1rem 1.1rem 0.95rem 1.1rem;
            margin-bottom: 0.6rem;
            box-shadow: 0 8px 24px rgba(0,0,0,0.25);
        }
        .kpi-label {
            font-size: 0.78rem; color: #94a3b8; text-transform: uppercase;
            letter-spacing: 0.06em; margin-bottom: 0.35rem;
        }
        .kpi-value {
            font-size: 1.45rem; font-weight: 700; color: #f8fafc;
            line-height: 1.15;
        }
        .kpi-hint { font-size: 0.75rem; color: #64748b; margin-top: 0.35rem; }

        /* Result highlight strip */
        .result-strip {
            display: flex; gap: 0.75rem; flex-wrap: wrap;
            background: rgba(14,165,233,0.08);
            border: 1px solid rgba(14,165,233,0.25);
            border-radius: 12px; padding: 0.9rem 1rem; margin: 0.5rem 0 1rem 0;
        }
        .result-item { flex: 1; min-width: 140px; }
        .result-item .lbl { font-size: 0.72rem; color: #7dd3fc; text-transform: uppercase; }
        .result-item .val { font-size: 1.2rem; font-weight: 700; color: #f8fafc; }

        /* Badges */
        .badge {
            display: inline-block; padding: 0.15rem 0.55rem; border-radius: 999px;
            font-size: 0.72rem; font-weight: 600; letter-spacing: 0.03em;
        }
        .badge-activa, .badge-pendiente {
            background: rgba(56,189,248,0.15); color: #7dd3fc;
            border: 1px solid rgba(56,189,248,0.35);
        }
        .badge-cobrada, .badge-pagada, .badge-cerrada {
            background: rgba(52,211,153,0.15); color: #6ee7b7;
            border: 1px solid rgba(52,211,153,0.35);
        }
        .badge-vencida {
            background: rgba(248,113,113,0.15); color: #fca5a5;
            border: 1px solid rgba(248,113,113,0.35);
        }

        /* Compact metric tweaks */
        div[data-testid="stMetric"] {
            background: rgba(30,41,59,0.55);
            border: 1px solid rgba(148,163,184,0.15);
            border-radius: 12px;
            padding: 0.75rem 0.9rem;
        }
        div[data-testid="stMetric"] label { color: #94a3b8 !important; }

        /* Tabs */
        .stTabs [data-baseweb="tab-list"] {
            gap: 0.4rem; background: transparent;
        }
        .stTabs [data-baseweb="tab"] {
            background: rgba(30,41,59,0.6);
            border-radius: 10px 10px 0 0;
            color: #cbd5e1;
            padding: 0.45rem 1rem;
        }
        .stTabs [aria-selected="true"] {
            background: rgba(14,165,233,0.2) !important;
            color: #e0f2fe !important;
        }

        /* Buttons */
        .stButton > button[kind="primary"] {
            background: linear-gradient(90deg, #0284c7, #0ea5e9);
            border: none; color: white; font-weight: 600;
        }
        .stButton > button:hover { transform: translateY(-1px); transition: 0.15s ease; }

        /* Dataframes */
        [data-testid="stDataFrame"] {
            border: 1px solid rgba(148,163,184,0.15);
            border-radius: 10px; overflow: hidden;
        }

        /* Hide default footer noise */
        footer { visibility: hidden; }
        </style>
        """,
        unsafe_allow_html=True,
    )


def fmt_ars(valor: float) -> str:
    """Formatea un monto en pesos argentinos (ARS)."""
    return f"$ {valor:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def kpi_card(label: str, value: str, hint: str = "") -> None:
    """Renderiza una tarjeta KPI HTML."""
    hint_html = f'<div class="kpi-hint">{hint}</div>' if hint else ""
    st.markdown(
        f"""
        <div class="kpi-card">
            <div class="kpi-label">{label}</div>
            <div class="kpi-value">{value}</div>
            {hint_html}
        </div>
        """,
        unsafe_allow_html=True,
    )


def result_strip(items: list[tuple[str, str]]) -> None:
    """
    Franja de resultados rápidos.
    items: lista de (etiqueta, valor).
    """
    parts = "".join(
        f'<div class="result-item"><div class="lbl">{lbl}</div>'
        f'<div class="val">{val}</div></div>'
        for lbl, val in items
    )
    st.markdown(f'<div class="result-strip">{parts}</div>', unsafe_allow_html=True)


def badge_estado(estado: str) -> str:
    """Devuelve HTML de un badge según el estado."""
    e = (estado or "").lower()
    return f'<span class="badge badge-{e}">{estado.upper()}</span>'


def plotly_layout(fig, title: str = "") -> None:
    """Aplica tema oscuro consistente a un gráfico Plotly."""
    fig.update_layout(
        title=dict(text=title, font=dict(size=14, color="#e2e8f0")),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(15,23,42,0.4)",
        font=dict(color="#cbd5e1", size=12),
        margin=dict(l=40, r=20, t=50, b=40),
        legend=dict(bgcolor="rgba(0,0,0,0)"),
        xaxis=dict(gridcolor="rgba(148,163,184,0.12)", zeroline=False),
        yaxis=dict(gridcolor="rgba(148,163,184,0.12)", zeroline=False),
    )
