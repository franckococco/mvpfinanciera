"""
Módulo de persistencia local con SQLite.

Gestiona el esquema, la inicialización de la base de datos y las operaciones
CRUD necesarias para Factoring, BNPL y el Dashboard administrativo.
"""

from __future__ import annotations

import os
import sqlite3
from contextlib import contextmanager
from datetime import date, datetime
from typing import Any, Generator, Optional

# Ruta absoluta del archivo SQLite (carpeta raíz del proyecto).
DB_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "finan.db")


@contextmanager
def get_connection() -> Generator[sqlite3.Connection, None, None]:
    """Abre una conexión SQLite con row_factory tipo dict y la cierra al salir."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_db() -> None:
    """
    Crea las tablas si no existen.

    Tablas:
      - factoring_ops: operaciones de adelanto de cupones.
      - bnpl_credits: créditos BNPL (cabecera).
      - bnpl_installments: cronograma de cuotas de cada crédito.
    """
    with get_connection() as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS factoring_ops (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                comercio        TEXT    NOT NULL,
                cuit            TEXT,
                monto_bruto     REAL    NOT NULL,
                tasa_comision   REAL    NOT NULL,
                fecha_liquidacion TEXT  NOT NULL,
                monto_neto      REAL    NOT NULL,
                ganancia        REAL    NOT NULL,
                tna             REAL    NOT NULL,
                tea             REAL    NOT NULL,
                dias_adelanto   INTEGER NOT NULL,
                estado          TEXT    NOT NULL DEFAULT 'activa',
                creado_en       TEXT    NOT NULL
            );

            CREATE TABLE IF NOT EXISTS bnpl_credits (
                id                  INTEGER PRIMARY KEY AUTOINCREMENT,
                dni_cliente         TEXT    NOT NULL,
                nombre_cliente      TEXT,
                comercio            TEXT    NOT NULL,
                monto_producto      REAL    NOT NULL,
                cantidad_cuotas     INTEGER NOT NULL,
                tasa_mensual        REAL    NOT NULL,
                cuota_mensual       REAL    NOT NULL,
                total_a_pagar       REAL    NOT NULL,
                interes_total       REAL    NOT NULL,
                pagare_texto        TEXT,
                estado              TEXT    NOT NULL DEFAULT 'activa',
                creado_en           TEXT    NOT NULL
            );

            CREATE TABLE IF NOT EXISTS bnpl_installments (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                credito_id      INTEGER NOT NULL,
                nro_cuota       INTEGER NOT NULL,
                fecha_vencimiento TEXT  NOT NULL,
                capital         REAL    NOT NULL,
                interes         REAL    NOT NULL,
                cuota_total     REAL    NOT NULL,
                saldo_restante  REAL    NOT NULL,
                estado          TEXT    NOT NULL DEFAULT 'pendiente',
                FOREIGN KEY (credito_id) REFERENCES bnpl_credits(id) ON DELETE CASCADE
            );
            """
        )


# ---------------------------------------------------------------------------
# Factoring
# ---------------------------------------------------------------------------

