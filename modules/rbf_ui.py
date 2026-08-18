"""
UI — Préstamo al comercio (cobro por porcentaje de ventas).
"""

from __future__ import annotations

import json
from datetime import date, datetime

import pandas as pd
import streamlit as st

from modules.database import (
    get_rbf_grace,
    get_rbf_loan,
    get_rbf_merchant,
    insert_rbf_loan,
    insert_rbf_merchant,
    list_mp_sales,
    list_rbf_loans,
    list_rbf_merchants,
    list_rbf_sweeps,
    rbf_loan_progress,
    update_rbf_grace,
    update_rbf_loan_status,
    update_rbf_sweep,
)
from modules import mercadopago
from modules.rbf_engine import (
    RETENTION_ALERT_PCT,
    build_sweep_schedule,
    comparar_metodos,
    evaluar_retencion,
    procesar_dia_sweep,
    simular_prestamo,
    sugerir_garantias,
)
from modules.traceability import crear_operacion
from modules.ui import fmt_ars, kpi_card, result_strip


def render_rbf() -> None:
    st.header("Préstamo al comercio")
    st.caption(
        "Prestás al local y cobrás en la caja: el cliente paga ahí mismo con Mercado Pago "
        "(QR o link). La venta se parte sola. Firmar en Trazabilidad antes de desembolsar."
    )
    tab_sim, tab_alta, tab_cart, tab_mp = st.tabs(
        ["Simular", "Alta préstamo", "Cartera & cobros", "Cobro en el local"]
    )
    with tab_sim:
        _render_sim()
    with tab_alta:
        _render_alta()
    with tab_cart:
        _render_cartera()
    with tab_mp:
        _render_cobro_local()


def _render_sim() -> None:
    c1, c2 = st.columns(2)
    with c1:
        principal = st.number_input(
            "Capital (ARS)",
            min_value=0.0,
            value=1_000_000.0,
            step=50_000.0,
            format="%.2f",
            key="rbf_sim_p",
        )
        rate = st.number_input(
            "Tasa mensual (%)",
            min_value=0.0,
            value=15.0,
            step=0.5,
            key="rbf_sim_r",
        )
        months = st.number_input("Plazo (meses)", min_value=1, value=3, key="rbf_sim_m")
        avg_sales = st.number_input(
            "Venta diaria promedio (ARS)",
            min_value=0.0,
            value=80_000.0,
            step=5_000.0,
            key="rbf_sim_avg",
        )
    with c2:
        freq = st.selectbox(
            "Frecuencia de barrido",
            options=["DAILY", "WEEKLY", "BIWEEKLY", "CUSTOM_DAYS"],
            format_func=lambda x: {
                "DAILY": "Diario (hábil)",
                "WEEKLY": "Semanal (lunes)",
                "BIWEEKLY": "Quincenal (15 y fin de mes)",
                "CUSTOM_DAYS": "Días específicos (mar/jue)",
            }[x],
            key="rbf_sim_freq",
        )
        start = st.date_input("Inicio", value=date.today(), key="rbf_sim_start")

    if principal <= 0:
        st.warning("Ingresá un capital.")
        return

    comp = comparar_metodos(principal, rate, int(months))
    flat, french = comp["flat"], comp["french"]

    k1, k2, k3 = st.columns(3)
    with k1:
        kpi_card("Francés · cuota/mes", fmt_ars(french["cuota_mensual"]), "Recomendado")
    with k2:
        kpi_card("Francés · total", fmt_ars(french["total_a_cobrar"]), f"Interés {fmt_ars(french['interes_total'])}")
    with k3:
        kpi_card(
            "Plana · total",
            fmt_ars(flat["total_a_cobrar"]),
            f"Interés {fmt_ars(flat['interes_total'])} · +{fmt_ars(comp['ahorro_interes_french'])} vs francés",
        )

    st.subheader("Tabla francesa")
    st.dataframe(
        pd.DataFrame(french["tabla_mensual"]).rename(
            columns={
                "mes": "Mes",
                "cuota": "Cuota",
                "interes": "Interés",
                "capital": "Capital",
                "saldo": "Saldo",
            }
        ),
        use_container_width=True,
        hide_index=True,
        column_config={
            "Cuota": st.column_config.NumberColumn(format="$ %.2f"),
            "Interés": st.column_config.NumberColumn(format="$ %.2f"),
            "Capital": st.column_config.NumberColumn(format="$ %.2f"),
            "Saldo": st.column_config.NumberColumn(format="$ %.2f"),
        },
    )

    objetivo_dia = round(french["cuota_mensual"] / 30.0, 2)
    ret = evaluar_retencion(objetivo_dia, avg_sales)
    result_strip(
        [
            ("Objetivo diario", fmt_ars(objetivo_dia)),
            ("Retención est.", f"{ret['retention_pct']}%" if ret["retention_pct"] is not None else "—"),
            ("Umbral alerta", f"{RETENTION_ALERT_PCT}%"),
        ]
    )
    if ret["alerta_retencion"]:
        st.error(ret["mensaje"])
    else:
        st.success(ret["mensaje"])

    sweeps = build_sweep_schedule(
        start=start,
        term_months=int(months),
        cuota_mensual=french["cuota_mensual"],
        frequency=freq,  # type: ignore[arg-type]
        avg_daily_sales=avg_sales,
    )
    st.subheader(f"Cronograma de barridos ({len(sweeps)} cobros)")
    if sweeps:
        st.dataframe(
            pd.DataFrame(sweeps[:60]),
            use_container_width=True,
            hide_index=True,
            column_config={
                "expected_amount": st.column_config.NumberColumn("Esperado", format="$ %.2f"),
                "retention_pct": st.column_config.NumberColumn("Retención %", format="%.2f"),
            },
        )
        if len(sweeps) > 60:
            st.caption(f"Mostrando 60 de {len(sweeps)} barridos.")


