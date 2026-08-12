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
      - factoring_ops / bnpl_*: módulos operativos existentes.
      - operaciones: expediente unificado (cupón / crédito comercio / BNPL).
      - audit_events: cadena de hashes append-only.
      - app_settings: config local (ej. API key Signatura).
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

            CREATE TABLE IF NOT EXISTS operaciones (
                id                  INTEGER PRIMARY KEY AUTOINCREMENT,
                tipo                TEXT    NOT NULL,
                ref_tabla           TEXT,
                ref_id              INTEGER,
                comercio            TEXT    NOT NULL,
                cuit                TEXT,
                email_firmante      TEXT,
                telefono_firmante   TEXT,
                email_fiador        TEXT,
                telefono_fiador     TEXT,
                cuit_fiador         TEXT,
                monto               REAL    NOT NULL,
                moneda              TEXT    NOT NULL DEFAULT 'ARS',
                estado              TEXT    NOT NULL DEFAULT 'borrador',
                doc_hash_sha256     TEXT,
                signatura_doc_id    TEXT,
                signatura_status    TEXT,
                signatura_cert_url  TEXT,
                payload_json        TEXT,
                creado_en           TEXT    NOT NULL,
                actualizado_en      TEXT    NOT NULL
            );

            CREATE TABLE IF NOT EXISTS audit_events (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                operacion_id    INTEGER NOT NULL,
                event_type      TEXT    NOT NULL,
                payload_json    TEXT,
                prev_hash       TEXT    NOT NULL,
                event_hash      TEXT    NOT NULL,
                created_at_utc  TEXT    NOT NULL,
                FOREIGN KEY (operacion_id) REFERENCES operaciones(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS app_settings (
                key   TEXT PRIMARY KEY,
                value TEXT NOT NULL
            );

            CREATE INDEX IF NOT EXISTS idx_operaciones_estado
                ON operaciones(estado);
            CREATE INDEX IF NOT EXISTS idx_operaciones_tipo
                ON operaciones(tipo);
            CREATE INDEX IF NOT EXISTS idx_audit_op
                ON audit_events(operacion_id);

            CREATE TABLE IF NOT EXISTS rbf_merchants (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                business_name   TEXT    NOT NULL,
                tax_id_cuit     TEXT,
                tax_status      TEXT    NOT NULL DEFAULT 'MONOTRIBUTO',
                has_echeq       INTEGER NOT NULL DEFAULT 0,
                avg_daily_sales REAL    NOT NULL DEFAULT 0,
                bank_cbu        TEXT,
                email           TEXT,
                phone           TEXT,
                creado_en       TEXT    NOT NULL
            );

            CREATE TABLE IF NOT EXISTS rbf_loans (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                merchant_id     INTEGER NOT NULL,
                principal       REAL    NOT NULL,
                monthly_rate    REAL    NOT NULL,
                term_months     INTEGER NOT NULL,
                calc_type       TEXT    NOT NULL,
                frequency       TEXT    NOT NULL,
                cuota_mensual   REAL    NOT NULL,
                total_a_cobrar  REAL    NOT NULL,
                interes_total   REAL    NOT NULL,
                status          TEXT    NOT NULL DEFAULT 'ACTIVE',
                start_date      TEXT    NOT NULL,
                operacion_id    INTEGER,
                payload_json    TEXT,
                creado_en       TEXT    NOT NULL,
                FOREIGN KEY (merchant_id) REFERENCES rbf_merchants(id)
            );

            CREATE TABLE IF NOT EXISTS rbf_guarantees (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                loan_id         INTEGER NOT NULL,
                type            TEXT    NOT NULL,
                identifier      TEXT,
                amount_covered  REAL    NOT NULL,
                is_active       INTEGER NOT NULL DEFAULT 1,
                FOREIGN KEY (loan_id) REFERENCES rbf_loans(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS rbf_sweeps (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                loan_id         INTEGER NOT NULL,
                nro             INTEGER NOT NULL,
                due_date        TEXT    NOT NULL,
                expected_amount REAL    NOT NULL,
                collected_amount REAL   NOT NULL DEFAULT 0,
                penalty_fee     REAL    NOT NULL DEFAULT 0,
                retention_pct   REAL,
                status          TEXT    NOT NULL DEFAULT 'PENDING',
                FOREIGN KEY (loan_id) REFERENCES rbf_loans(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS rbf_grace (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                loan_id         INTEGER NOT NULL,
                month           TEXT    NOT NULL,
                used_grace_days_count INTEGER NOT NULL DEFAULT 0,
                auto_recovery_active INTEGER NOT NULL DEFAULT 0,
                UNIQUE(loan_id, month),
                FOREIGN KEY (loan_id) REFERENCES rbf_loans(id) ON DELETE CASCADE
            );

            CREATE INDEX IF NOT EXISTS idx_rbf_loans_status ON rbf_loans(status);
            CREATE INDEX IF NOT EXISTS idx_rbf_sweeps_loan ON rbf_sweeps(loan_id);
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


# ---------------------------------------------------------------------------
# Settings
# ---------------------------------------------------------------------------

def get_setting(key: str) -> Optional[str]:
    with get_connection() as conn:
        row = conn.execute(
            "SELECT value FROM app_settings WHERE key = ?", (key,)
        ).fetchone()
        return str(row["value"]) if row else None


def set_setting(key: str, value: str) -> None:
    with get_connection() as conn:
        conn.execute(
            """
            INSERT INTO app_settings (key, value) VALUES (?, ?)
            ON CONFLICT(key) DO UPDATE SET value = excluded.value
            """,
            (key, value),
        )


# ---------------------------------------------------------------------------
# Operaciones (trazabilidad unificada)
# ---------------------------------------------------------------------------

def insert_operacion(data: dict[str, Any]) -> int:
    with get_connection() as conn:
        cursor = conn.execute(
            """
            INSERT INTO operaciones (
                tipo, ref_tabla, ref_id, comercio, cuit,
                email_firmante, telefono_firmante,
                email_fiador, telefono_fiador, cuit_fiador,
                monto, moneda, estado, doc_hash_sha256,
                signatura_doc_id, signatura_status, signatura_cert_url,
                payload_json, creado_en, actualizado_en
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                data["tipo"],
                data.get("ref_tabla") or "",
                data.get("ref_id"),
                data["comercio"],
                data.get("cuit") or "",
                data.get("email_firmante") or "",
                data.get("telefono_firmante") or "",
                data.get("email_fiador") or "",
                data.get("telefono_fiador") or "",
                data.get("cuit_fiador") or "",
                data["monto"],
                data.get("moneda") or "ARS",
                data.get("estado") or "borrador",
                data.get("doc_hash_sha256"),
                data.get("signatura_doc_id"),
                data.get("signatura_status"),
                data.get("signatura_cert_url"),
                data.get("payload_json") or "{}",
                data["creado_en"],
                data["actualizado_en"],
            ),
        )
        return int(cursor.lastrowid)


def get_operacion(op_id: int) -> Optional[dict[str, Any]]:
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM operaciones WHERE id = ?", (op_id,)
        ).fetchone()
        return dict(row) if row else None


def list_operaciones(
    estado: Optional[str] = None,
    tipo: Optional[str] = None,
) -> list[dict[str, Any]]:
    clauses: list[str] = []
    params: list[Any] = []
    if estado:
        clauses.append("estado = ?")
        params.append(estado)
    if tipo:
        clauses.append("tipo = ?")
        params.append(tipo)
    where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    with get_connection() as conn:
        rows = conn.execute(
            f"SELECT * FROM operaciones {where} ORDER BY id DESC",
            params,
        ).fetchall()
        return [dict(r) for r in rows]


def update_operacion(op_id: int, fields: dict[str, Any]) -> None:
    if not fields:
        return
    cols = ", ".join(f"{k} = ?" for k in fields)
    values = list(fields.values()) + [op_id]
    with get_connection() as conn:
        conn.execute(f"UPDATE operaciones SET {cols} WHERE id = ?", values)


def append_audit_event(data: dict[str, Any]) -> dict[str, Any]:
    with get_connection() as conn:
        cursor = conn.execute(
            """
            INSERT INTO audit_events (
                operacion_id, event_type, payload_json,
                prev_hash, event_hash, created_at_utc
            ) VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                data["operacion_id"],
                data["event_type"],
                data.get("payload_json") or "{}",
                data["prev_hash"],
                data["event_hash"],
                data["created_at_utc"],
            ),
        )
        event_id = int(cursor.lastrowid)
    return {
        "id": event_id,
        "operacion_id": data["operacion_id"],
        "event_type": data["event_type"],
        "payload_json": data.get("payload_json") or "{}",
        "prev_hash": data["prev_hash"],
        "event_hash": data["event_hash"],
        "created_at_utc": data["created_at_utc"],
    }


def list_audit_events(operacion_id: int) -> list[dict[str, Any]]:
    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT * FROM audit_events
            WHERE operacion_id = ?
            ORDER BY id ASC
            """,
            (operacion_id,),
        ).fetchall()
        return [dict(r) for r in rows]


# ---------------------------------------------------------------------------
# RBF — Adelanto de Flujo
# ---------------------------------------------------------------------------

def insert_rbf_merchant(data: dict[str, Any]) -> int:
    with get_connection() as conn:
        cur = conn.execute(
            """
            INSERT INTO rbf_merchants (
                business_name, tax_id_cuit, tax_status, has_echeq,
                avg_daily_sales, bank_cbu, email, phone, creado_en
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                data["business_name"],
                data.get("tax_id_cuit") or "",
                data.get("tax_status") or "MONOTRIBUTO",
                1 if data.get("has_echeq") else 0,
                float(data.get("avg_daily_sales") or 0),
                data.get("bank_cbu") or "",
                data.get("email") or "",
                data.get("phone") or "",
                data.get("creado_en") or datetime.now().isoformat(timespec="seconds"),
            ),
        )
        return int(cur.lastrowid)


def list_rbf_merchants() -> list[dict[str, Any]]:
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT * FROM rbf_merchants ORDER BY id DESC"
        ).fetchall()
        return [dict(r) for r in rows]


def get_rbf_merchant(merchant_id: int) -> Optional[dict[str, Any]]:
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM rbf_merchants WHERE id = ?", (merchant_id,)
        ).fetchone()
        return dict(row) if row else None


def insert_rbf_loan(
    loan: dict[str, Any],
    sweeps: list[dict[str, Any]],
    guarantees: list[dict[str, Any]],
) -> int:
    with get_connection() as conn:
        cur = conn.execute(
            """
            INSERT INTO rbf_loans (
                merchant_id, principal, monthly_rate, term_months, calc_type,
                frequency, cuota_mensual, total_a_cobrar, interes_total,
                status, start_date, operacion_id, payload_json, creado_en
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                loan["merchant_id"],
                loan["principal"],
                loan["monthly_rate"],
                loan["term_months"],
                loan["calc_type"],
                loan["frequency"],
                loan["cuota_mensual"],
                loan["total_a_cobrar"],
                loan["interes_total"],
                loan.get("status") or "ACTIVE",
                loan["start_date"],
                loan.get("operacion_id"),
                loan.get("payload_json") or "{}",
                loan.get("creado_en") or datetime.now().isoformat(timespec="seconds"),
            ),
        )
        loan_id = int(cur.lastrowid)

        for s in sweeps:
            conn.execute(
                """
                INSERT INTO rbf_sweeps (
                    loan_id, nro, due_date, expected_amount, collected_amount,
                    penalty_fee, retention_pct, status
                ) VALUES (?, ?, ?, ?, 0, 0, ?, 'PENDING')
                """,
                (
                    loan_id,
                    s["nro"],
                    s["due_date"],
                    s["expected_amount"],
                    s.get("retention_pct"),
                ),
            )

        for g in guarantees:
            conn.execute(
                """
                INSERT INTO rbf_guarantees (
                    loan_id, type, identifier, amount_covered, is_active
                ) VALUES (?, ?, ?, ?, 1)
                """,
                (
                    loan_id,
                    g["type"],
                    g.get("identifier") or "",
                    float(g.get("amount_covered") or loan["total_a_cobrar"]),
                ),
            )

        # grace tracker primer mes
        month_key = loan["start_date"][:7]
        conn.execute(
            """
            INSERT OR IGNORE INTO rbf_grace (
                loan_id, month, used_grace_days_count, auto_recovery_active
            ) VALUES (?, ?, 0, 0)
            """,
            (loan_id, month_key),
        )
        return loan_id


def list_rbf_loans(status: Optional[str] = None) -> list[dict[str, Any]]:
    with get_connection() as conn:
        if status:
            rows = conn.execute(
                """
                SELECT l.*, m.business_name, m.tax_id_cuit
                FROM rbf_loans l
                JOIN rbf_merchants m ON m.id = l.merchant_id
                WHERE l.status = ?
                ORDER BY l.id DESC
                """,
                (status,),
            ).fetchall()
        else:
            rows = conn.execute(
                """
                SELECT l.*, m.business_name, m.tax_id_cuit
                FROM rbf_loans l
                JOIN rbf_merchants m ON m.id = l.merchant_id
                ORDER BY l.id DESC
                """
            ).fetchall()
        return [dict(r) for r in rows]


def get_rbf_loan(loan_id: int) -> Optional[dict[str, Any]]:
    with get_connection() as conn:
        row = conn.execute(
            """
            SELECT l.*, m.business_name, m.tax_id_cuit, m.avg_daily_sales,
                   m.tax_status, m.has_echeq, m.email, m.phone
            FROM rbf_loans l
            JOIN rbf_merchants m ON m.id = l.merchant_id
            WHERE l.id = ?
            """,
            (loan_id,),
        ).fetchone()
        return dict(row) if row else None


def list_rbf_sweeps(loan_id: int) -> list[dict[str, Any]]:
    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT * FROM rbf_sweeps
            WHERE loan_id = ?
            ORDER BY nro ASC
            """,
            (loan_id,),
        ).fetchall()
        return [dict(r) for r in rows]


def update_rbf_sweep(
    sweep_id: int,
    *,
    collected_amount: float,
    status: str,
    penalty_fee: float = 0.0,
) -> None:
    with get_connection() as conn:
        conn.execute(
            """
            UPDATE rbf_sweeps
            SET collected_amount = ?, status = ?, penalty_fee = ?
            WHERE id = ?
            """,
            (collected_amount, status, penalty_fee, sweep_id),
        )


def update_rbf_loan_status(loan_id: int, status: str) -> None:
    with get_connection() as conn:
        conn.execute(
            "UPDATE rbf_loans SET status = ? WHERE id = ?",
            (status, loan_id),
        )


def get_rbf_grace(loan_id: int, month: str) -> dict[str, Any]:
    with get_connection() as conn:
        row = conn.execute(
            """
            SELECT * FROM rbf_grace WHERE loan_id = ? AND month = ?
            """,
            (loan_id, month),
        ).fetchone()
        if row:
            return dict(row)
        conn.execute(
            """
            INSERT INTO rbf_grace (
                loan_id, month, used_grace_days_count, auto_recovery_active
            ) VALUES (?, ?, 0, 0)
            """,
            (loan_id, month),
        )
        row = conn.execute(
            "SELECT * FROM rbf_grace WHERE loan_id = ? AND month = ?",
            (loan_id, month),
        ).fetchone()
        return dict(row) if row else {
            "loan_id": loan_id,
            "month": month,
            "used_grace_days_count": 0,
            "auto_recovery_active": 0,
        }


def update_rbf_grace(
    loan_id: int,
    month: str,
    used: int,
    auto_recovery: bool,
) -> None:
    with get_connection() as conn:
        conn.execute(
            """
            INSERT INTO rbf_grace (
                loan_id, month, used_grace_days_count, auto_recovery_active
            ) VALUES (?, ?, ?, ?)
            ON CONFLICT(loan_id, month) DO UPDATE SET
                used_grace_days_count = excluded.used_grace_days_count,
                auto_recovery_active = excluded.auto_recovery_active
            """,
            (loan_id, month, used, 1 if auto_recovery else 0),
        )


def rbf_loan_progress(loan_id: int) -> dict[str, Any]:
    with get_connection() as conn:
        row = conn.execute(
            """
            SELECT
                COUNT(*) AS total,
                SUM(CASE WHEN status = 'PAID' THEN 1 ELSE 0 END) AS paid,
                COALESCE(SUM(expected_amount), 0) AS expected,
                COALESCE(SUM(collected_amount), 0) AS collected
            FROM rbf_sweeps WHERE loan_id = ?
            """,
            (loan_id,),
        ).fetchone()
        total = int(row["total"] or 0)
        paid = int(row["paid"] or 0)
        return {
            "total": total,
            "paid": paid,
            "expected": float(row["expected"]),
            "collected": float(row["collected"]),
            "pct": (paid / total * 100) if total else 0.0,
        }