def insert_factoring_op(data: dict[str, Any]) -> int:
    """Inserta una operación de factoring y devuelve el ID generado."""
    with get_connection() as conn:
        cursor = conn.execute(
            """
            INSERT INTO factoring_ops (
                comercio, cuit, monto_bruto, tasa_comision, fecha_liquidacion,
                monto_neto, ganancia, tna, tea, dias_adelanto, estado, creado_en
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                data["comercio"],
                data.get("cuit", ""),
                data["monto_bruto"],
                data["tasa_comision"],
                data["fecha_liquidacion"],
                data["monto_neto"],
                data["ganancia"],
                data["tna"],
                data["tea"],
                data["dias_adelanto"],
                data.get("estado", "activa"),
                data.get("creado_en", datetime.now().isoformat(timespec="seconds")),
            ),
        )
        return int(cursor.lastrowid)


def list_factoring_ops(estado: Optional[str] = None) -> list[dict[str, Any]]:
    """Lista operaciones de factoring, opcionalmente filtradas por estado."""
    with get_connection() as conn:
        if estado:
            rows = conn.execute(
                "SELECT * FROM factoring_ops WHERE estado = ? ORDER BY id DESC",
                (estado,),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM factoring_ops ORDER BY id DESC"
            ).fetchall()
        return [dict(r) for r in rows]


def update_factoring_estado(op_id: int, estado: str) -> None:
    """Actualiza el estado de una operación de factoring (activa / cobrada)."""
    with get_connection() as conn:
        conn.execute(
            "UPDATE factoring_ops SET estado = ? WHERE id = ?",
            (estado, op_id),
        )


def get_factoring_op(op_id: int) -> Optional[dict[str, Any]]:
    """Obtiene una operación de factoring por ID."""
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM factoring_ops WHERE id = ?", (op_id,)
        ).fetchone()
        return dict(row) if row else None


# ---------------------------------------------------------------------------
# BNPL
# ---------------------------------------------------------------------------

def insert_bnpl_credit(
    credit: dict[str, Any],
    installments: list[dict[str, Any]],
) -> int:
    """
    Inserta un crédito BNPL junto con su cronograma de cuotas.
    Devuelve el ID del crédito creado.
    """
    with get_connection() as conn:
        cursor = conn.execute(
            """
            INSERT INTO bnpl_credits (
                dni_cliente, nombre_cliente, comercio, monto_producto,
                cantidad_cuotas, tasa_mensual, cuota_mensual, total_a_pagar,
                interes_total, pagare_texto, estado, creado_en
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                credit["dni_cliente"],
                credit.get("nombre_cliente", ""),
                credit["comercio"],
                credit["monto_producto"],
                credit["cantidad_cuotas"],
                credit["tasa_mensual"],
                credit["cuota_mensual"],
                credit["total_a_pagar"],
                credit["interes_total"],
                credit.get("pagare_texto", ""),
                credit.get("estado", "activa"),
                credit.get("creado_en", datetime.now().isoformat(timespec="seconds")),
            ),
        )
        credito_id = int(cursor.lastrowid)

        for inst in installments:
            conn.execute(
                """
                INSERT INTO bnpl_installments (
                    credito_id, nro_cuota, fecha_vencimiento, capital,
                    interes, cuota_total, saldo_restante, estado
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    credito_id,
                    inst["nro_cuota"],
                    inst["fecha_vencimiento"],
                    inst["capital"],
                    inst["interes"],
                    inst["cuota_total"],
                    inst["saldo_restante"],
                    inst.get("estado", "pendiente"),
                ),
            )

        return credito_id


def list_bnpl_credits(estado: Optional[str] = None) -> list[dict[str, Any]]:
    """Lista créditos BNPL, opcionalmente filtrados por estado."""
    with get_connection() as conn:
        if estado:
            rows = conn.execute(
                "SELECT * FROM bnpl_credits WHERE estado = ? ORDER BY id DESC",
                (estado,),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM bnpl_credits ORDER BY id DESC"
            ).fetchall()
        return [dict(r) for r in rows]


def get_bnpl_credit(credito_id: int) -> Optional[dict[str, Any]]:
    """Obtiene un crédito BNPL por ID."""
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM bnpl_credits WHERE id = ?", (credito_id,)
        ).fetchone()
        return dict(row) if row else None


def list_bnpl_installments(credito_id: int) -> list[dict[str, Any]]:
    """Devuelve el cronograma de cuotas de un crédito."""
    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT * FROM bnpl_installments
            WHERE credito_id = ?
            ORDER BY nro_cuota ASC
            """,
            (credito_id,),
        ).fetchall()
        return [dict(r) for r in rows]