def _render_alta() -> None:
    st.subheader("Comercio")
    merchants = list_rbf_merchants()
    mode = st.radio("Comercio", ["Nuevo", "Existente"], horizontal=True, key="rbf_mer_mode")

    merchant_id: int | None = None
    if mode == "Existente" and merchants:
        opts = {
            f"#{m['id']} · {m['business_name']} · {m.get('tax_id_cuit') or ''}": m["id"]
            for m in merchants
        }
        sel = st.selectbox("Elegir", list(opts.keys()), key="rbf_mer_sel")
        merchant_id = opts[sel]
        mer = next(m for m in merchants if m["id"] == merchant_id)
        email = mer.get("email") or ""
        phone = mer.get("phone") or ""
        tax_status = mer.get("tax_status") or "MONOTRIBUTO"
        has_echeq = bool(mer.get("has_echeq"))
        avg_sales = float(mer.get("avg_daily_sales") or 0)
        cuit = mer.get("tax_id_cuit") or ""
        nombre = mer["business_name"]
    else:
        nombre = st.text_input("Razón social / nombre *", key="rbf_new_name")
        cuit = st.text_input("CUIT", key="rbf_new_cuit")
        tax_status = st.selectbox(
            "Perfil fiscal",
            ["MONOTRIBUTO", "RI"],
            format_func=lambda x: "Monotributista" if x == "MONOTRIBUTO" else "Responsable Inscripto",
            key="rbf_tax",
        )
        has_echeq = st.checkbox("Tiene eCheq / chequera", key="rbf_echeq")
        avg_sales = st.number_input(
            "Venta diaria promedio",
            min_value=0.0,
            value=80_000.0,
            step=5_000.0,
            key="rbf_avg",
        )
        cbu = st.text_input("CBU/CVU", key="rbf_cbu")
        email = st.text_input("Email firmante *", key="rbf_email")
        phone = st.text_input("Teléfono", key="rbf_phone")

    st.subheader("Préstamo")
    p1, p2, p3 = st.columns(3)
    with p1:
        principal = st.number_input(
            "Capital *",
            min_value=0.0,
            value=1_000_000.0,
            step=50_000.0,
            key="rbf_prin",
        )
    with p2:
        rate = st.number_input("Tasa % mensual", min_value=0.0, value=15.0, step=0.5, key="rbf_rate")
    with p3:
        months = st.number_input("Meses", min_value=1, value=3, key="rbf_months")

    calc_type = st.radio(
        "Método",
        ["FRENCH", "FLAT"],
        format_func=lambda x: "Francés (recomendado)" if x == "FRENCH" else "Tasa plana",
        horizontal=True,
        key="rbf_calc",
    )
    freq = st.selectbox(
        "Barrido",
        ["DAILY", "WEEKLY", "BIWEEKLY", "CUSTOM_DAYS"],
        format_func=lambda x: {
            "DAILY": "Diario",
            "WEEKLY": "Semanal",
            "BIWEEKLY": "Quincenal",
            "CUSTOM_DAYS": "Mar/Jue",
        }[x],
        key="rbf_freq",
    )
    start = st.date_input("Inicio", value=date.today(), key="rbf_start")

    if principal <= 0:
        return

    sim = simular_prestamo(principal, rate, int(months), calc_type)  # type: ignore[arg-type]
    garant = sugerir_garantias(tax_status, has_echeq)
    ret = evaluar_retencion(sim["cuota_mensual"] / 30.0, avg_sales)

    kpi_card("Total a cobrar", fmt_ars(sim["total_a_cobrar"]), f"Cuota mes {fmt_ars(sim['cuota_mensual'])}")
    st.info(garant["detalle"])
    if garant["limite_reducido"]:
        st.warning("Perfil con límite de crédito reducido (monotributo sin eCheq).")
    if ret["alerta_retencion"]:
        st.error(ret["mensaje"])

    if st.button("Registrar préstamo + expediente", type="primary", key="rbf_crear"):
        if mode == "Nuevo":
            if not nombre.strip():
                st.error("Nombre obligatorio.")
                return
            if not email.strip():
                st.error("Email obligatorio (firma).")
                return
            merchant_id = insert_rbf_merchant(
                {
                    "business_name": nombre.strip(),
                    "tax_id_cuit": cuit.strip(),
                    "tax_status": tax_status,
                    "has_echeq": has_echeq,
                    "avg_daily_sales": avg_sales,
                    "bank_cbu": st.session_state.get("rbf_cbu", ""),
                    "email": email.strip(),
                    "phone": phone.strip(),
                }
            )
        assert merchant_id is not None

        sweeps = build_sweep_schedule(
            start=start,
            term_months=int(months),
            cuota_mensual=sim["cuota_mensual"],
            frequency=freq,  # type: ignore[arg-type]
            avg_daily_sales=avg_sales,
        )
        guarantees = [
            {
                "type": garant["principal"],
                "identifier": "",
                "amount_covered": sim["total_a_cobrar"],
            },
            {
                "type": garant["respaldo"],
                "identifier": "",
                "amount_covered": sim["total_a_cobrar"],
            },
        ]

        exp_id = crear_operacion(
            "rbf",
            nombre.strip() if mode == "Nuevo" else next(
                m["business_name"] for m in list_rbf_merchants() if m["id"] == merchant_id
            ),
            principal,
            cuit=cuit.strip(),
            email_firmante=email.strip(),
            telefono_firmante=phone.strip(),
            payload={
                "calc_type": calc_type,
                "frequency": freq,
                "monthly_rate": rate,
                "term_months": int(months),
                "garantias": garant,
            },
        )

        loan_id = insert_rbf_loan(
            {
                "merchant_id": merchant_id,
                "principal": principal,
                "monthly_rate": rate,
                "term_months": int(months),
                "calc_type": calc_type,
                "frequency": freq,
                "cuota_mensual": sim["cuota_mensual"],
                "total_a_cobrar": sim["total_a_cobrar"],
                "interes_total": sim["interes_total"],
                "status": "ACTIVE",
                "start_date": start.isoformat(),
                "operacion_id": exp_id,
                "payload_json": json.dumps(
                    {"tabla": sim["tabla_mensual"], "garantias": garant},
                    ensure_ascii=False,
                    default=str,
                ),
                "creado_en": datetime.now().isoformat(timespec="seconds"),
            },
            sweeps,
            guarantees,
        )
        st.success(
            f"Préstamo #{loan_id} · expediente #{exp_id} · "
            f"{len(sweeps)} barridos. Generá el contrato y firmá en **Trazabilidad** "
            "antes de desembolsar."
        )


