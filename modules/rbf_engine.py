"""
Motor de Adelantos de Flujo (Revenue-Based Financing).

- Método A: tasa plana (flat)
- Método B: sistema francés sobre saldo
- Cronogramas de barrido: diario / semanal / quincenal / días específicos
- Reglas de riesgo: retención, alertas, respiro (sin exponer al comercio)
"""

from __future__ import annotations

from calendar import monthrange
from datetime import date, timedelta
from typing import Any, Literal

CalcType = Literal["FLAT", "FRENCH"]
Frequency = Literal["DAILY", "WEEKLY", "BIWEEKLY", "CUSTOM_DAYS"]

DEFAULT_MONTHLY_RATE = 0.15  # 15% mensual
DEFAULT_TERM_MONTHS = 3
MAX_GRACE_DAYS_PER_MONTH = 3
RETENTION_ALERT_PCT = 25.0
PUNITIVE_DAILY_RATE_DEFAULT = 0.005  # 0.5% diario


def pmt(principal: float, monthly_rate: float, n_months: int) -> float:
    """Cuota fija sistema francés."""
    if principal <= 0 or n_months < 1:
        raise ValueError("Capital y plazo inválidos.")
    if monthly_rate == 0:
        return round(principal / n_months, 2)
    r = monthly_rate
    factor = (1 + r) ** n_months
    return round(principal * (r * factor) / (factor - 1), 2)


def amortizacion_frances(
    principal: float,
    monthly_rate: float,
    n_months: int,
) -> tuple[float, list[dict[str, Any]], float]:
    """
    Tabla mensual francesa. Ajusta la última fila para que el capital amortizado = P.
    Returns: (cuota, filas, total_a_cobrar)
    """
    cuota = pmt(principal, monthly_rate, n_months)
    saldo = round(principal, 2)
    filas: list[dict[str, Any]] = []
    capital_acum = 0.0

    for m in range(1, n_months + 1):
        interes = round(saldo * monthly_rate, 2)
        if m == n_months:
            capital = round(saldo, 2)
            cuota_m = round(capital + interes, 2)
            saldo = 0.0
        else:
            capital = round(cuota - interes, 2)
            if capital > saldo:
                capital = round(saldo, 2)
                cuota_m = round(capital + interes, 2)
            else:
                cuota_m = cuota
            saldo = round(saldo - capital, 2)
        capital_acum = round(capital_acum + capital, 2)
        filas.append(
            {
                "mes": m,
                "cuota": cuota_m,
                "interes": interes,
                "capital": capital,
                "saldo": saldo,
            }
        )

    # Corrección residual de redondeo sobre capital
    diff = round(principal - capital_acum, 2)
    if diff != 0 and filas:
        filas[-1]["capital"] = round(filas[-1]["capital"] + diff, 2)
        filas[-1]["cuota"] = round(filas[-1]["capital"] + filas[-1]["interes"], 2)
        filas[-1]["saldo"] = 0.0

    total = round(sum(f["cuota"] for f in filas), 2)
    return cuota, filas, total


def amortizacion_plana(
    principal: float,
    monthly_rate: float,
    n_months: int,
) -> tuple[float, list[dict[str, Any]], float]:
    """Interés = P * r * n; cuotas iguales capital/n + interés/n."""
    if principal <= 0 or n_months < 1:
        raise ValueError("Capital y plazo inválidos.")
    interes_total = round(principal * monthly_rate * n_months, 2)
    total = round(principal + interes_total, 2)
    capital_cuota = round(principal / n_months, 2)
    interes_cuota = round(interes_total / n_months, 2)
    cuota = round(capital_cuota + interes_cuota, 2)
    saldo = round(principal, 2)
    filas: list[dict[str, Any]] = []
    capital_acum = 0.0

    for m in range(1, n_months + 1):
        if m == n_months:
            capital = round(saldo, 2)
            interes = round(interes_total - interes_cuota * (n_months - 1), 2)
            cuota_m = round(capital + interes, 2)
            saldo = 0.0
        else:
            capital = capital_cuota
            interes = interes_cuota
            cuota_m = cuota
            saldo = round(saldo - capital, 2)
        capital_acum = round(capital_acum + capital, 2)
        filas.append(
            {
                "mes": m,
                "cuota": cuota_m,
                "interes": interes,
                "capital": capital,
                "saldo": saldo,
            }
        )

    diff = round(principal - capital_acum, 2)
    if diff != 0 and filas:
        filas[-1]["capital"] = round(filas[-1]["capital"] + diff, 2)
        filas[-1]["cuota"] = round(filas[-1]["capital"] + filas[-1]["interes"], 2)
        filas[-1]["saldo"] = 0.0

    total = round(sum(f["cuota"] for f in filas), 2)
    return cuota, filas, total