def update_installment_estado(installment_id: int, estado: str) -> None:
    """Marca una cuota como pendiente o pagada."""
    with get_connection() as conn:
        conn.execute(
            "UPDATE bnpl_installments SET estado = ? WHERE id = ?",
            (estado, installment_id),
        )
        # Si todas las cuotas están pagadas, cierra el crédito.
        row = conn.execute(
            "SELECT credito_id FROM bnpl_installments WHERE id = ?",
            (installment_id,),
        ).fetchone()
        if row:
            credito_id = int(row["credito_id"])
            pendientes = conn.execute(
                """
                SELECT COUNT(*) AS c FROM bnpl_installments
                WHERE credito_id = ? AND estado = 'pendiente'
                """,
                (credito_id,),
            ).fetchone()
            if int(pendientes["c"]) == 0:
                conn.execute(
                    "UPDATE bnpl_credits SET estado = 'cerrada' WHERE id = ?",
                    (credito_id,),
                )


def update_bnpl_estado(credito_id: int, estado: str) -> None:
    """Actualiza el estado de un crédito BNPL."""
    with get_connection() as conn:
        conn.execute(
            "UPDATE bnpl_credits SET estado = ? WHERE id = ?",
            (estado, credito_id),
        )


def get_bnpl_progress(credito_id: int) -> dict[str, Any]:
    """Progreso de cobro de un crédito (cuotas pagadas vs total)."""
    with get_connection() as conn:
        row = conn.execute(
            """
            SELECT
                COUNT(*) AS total,
                SUM(CASE WHEN estado = 'pagada' THEN 1 ELSE 0 END) AS pagadas,
                COALESCE(SUM(CASE WHEN estado = 'pagada' THEN cuota_total ELSE 0 END), 0) AS cobrado,
                COALESCE(SUM(CASE WHEN estado = 'pendiente' THEN cuota_total ELSE 0 END), 0) AS pendiente
            FROM bnpl_installments
            WHERE credito_id = ?
            """,
            (credito_id,),
        ).fetchone()
        total = int(row["total"] or 0)
        pagadas = int(row["pagadas"] or 0)
        return {
            "total": total,
            "pagadas": pagadas,
            "pct": (pagadas / total * 100) if total else 0.0,
            "cobrado": float(row["cobrado"]),
            "pendiente": float(row["pendiente"]),
        }


# ---------------------------------------------------------------------------
# Dashboard / métricas
# ---------------------------------------------------------------------------