def _render_cartera() -> None:
    loans = list_rbf_loans()
    if not loans:
        st.info("Sin préstamos al comercio. Creá uno en Alta.")
        return

    st.dataframe(
        pd.DataFrame(
            [
                {
                    "ID": l["id"],
                    "Comercio": l["business_name"],
                    "Capital": l["principal"],
                    "Total": l["total_a_cobrar"],
                    "Método": l["calc_type"],
                    "Barrido": l["frequency"],
                    "Estado": l["status"],
                    "Inicio": l["start_date"],
                }
                for l in loans
            ]
        ),
        use_container_width=True,
        hide_index=True,
        column_config={
            "Capital": st.column_config.NumberColumn(format="$ %.2f"),
            "Total": st.column_config.NumberColumn(format="$ %.2f"),
        },
    )

    opts = {f"#{l['id']} · {l['business_name']} · {l['status']}": l["id"] for l in loans}
    sel = st.selectbox("Abrir préstamo", list(opts.keys()), key="rbf_loan_sel")
    loan_id = opts[sel]
    loan = get_rbf_loan(loan_id)
    if not loan:
        return

    prog = rbf_loan_progress(loan_id)
    result_strip(
        [
            ("Cobrado", fmt_ars(prog["collected"])),
            ("Esperado", fmt_ars(prog["expected"])),
            ("Barridos OK", f"{prog['paid']}/{prog['total']}"),
        ]
    )

    month_key = date.today().strftime("%Y-%m")
    grace = get_rbf_grace(loan_id, month_key)
    st.caption(
        f"Control interno mes {month_key}: respiro usado "
        f"{grace.get('used_grace_days_count', 0)}/3 · "
        f"auto-recuperación={'ON' if grace.get('auto_recovery_active') else 'OFF'}"
    )

    sweeps = list_rbf_sweeps(loan_id)
    st.dataframe(
        pd.DataFrame(sweeps),
        use_container_width=True,
        hide_index=True,
        column_config={
            "expected_amount": st.column_config.NumberColumn(format="$ %.2f"),
            "collected_amount": st.column_config.NumberColumn(format="$ %.2f"),
            "penalty_fee": st.column_config.NumberColumn(format="$ %.2f"),
        },
    )

    pending = [s for s in sweeps if s["status"] in ("PENDING", "PARTIAL", "OVERDUE")]
    if pending:
        st.subheader("Registrar cobro de barrido (manual v1)")
        popts = {
            f"#{s['nro']} · {s['due_date']} · {fmt_ars(s['expected_amount'])} · {s['status']}": s
            for s in pending[:40]
        }
        pick = st.selectbox("Barrido", list(popts.keys()), key="rbf_sw_pick")
        sw = popts[pick]
        collected = st.number_input(
            "Monto cobrado",
            min_value=0.0,
            value=float(sw["expected_amount"]),
            step=100.0,
            key="rbf_sw_amt",
        )
        sales_today = st.number_input(
            "Venta digital del día (para riesgo)",
            min_value=0.0,
            value=float(loan.get("avg_daily_sales") or 0),
            key="rbf_sw_sales",
        )
        peak = st.checkbox("¿Día pico (vie/sáb)?", key="rbf_peak")

        if st.button("Aplicar cobro", type="primary", key="rbf_sw_go"):
            day = date.today().day
            used = int(grace.get("used_grace_days_count") or 0)
            auto = bool(grace.get("auto_recovery_active"))
            result = procesar_dia_sweep(
                expected=float(sw["expected_amount"]),
                collected=collected,
                used_grace_days=used,
                sales_today=sales_today,
                is_peak_day=peak,
                day_of_month=day,
                auto_recovery_active=auto,
            )
            # Si hay cobro parcial/total, status del engine; si grace sin cobro queda PENDING
            status = result["status"]
            if collected + 0.01 >= float(sw["expected_amount"]):
                status = "PAID"
            elif collected > 0:
                status = "PARTIAL"

            update_rbf_sweep(
                int(sw["id"]),
                collected_amount=collected,
                status=status,
                penalty_fee=float(result["penalty_fee"]),
            )
            update_rbf_grace(
                loan_id,
                month_key,
                int(result["used_grace_days"]),
                bool(result["auto_recovery_active"]),
            )
            if result["fraud_alert"]:
                st.error("Alerta fraude: día pico con venta digital $0.")
            st.success(f"Barrido actualizado → {status}")
            st.rerun()

    st.subheader("Estado del préstamo")
    new_status = st.selectbox(
        "Cambiar estado",
        ["ACTIVE", "OVERDUE", "IN_DEFAULT", "PAID"],
        index=["ACTIVE", "OVERDUE", "IN_DEFAULT", "PAID"].index(loan["status"])
        if loan["status"] in ("ACTIVE", "OVERDUE", "IN_DEFAULT", "PAID")
        else 0,
        key="rbf_st",
    )
    if st.button("Actualizar estado", key="rbf_st_btn"):
        update_rbf_loan_status(loan_id, new_status)
        if new_status == "IN_DEFAULT":
            st.warning(
                "IN_DEFAULT: generar paquete ejecutivo (pagaré/eCheq) desde Trazabilidad / estudio."
            )
        st.success(f"Estado → {new_status}")
        st.rerun()