def simular_prestamo(
    principal: float,
    monthly_rate_pct: float = 15.0,
    term_months: int = DEFAULT_TERM_MONTHS,
    calc_type: CalcType = "FRENCH",
) -> dict[str, Any]:
    rate = monthly_rate_pct / 100.0
    if calc_type == "FLAT":
        cuota, filas, total = amortizacion_plana(principal, rate, term_months)
    else:
        cuota, filas, total = amortizacion_frances(principal, rate, term_months)

    interes_total = round(total - principal, 2)
    return {
        "principal": round(principal, 2),
        "monthly_rate_pct": monthly_rate_pct,
        "term_months": term_months,
        "calc_type": calc_type,
        "cuota_mensual": cuota,
        "interes_total": interes_total,
        "total_a_cobrar": total,
        "tabla_mensual": filas,
    }


def _daterange(start: date, end: date):
    d = start
    while d <= end:
        yield d
        d += timedelta(days=1)


def build_sweep_schedule(
    *,
    start: date,
    term_months: int,
    cuota_mensual: float,
    frequency: Frequency,
    avg_daily_sales: float = 0.0,
    custom_weekdays: list[int] | None = None,
) -> list[dict[str, Any]]:
    """
    Genera barridos esperados.
    custom_weekdays: 0=lun … 6=dom (ej. mar/jue = [1, 3]).
    """
    end = start + timedelta(days=term_months * 30)
    sweeps: list[dict[str, Any]] = []

    if frequency == "DAILY":
        objetivo = round(cuota_mensual / 30.0, 2)
        n = 0
        for d in _daterange(start, end - timedelta(days=1)):
            if d.weekday() >= 5:
                continue  # solo hábiles para barrido diario operativo
            n += 1
            ret = None
            if avg_daily_sales > 0:
                ret = round((objetivo / avg_daily_sales) * 100, 2)
            sweeps.append(
                {
                    "nro": n,
                    "due_date": d.isoformat(),
                    "expected_amount": objetivo,
                    "retention_pct": ret,
                    "kind": "daily",
                }
            )

    elif frequency == "WEEKLY":
        objetivo = round(cuota_mensual / 4.0, 2)
        # cada lunes
        d = start
        while d.weekday() != 0:
            d += timedelta(days=1)
        n = 0
        while d < end:
            n += 1
            sweeps.append(
                {
                    "nro": n,
                    "due_date": d.isoformat(),
                    "expected_amount": objetivo,
                    "retention_pct": None,
                    "kind": "weekly",
                }
            )
            d += timedelta(days=7)

    elif frequency == "BIWEEKLY":
        objetivo = round(cuota_mensual / 2.0, 2)
        n = 0
        y, m = start.year, start.month
        for _ in range(term_months):
            last = monthrange(y, m)[1]
            for day in (15, last):
                due = date(y, m, day)
                if due < start:
                    continue
                if due >= end:
                    break
                n += 1
                sweeps.append(
                    {
                        "nro": n,
                        "due_date": due.isoformat(),
                        "expected_amount": objetivo,
                        "retention_pct": None,
                        "kind": "biweekly",
                    }
                )
            if m == 12:
                y, m = y + 1, 1
            else:
                m += 1

    else:  # CUSTOM_DAYS
        days = custom_weekdays or [1, 3]  # mar/jue default
        # ~8 cobros/mes → objetivo = cuota/8
        objetivo = round(cuota_mensual / 8.0, 2)
        n = 0
        for d in _daterange(start, end - timedelta(days=1)):
            if d.weekday() in days:
                n += 1
                sweeps.append(
                    {
                        "nro": n,
                        "due_date": d.isoformat(),
                        "expected_amount": objetivo,
                        "retention_pct": None,
                        "kind": "custom",
                    }
                )

    return sweeps


