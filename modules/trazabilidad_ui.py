"""
UI de trazabilidad + configuración Signatura Flex.
"""

from __future__ import annotations

import json

import pandas as pd
import streamlit as st

from modules import signatura
from modules.checklist import get_checklist, save_checklist
from modules.database import get_operacion, list_operaciones
from modules.documents import TEMPLATE_VERSION, generar_pdf_operacion, nombre_plantilla
from modules.legajo import build_legajo_zip
from modules.signatura import SignaturaError
from modules.traceability import (
    ESTADOS,
    TIPOS,
    TIPOS_ACTIVOS,
    marcar_desembolsado,
    resumen_cartera_trazabilidad,
    sincronizar_firma,
    timeline,
    transicionar,
    enviar_a_firmar,
)
from modules.ui import fmt_ars, kpi_card


def render_trazabilidad() -> None:
    st.header("Trazabilidad")
    st.caption(
        f"Expediente · préstamo al comercio · crédito al cliente · firma Signatura · "
        f"plantillas {TEMPLATE_VERSION}"
    )

    tab_ops, tab_cfg = st.tabs(["Expedientes", "Signatura / Config"])

    with tab_cfg:
        _render_config()

    with tab_ops:
        _render_ops()


def _render_config() -> None:
    st.subheader("Signatura Flex")
    st.markdown(
        "Alta y créditos: [signatura.co/flex-plan](https://signatura.co/flex-plan) · "
        "API key: [connect.signatura.co](https://connect.signatura.co)"
    )

    configured = signatura.is_configured()
    st.write("Estado API:", "✅ configurada" if configured else "⚠️ falta API key")

    api_key = st.text_input(
        "API key Signatura",
        type="password",
        value="",
        help="Se guarda en finan.db (app_settings). También podés usar SIGNATURA_API_KEY.",
        key="sig_api_key",
    )
    c1, c2 = st.columns(2)
    with c1:
        if st.button("Guardar API key", type="primary", key="sig_save"):
            if not api_key.strip():
                st.error("Pegá la key.")
            else:
                signatura.save_api_key(api_key.strip())
                st.success("API key guardada.")
                st.rerun()
    with c2:
        if st.button("Probar conexión", key="sig_test"):
            try:
                signatura.list_documents()
                st.success("Conexión OK con Signatura.")
            except SignaturaError as exc:
                st.error(str(exc))

    st.info(
        "Flujo: crear expediente → PDF → Enviar a Signatura → Sync firma → "
        "Desembolsar (solo si listo_desembolso)."
    )