def _render_cobro_local() -> None:
    """El cliente paga en la caja con Mercado Pago; Finan se queda la retención."""
    st.subheader("Cobrar una venta en el local")
    st.markdown(
        "El cliente **no se lleva un link a la casa**. Paga en el mostrador: el cajero "
        "abre el checkout de Mercado Pago (QR o celular) y la venta se parte sola."
    )

    st.info(
        "**Ejemplo real.** Prestaste **$1.000.000** a la panadería. Pactaste **15%** de cada cobro. "
        "Entra un cliente, pide facturas por **$10.000** y paga con Mercado Pago en la caja. "
        "Vos te quedás **$1.500**. Al local le queda **$8.500** menos la comisión de Mercado Pago "
        "(si pagó con crédito al instante, Mercado Pago se lleva ~6,29% + IVA sobre los $10.000). "
        "El cliente se va con el pan. Nadie transfiere después."
    )

    if not mercadopago.is_configured():
        st.warning(
            "Faltan las credenciales de Mercado Pago. Cargalas en **Trazabilidad → Signatura / Config** "
            "(abajo, sección Mercado Pago). Creá la app en "
            "[tus integraciones](https://www.mercadopago.com.ar/developers/panel/app) "
            "y poné como URL de redirección exactamente: "
            f"`{mercadopago.get_redirect_uri()}`"
        )
        return

    merchants = list_rbf_merchants()
    if not merchants:
        st.info("Primero cargá un comercio en **Alta préstamo**.")
        return

    labels = {f"#{m['id']} · {m['business_name']}": m["id"] for m in merchants}
    pick = st.selectbox("Comercio", list(labels.keys()), key="mp_merch")
    merchant_id = labels[pick]
    merchant = get_rbf_merchant(merchant_id)
    loans = [
        l
        for l in list_rbf_loans()
        if l["merchant_id"] == merchant_id and l["status"] in ("ACTIVE", "OVERDUE")
    ]

    linked = mercadopago.merchant_linked(merchant)
    if linked:
        st.success(
            f"Mercado Pago vinculado"
            + (f" · {merchant.get('mp_linked_en')}" if merchant and merchant.get("mp_linked_en") else "")
        )
    else:
        st.error("Este local todavía no autorizó a Finan a cobrar sobre su Mercado Pago.")
        try:
            url = mercadopago.authorization_url(merchant_id)
            st.link_button(
                "Vincular cuenta de Mercado Pago del local",
                url,
                type="primary",
                use_container_width=True,
            )
            st.caption(
                "Se abre Mercado Pago. El dueño entra con la cuenta del local y acepta. "
                "Vuelve a esta pantalla ya vinculado."
            )
        except mercadopago.MercadoPagoError as exc:
            st.error(str(exc))
        return

    if not loans:
        st.warning("Este comercio no tiene un préstamo activo. Creá uno en Alta.")
        return

    loan_labels = {
        f"#{l['id']} · capital {fmt_ars(l['principal'])} · {l['status']}": l["id"] for l in loans
    }
    loan_pick = st.selectbox("Préstamo a cobrar", list(loan_labels.keys()), key="mp_loan")
    loan = get_rbf_loan(loan_labels[loan_pick])
    if not loan:
        return

    ret = evaluar_retencion(
        float(loan["cuota_mensual"]) / 30.0,
        float(loan.get("avg_daily_sales") or 0),
    )
    default_pct = float(ret.get("retention_pct") or 15.0)
    if default_pct <= 0:
        default_pct = 15.0

    c1, c2 = st.columns(2)
    with c1:
        venta = st.number_input(
            "Lo que el cliente está pagando ahora en la caja (ARS)",
            min_value=1.0,
            value=10_000.0,
            step=500.0,
            key="mp_venta",
        )
    with c2:
        pct = st.number_input(
            "% que se queda Finan de esa venta",
            min_value=1.0,
            max_value=40.0,
            value=min(default_pct, 40.0),
            step=0.5,
            key="mp_pct",
        )

    partes = mercadopago.split_de_venta(venta, pct)
    result_strip(
        [
            ("Cliente paga", fmt_ars(partes["venta"])),
            ("A Finan", fmt_ars(partes["finan"])),
            ("Al local (antes de comisión MP)", fmt_ars(partes["comercio_antes_mp"])),
        ]
    )
    st.caption(ret.get("mensaje") or "")

    if st.button("Generar cobro de caja (link / QR Mercado Pago)", type="primary", key="mp_crear"):
        try:
            cobro = mercadopago.crear_cobro_local(
                merchant_id=merchant_id,
                loan_id=int(loan["id"]),
                monto_venta=venta,
                retencion_pct=pct,
                titulo=f"Venta {loan['business_name']}",
            )
            st.session_state["mp_last_init"] = cobro["init_point"]
            st.success(
                f"Listo. El cliente paga {fmt_ars(cobro['venta'])} en la caja. "
                f"Finan se queda {fmt_ars(cobro['finan'])}."
            )
        except mercadopago.MercadoPagoError as exc:
            st.error(str(exc))

    last = st.session_state.get("mp_last_init")
    if last:
        st.link_button("Abrir checkout para que pague el cliente", last, use_container_width=True)
        st.code(last, language=None)

    sales = list_mp_sales(int(loan["id"]))
    if not sales:
        return

    st.subheader("Ventas de este préstamo")
    st.dataframe(
        pd.DataFrame(
            [
                {
                    "ID": s["id"],
                    "Venta": s["sale_amount"],
                    "A Finan": s["finan_amount"],
                    "%": s["retention_pct"],
                    "Estado": s["status"],
                    "Cuando": s["creado_en"],
                }
                for s in sales
            ]
        ),
        use_container_width=True,
        hide_index=True,
        column_config={
            "Venta": st.column_config.NumberColumn(format="$ %.2f"),
            "A Finan": st.column_config.NumberColumn(format="$ %.2f"),
        },
    )

    pendientes = [s for s in sales if s["status"] != "cobrada"]
    if not pendientes:
        return
    popts = {f"#{s['id']} · {fmt_ars(s['sale_amount'])} · {s['status']}": s["id"] for s in pendientes}
    sid = st.selectbox("Si el cliente ya pagó, sincronizar", list(popts.keys()), key="mp_sync_sel")
    if st.button("Consultar en Mercado Pago y acreditar", key="mp_sync"):
        try:
            res = mercadopago.sincronizar_cobro(int(popts[sid]))
            if res.get("ya_estaba"):
                st.info("Esa venta ya estaba acreditada.")
            elif not res.get("encontrado") and res.get("status") == "pendiente":
                st.warning("Todavía no hay un pago aprobado. Que el cliente termine en la caja.")
            elif res.get("status") == "cobrada":
                ap = res.get("aplicado") or {}
                st.success(
                    f"Pago aprobado. Se acreditaron {fmt_ars(ap.get('aplicado', 0))} "
                    f"a los barridos del préstamo."
                )
                st.rerun()
            else:
                st.warning(f"Mercado Pago informa estado: {res.get('status')}")
        except mercadopago.MercadoPagoError as exc:
            st.error(str(exc))