def evaluar_retencion(
    objetivo_diario: float,
    avg_daily_sales: float,
) -> dict[str, Any]:
    if avg_daily_sales <= 0:
        return {
            "retention_pct": None,
            "alerta_retencion": True,
            "mensaje": "Falta venta diaria promedio para calcular retención.",
        }
    pct = round((objetivo_diario / avg_daily_sales) * 100, 2)
    alerta = pct > RETENTION_ALERT_PCT
    return {
        "retention_pct": pct,
        "alerta_retencion": alerta,
        "mensaje": (
            f"Retención {pct}% supera el umbral del {RETENTION_ALERT_PCT}%."
            if alerta
            else f"Retención estimada {pct}% (OK)."
        ),
    }


def sugerir_garantias(tax_status: str, has_echeq: bool) -> dict[str, Any]:
    """Matriz legal simplificada RI / Monotributo."""
    status = (tax_status or "").upper()
    if status in ("RI", "RESPONSABLE_INSCRIPTO", "RESPONSABLE INSCRIPTO"):
        if has_echeq:
            return {
                "principal": "ECHEQ",
                "respaldo": "FIANZA_SOCIO",
                "codeudor_obligatorio": False,
                "limite_reducido": False,
                "detalle": "RI con eCheq: eCheq diferido + fianza del socio/gerente.",
            }
        return {
            "principal": "PAGARE",
            "respaldo": "FIANZA_EMBARGO",
            "codeudor_obligatorio": False,
            "limite_reducido": False,
            "detalle": "RI sin eCheq: pagaré digital/físico + fianza y embargo de cuenta.",
        }
    # Monotributo
    if has_echeq:
        return {
            "principal": "ECHEQ",
            "respaldo": "CODEUDOR",
            "codeudor_obligatorio": True,
            "limite_reducido": False,
            "detalle": "Monotributo con eCheq: eCheq + codeudor solidario.",
        }
    return {
        "principal": "PAGARE",
        "respaldo": "CODEUDOR",
        "codeudor_obligatorio": True,
        "limite_reducido": True,
        "detalle": "Monotributo sin eCheq: pagaré + codeudor obligatorio + límite reducido.",
    }


def comparar_metodos(
    principal: float,
    monthly_rate_pct: float = 15.0,
    term_months: int = 3,
) -> dict[str, Any]:
    flat = simular_prestamo(principal, monthly_rate_pct, term_months, "FLAT")
    french = simular_prestamo(principal, monthly_rate_pct, term_months, "FRENCH")
    return {
        "flat": flat,
        "french": french,
        "ahorro_interes_french": round(flat["interes_total"] - french["interes_total"], 2),
    }


def procesar_dia_sweep(
    *,
    expected: float,
    collected: float,
    used_grace_days: int,
    sales_today: float,
    is_peak_day: bool,
    day_of_month: int,
    auto_recovery_active: bool,
) -> dict[str, Any]:
    """
    Evalúa un día de cobro (motor interno).
    Grace days: hasta 3/mes sin mora visible si collected==0 y sales bajas.
    """
    status = "PAID"
    penalty = 0.0
    new_grace = used_grace_days
    recovery = auto_recovery_active
    fraud_alert = False
    notes: list[str] = []

    if collected + 0.01 >= expected:
        status = "PAID"
    elif collected > 0:
        status = "PARTIAL"
    else:
        # posible uso de respiro
        if sales_today <= 0 and used_grace_days < MAX_GRACE_DAYS_PER_MONTH:
            new_grace = used_grace_days + 1
            status = "PENDING"  # no OVERDUE por respiro interno
            notes.append("grace_day_consumed")
        else:
            status = "OVERDUE"
            notes.append("missed_sweep")

    if is_peak_day and sales_today <= 0:
        fraud_alert = True
        notes.append("peak_day_zero_sales")

    # Auto-recuperación desde día 20
    if day_of_month >= 20 and status in ("PARTIAL", "OVERDUE", "PENDING"):
        recovery = True
        notes.append("auto_recovery_on")

    return {
        "status": status,
        "penalty_fee": penalty,
        "used_grace_days": new_grace,
        "auto_recovery_active": recovery,
        "fraud_alert": fraud_alert,
        "notes": notes,
    }