def _render_ops() -> None:
    resumen = resumen_cartera_trazabilidad()
    k1, k2, k3, k4 = st.columns(4)
    with k1:
        kpi_card("Expedientes", str(resumen["total"]), "Todos los tipos")
    with k2:
        kpi_card(
            "Pendiente firma",
            fmt_ars(resumen["monto_pendiente_firma"]),
            f"{resumen['by_estado'].get('pendiente_firma', 0)} ops",
        )
    with k3:
        kpi_card(
            "Listo desembolso",
            fmt_ars(resumen["monto_listo_desembolso"]),
            f"{resumen['by_estado'].get('listo_desembolso', 0)} ops",
        )
    with k4:
        firmados = resumen["by_estado"].get("firmado", 0) + resumen["by_estado"].get(
            "listo_desembolso", 0
        )
        kpi_card("Post-firma", str(firmados), "firmado + listo")

    f1, f2 = st.columns(2)
    with f1:
        filtro_tipo = st.selectbox(
            "Tipo",
            options=["todos"] + list(TIPOS_ACTIVOS) + [
                k for k in TIPOS if k not in TIPOS_ACTIVOS
            ],
            format_func=lambda x: "Todos" if x == "todos" else TIPOS.get(x, x),
            key="tr_tipo",
        )
    with f2:
        filtro_estado = st.selectbox(
            "Estado",
            options=["todos"] + ESTADOS,
            key="tr_estado",
        )

    ops = list_operaciones(
        estado=None if filtro_estado == "todos" else filtro_estado,
        tipo=None if filtro_tipo == "todos" else filtro_tipo,
    )

    if not ops:
        st.info(
            "Todavía no hay expedientes. Registrá un préstamo al comercio o un crédito "
            "al cliente: se abre el expediente en borrador. Después generá el PDF, "
            "envialo a firmar y recién ahí desembolsá."
        )
        return

    df = pd.DataFrame(
        [
            {
                "ID": o["id"],
                "Tipo": TIPOS.get(o["tipo"], o["tipo"]),
                "Comercio": o["comercio"],
                "Monto": o["monto"],
                "Estado": o["estado"],
                "Signatura": o.get("signatura_doc_id") or "—",
                "Hash": (o.get("doc_hash_sha256") or "—")[:12],
                "Actualizado": o.get("actualizado_en"),
            }
            for o in ops
        ]
    )
    st.dataframe(
        df,
        use_container_width=True,
        hide_index=True,
        column_config={"Monto": st.column_config.NumberColumn(format="$ %.2f")},
    )

    ids = {f"#{o['id']} · {o['comercio']} · {o['estado']}": o["id"] for o in ops}
    seleccion = st.selectbox("Abrir expediente", options=list(ids.keys()), key="tr_sel")
    op = get_operacion(ids[seleccion])
    if not op:
        return

    st.subheader(f"Expediente #{op['id']}")
    plantilla = nombre_plantilla(op.get("tipo") or "")
    st.caption(f"Plantilla contractual: **{plantilla}**")
    st.write(
        {
            "tipo": op["tipo"],
            "estado": op["estado"],
            "comercio": op["comercio"],
            "cuit": op["cuit"],
            "monto": op["monto"],
            "signatura_doc_id": op.get("signatura_doc_id"),
            "signatura_status": op.get("signatura_status"),
            "doc_hash_sha256": op.get("doc_hash_sha256"),
            "template": TEMPLATE_VERSION,
        }
    )

    st.markdown("##### Checklist pre-desembolso")
    chk = get_checklist(op["id"])
    checks_ui: dict[str, bool] = {}
    for item in chk["items"]:
        checks_ui[item["id"]] = st.checkbox(
            item["label"],
            value=item["ok"],
            key=f"chk_{op['id']}_{item['id']}",
        )
    c_save, c_status = st.columns([1, 2])
    with c_save:
        if st.button("Guardar checklist", key="tr_chk_save"):
            save_checklist(op["id"], checks_ui)
            st.success("Checklist guardado.")
            st.rerun()
    with c_status:
        if chk["puede_desembolsar"]:
            st.success("Listo para desembolsar (firma + checklist OK).")
        elif chk["all_ok"] and not chk["firma_lista"]:
            st.warning("Checklist OK · falta firma completa (estado listo_desembolso).")
        elif chk["firma_lista"] and not chk["all_ok"]:
            st.warning("Firma lista · falta completar checklist.")
        else:
            st.info("Completá checklist y firma antes de desembolsar.")

    a1, a2, a3, a4 = st.columns(4)

    with a1:
        if st.button("Generar PDF + enviar Signatura", type="primary", key="tr_send"):
            try:
                if not op.get("email_firmante") and not op.get("telefono_firmante"):
                    st.error("Falta email o teléfono del firmante en el expediente.")
                else:
                    pdf = generar_pdf_operacion(op)
                    result = enviar_a_firmar(
                        op["id"],
                        pdf,
                        title=f"Finan {op['tipo']} #{op['id']} · {TEMPLATE_VERSION}",
                    )
                    st.success(f"Enviado. Signatura doc: {result['signatura_doc_id']}")
                    st.rerun()
            except (SignaturaError, ValueError) as exc:
                st.error(str(exc))

    with a2:
        if st.button("Sync estado firma", key="tr_sync"):
            try:
                sync = sincronizar_firma(op["id"])
                st.success(f"Estado ahora: {sync.get('estado')} / {sync.get('signatura_status')}")
                st.rerun()
            except (SignaturaError, ValueError) as exc:
                st.error(str(exc))

    with a3:
        if st.button("Desembolsar", key="tr_disb"):
            try:
                # Persistir checks actuales de la UI antes de validar
                save_checklist(op["id"], checks_ui)
                marcar_desembolsado(op["id"], referencia="manual_ui")
                st.success("Marcado como desembolsado.")
                st.rerun()
            except ValueError as exc:
                st.error(str(exc))

    with a4:
        destino = st.selectbox(
            "Transición manual",
            options=sorted(
                {
                    "cancelado",
                    "cobrado",
                    "en_mora",
                    "chargeback",
                    "listo_desembolso",
                    "firmado",
                }
            ),
            key="tr_manual_state",
        )
        if st.button("Aplicar", key="tr_apply"):
            try:
                transicionar(op["id"], destino, nota="manual_ui")
                st.success(f"Estado → {destino}")
                st.rerun()
            except ValueError as exc:
                st.error(str(exc))

    st.markdown("##### Timeline (audit log)")
    events = timeline(op["id"])
    if not events:
        st.caption("Sin eventos.")
    else:
        rows = []
        for e in events:
            rows.append(
                {
                    "UTC": e["created_at_utc"],
                    "Evento": e["event_type"],
                    "Detalle": json.dumps(e["payload"], ensure_ascii=False)[:120],
                    "Hash": e["event_hash"][:16],
                    "Prev": e["prev_hash"][:16],
                }
            )
        st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)

    d1, d2 = st.columns(2)
    with d1:
        pdf_dl = generar_pdf_operacion(op)
        st.download_button(
            f"Descargar contrato PDF ({TEMPLATE_VERSION})",
            data=pdf_dl,
            file_name=f"finan_{op.get('tipo')}_op_{op['id']}_{TEMPLATE_VERSION}.pdf",
            mime="application/pdf",
            key="tr_dl_pdf",
        )
    with d2:
        try:
            zip_bytes, zip_name = build_legajo_zip(op["id"])
            st.download_button(
                "Descargar legajo completo (.zip)",
                data=zip_bytes,
                file_name=zip_name,
                mime="application/zip",
                key="tr_dl_zip",
            )
        except Exception as exc:  # noqa: BLE001
            st.caption(f"Legajo no disponible: {exc}")

