# Paquete de módulos de la plataforma financiera.

from modules.bnpl import render_bnpl
from modules.database import get_dashboard_metrics, init_db
from modules.factoring import render_factoring
from modules.ui import inject_styles

__all__ = [
    "render_factoring",
    "render_bnpl",
    "init_db",
    "get_dashboard_metrics",
    "inject_styles",
]