def get_dashboard_metrics() -> dict[str, Any]:
    """
    Calcula métricas agregadas para el panel administrativo.

    Retorna cartera, comisiones, cupones por fecha, series para gráficos
    y actividad reciente.
    """
    hoy = date.today()
    mes_inicio = hoy.replace(day=1).isoformat()
    if hoy.month == 12:
        mes_siguiente = date(hoy.year + 1, 1, 1).isoformat()
    else:
        mes_siguiente = date(hoy.year, hoy.month + 1, 1).isoformat()

    with get_connection() as conn:
        row = conn.execute(
            """
            SELECT COALESCE(SUM(monto_bruto), 0) AS total,
                   COUNT(*) AS cantidad
            FROM factoring_ops
            WHERE estado = 'activa'
            """
        ).fetchone()
        cartera_factoring = float(row["total"])
        ops_factoring = int(row["cantidad"])

        row = conn.execute(
            """
            SELECT COALESCE(SUM(i.cuota_total), 0) AS total
            FROM bnpl_installments i
            JOIN bnpl_credits c ON c.id = i.credito_id
            WHERE c.estado = 'activa' AND i.estado = 'pendiente'
            """
        ).fetchone()
        cartera_bnpl = float(row["total"])

        row = conn.execute(
            """
            SELECT COUNT(*) AS cantidad
            FROM bnpl_credits
            WHERE estado = 'activa'
            """
        ).fetchone()
        creditos_activos = int(row["cantidad"])

        row = conn.execute(
            """
            SELECT COALESCE(SUM(ganancia), 0) AS total
            FROM factoring_ops
            WHERE creado_en >= ? AND creado_en < ?
            """,
            (mes_inicio, mes_siguiente),
        ).fetchone()
        comisiones_mes = float(row["total"])

        # Intereses BNPL cobrados (cuotas pagadas este mes) — aproximado por fecha vencimiento.
        row = conn.execute(
            """
            SELECT COALESCE(SUM(interes), 0) AS total
            FROM bnpl_installments
            WHERE estado = 'pagada'
              AND fecha_vencimiento >= ? AND fecha_vencimiento < ?
            """,
            (mes_inicio, mes_siguiente),
        ).fetchone()
        intereses_bnpl_mes = float(row["total"])

        rows = conn.execute(
            """
            SELECT fecha_liquidacion AS fecha,
                   COUNT(*) AS cantidad,
                   SUM(monto_bruto) AS total
            FROM factoring_ops
            WHERE estado = 'activa'
            GROUP BY fecha_liquidacion
            ORDER BY fecha_liquidacion ASC
            """
        ).fetchall()
        cupones_por_fecha = [dict(r) for r in rows]

        # Cuotas BNPL a vencer por fecha (pendientes).
        rows = conn.execute(
            """
            SELECT i.fecha_vencimiento AS fecha,
                   COUNT(*) AS cantidad,
                   SUM(i.cuota_total) AS total
            FROM bnpl_installments i
            JOIN bnpl_credits c ON c.id = i.credito_id
            WHERE i.estado = 'pendiente' AND c.estado = 'activa'
            GROUP BY i.fecha_vencimiento
            ORDER BY i.fecha_vencimiento ASC
            LIMIT 12
            """
        ).fetchall()
        cuotas_por_fecha = [dict(r) for r in rows]

        # Actividad reciente (últimas 8 operaciones de ambos tipos).
        recientes_f = conn.execute(
            """
            SELECT id, comercio, monto_bruto AS monto, estado, creado_en,
                   'factoring' AS tipo
            FROM factoring_ops
            ORDER BY id DESC LIMIT 5
            """
        ).fetchall()
        recientes_b = conn.execute(
            """
            SELECT id, comercio, monto_producto AS monto, estado, creado_en,
                   'bnpl' AS tipo
            FROM bnpl_credits
            ORDER BY id DESC LIMIT 5
            """
        ).fetchall()
        actividad = [dict(r) for r in recientes_f] + [dict(r) for r in recientes_b]
        actividad.sort(key=lambda x: x.get("creado_en", ""), reverse=True)
        actividad = actividad[:8]

        # Totales históricos para gráfico de composición.
        row = conn.execute(
            "SELECT COALESCE(SUM(ganancia), 0) AS g FROM factoring_ops"
        ).fetchone()
        ganancia_hist = float(row["g"])

        row = conn.execute(
            """
            SELECT COALESCE(SUM(interes), 0) AS i
            FROM bnpl_installments WHERE estado = 'pagada'
            """
        ).fetchone()
        interes_cobrado = float(row["i"])

    return {
        "cartera_activa_factoring": cartera_factoring,
        "cartera_activa_bnpl": cartera_bnpl,
        "cartera_activa_total": cartera_factoring + cartera_bnpl,
        "comisiones_mes": comisiones_mes,
        "intereses_bnpl_mes": intereses_bnpl_mes,
        "ingresos_mes": comisiones_mes + intereses_bnpl_mes,
        "cupones_por_fecha": cupones_por_fecha,
        "cuotas_por_fecha": cuotas_por_fecha,
        "creditos_activos": creditos_activos,
        "ops_factoring_activas": ops_factoring,
        "mes_referencia": hoy.strftime("%Y-%m"),
        "actividad_reciente": actividad,
        "ganancia_hist_factoring": ganancia_hist,
        "interes_cobrado_bnpl": interes_cobrado,
    }
