# Paquete de módulos de la plataforma financiera.

from modules.bnpl import render_bnpl
from modules.database import get_dashboard_metrics, init_db
from modules.rbf_ui import render_rbf
from modules.ui import inject_styles

__all__ = [
    "render_rbf",
    "render_bnpl",
    "init_db",
    "get_dashboard_metrics",
    "inject_styles",
]
