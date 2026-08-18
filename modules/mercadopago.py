"""
Mercado Pago: vincular comercio (OAuth) y cobrar en el local con split.

El cliente paga en la caja con el checkout de Mercado Pago.
Mercado Pago se queda su comisión, Finan se queda la retención del préstamo,
el local recibe el resto.

Docs:
  OAuth: https://www.mercadopago.com.ar/developers/es/docs/security/oauth/creation
  Split: https://www.mercadopago.com.ar/developers/es/docs/split-payments/landing
"""

from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone
from typing import Any, Optional
from urllib.parse import urlencode
from uuid import uuid4

import requests
import streamlit as st

from modules.database import (
    aplicar_cobro_sweeps,
    get_mp_sale,
    get_rbf_merchant,
    get_setting,
    insert_mp_sale,
    save_rbf_merchant_mp_tokens,
    set_setting,
    update_mp_sale,
)

AUTH_URL = "https://auth.mercadopago.com/authorization"
TOKEN_URL = "https://api.mercadopago.com/oauth/token"
API_BASE = "https://api.mercadopago.com"

KEY_CLIENT_ID = "mp_client_id"
KEY_CLIENT_SECRET = "mp_client_secret"
KEY_REDIRECT = "mp_redirect_uri"


class MercadoPagoError(Exception):
    """Error de configuración o de la API de Mercado Pago."""


def get_client_id() -> str:
    env = (os.environ.get("MP_CLIENT_ID") or "").strip()
    return env or (get_setting(KEY_CLIENT_ID) or "").strip()


def get_client_secret() -> str:
    env = (os.environ.get("MP_CLIENT_SECRET") or "").strip()
    return env or (get_setting(KEY_CLIENT_SECRET) or "").strip()


def get_redirect_uri() -> str:
    env = (os.environ.get("MP_REDIRECT_URI") or "").strip()
    saved = (get_setting(KEY_REDIRECT) or "").strip()
    return env or saved or "http://localhost:8501"


def save_credentials(client_id: str, client_secret: str, redirect_uri: str) -> None:
    set_setting(KEY_CLIENT_ID, client_id.strip())
    set_setting(KEY_CLIENT_SECRET, client_secret.strip())
    set_setting(KEY_REDIRECT, (redirect_uri or "http://localhost:8501").strip())


def is_configured() -> bool:
    return bool(get_client_id() and get_client_secret())


def authorization_url(merchant_id: int) -> str:
    cid = get_client_id()
    if not cid:
        raise MercadoPagoError("Falta el identificador de la aplicación de Mercado Pago.")
    params = {
        "client_id": cid,
        "response_type": "code",
        "platform_id": "mp",
        "state": f"m{int(merchant_id)}",
        "redirect_uri": get_redirect_uri(),
    }
    return f"{AUTH_URL}?{urlencode(params)}"


def merchant_linked(merchant: dict[str, Any] | None) -> bool:
    if not merchant:
        return False
    return bool(merchant.get("mp_access_token"))


def _parse_state(state: str) -> Optional[int]:
    raw = (state or "").strip()
    if raw.startswith("m") and raw[1:].isdigit():
        return int(raw[1:])
    return None


def consume_oauth_if_present() -> Optional[str]:
    """Si Mercado Pago redirigió con ?code=, vincula el comercio y limpia la URL."""
    try:
        params = st.query_params
    except Exception:
        return None
    code = (params.get("code") or "").strip()
    state = (params.get("state") or "").strip()
    if not code or not state:
        return None
    merchant_id = _parse_state(state)
    try:
        st.query_params.clear()
    except Exception:
        pass
    if not merchant_id:
        return "Mercado Pago devolvió un código, pero no pude identificar el comercio."
    try:
        exchange_code(merchant_id, code)
        merchant = get_rbf_merchant(merchant_id)
        nombre = (merchant or {}).get("business_name") or f"#{merchant_id}"
        return f"Cuenta de Mercado Pago vinculada: {nombre}."
    except MercadoPagoError as exc:
        return str(exc)


def exchange_code(merchant_id: int, code: str) -> dict[str, Any]:
    payload = {
        "client_id": get_client_id(),
        "client_secret": get_client_secret(),
        "code": code,
        "grant_type": "authorization_code",
        "redirect_uri": get_redirect_uri(),
    }
    if not payload["client_id"] or not payload["client_secret"]:
        raise MercadoPagoError("Guardá primero el identificador y la clave secreta de Mercado Pago.")
    data = _token_request(payload)
    _persist_tokens(merchant_id, data)
    return data


def refresh_merchant_token(merchant_id: int) -> dict[str, Any]:
    merchant = get_rbf_merchant(merchant_id)
    if not merchant or not merchant.get("mp_refresh_token"):
        raise MercadoPagoError("Este comercio no tiene cuenta de Mercado Pago vinculada.")
    data = _token_request(
        {
            "client_id": get_client_id(),
            "client_secret": get_client_secret(),
            "grant_type": "refresh_token",
            "refresh_token": merchant["mp_refresh_token"],
        }
    )
    _persist_tokens(merchant_id, data)
    return data


def seller_access_token(merchant_id: int) -> str:
    merchant = get_rbf_merchant(merchant_id)
    if not merchant or not merchant.get("mp_access_token"):
        raise MercadoPagoError("Este comercio todavía no vinculó Mercado Pago.")
    expires = merchant.get("mp_token_expires_at") or ""
    try:
        exp = datetime.fromisoformat(expires)
        if exp.tzinfo is None:
            exp = exp.replace(tzinfo=timezone.utc)
        if exp - datetime.now(timezone.utc) < timedelta(days=3):
            merchant = get_rbf_merchant(merchant_id)
            refresh_merchant_token(merchant_id)
            merchant = get_rbf_merchant(merchant_id)
    except (TypeError, ValueError):
        pass
    token = (merchant or {}).get("mp_access_token") or ""
    if not token:
        raise MercadoPagoError("No pude renovar el acceso de Mercado Pago. Volvé a vincular el comercio.")
    return token


def split_de_venta(monto_venta: float, retencion_pct: float) -> dict[str, float]:
    """Parte una venta del local: retención Finan vs. lo que le queda al comercio (antes de comisión MP)."""
    venta = round(float(monto_venta), 2)
    pct = max(0.0, min(float(retencion_pct), 40.0))
    finan = round(venta * pct / 100.0, 2)
    if finan >= venta:
        finan = round(venta * 0.4, 2)
        pct = 40.0
    comercio = round(venta - finan, 2)
    return {
        "venta": venta,
        "retention_pct": pct,
        "finan": finan,
        "comercio_antes_mp": comercio,
    }


def crear_cobro_local(
    *,
    merchant_id: int,
    loan_id: int,
    monto_venta: float,
    retencion_pct: float,
    titulo: str,
) -> dict[str, Any]:
    partes = split_de_venta(monto_venta, retencion_pct)
    if partes["venta"] <= 0:
        raise MercadoPagoError("La venta tiene que ser mayor a cero.")
    if partes["finan"] < 1:
        raise MercadoPagoError("La retención da menos de $1. Subí el porcentaje o el monto.")

    token = seller_access_token(merchant_id)
    ext_ref = f"finan-l{loan_id}-m{merchant_id}-{uuid4().hex[:10]}"
    body = {
        "items": [
            {
                "title": (titulo or "Venta en el local")[:120],
                "quantity": 1,
                "currency_id": "ARS",
                "unit_price": partes["venta"],
            }
        ],
        "marketplace_fee": partes["finan"],
        "external_reference": ext_ref,
        "binary_mode": True,
        "statement_descriptor": "FINAN",
    }
    resp = requests.post(
        f"{API_BASE}/checkout/preferences",
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        },
        json=body,
        timeout=30,
    )
    data = _json_or_error(resp, "No pude crear el cobro en Mercado Pago.")
    init_point = data.get("init_point") or data.get("sandbox_init_point") or ""
    if not init_point:
        raise MercadoPagoError("Mercado Pago no devolvió el link de pago.")
    sale_id = insert_mp_sale(
        {
            "loan_id": loan_id,
            "merchant_id": merchant_id,
            "sale_amount": partes["venta"],
            "finan_amount": partes["finan"],
            "retention_pct": partes["retention_pct"],
            "preference_id": data.get("id") or "",
            "init_point": init_point,
            "external_reference": ext_ref,
            "status": "pendiente",
        }
    )
    return {
        "sale_id": sale_id,
        "init_point": init_point,
        "preference_id": data.get("id"),
        "external_reference": ext_ref,
        **partes,
    }


def sincronizar_cobro(sale_id: int) -> dict[str, Any]:
    """Consulta si el cliente ya pagó y acredita la retención a los barridos del préstamo."""
    sale = get_mp_sale(sale_id)
    if not sale:
        raise MercadoPagoError("No encuentro esa venta.")
    if sale.get("status") == "cobrada":
        return {"ya_estaba": True, **sale}

    token = seller_access_token(int(sale["merchant_id"]))
    resp = requests.get(
        f"{API_BASE}/v1/payments/search",
        headers={"Authorization": f"Bearer {token}"},
        params={"external_reference": sale["external_reference"], "sort": "date_created", "criteria": "desc"},
        timeout=30,
    )
    data = _json_or_error(resp, "No pude consultar el pago en Mercado Pago.")
    results = data.get("results") or []
    pago = None
    for item in results:
        if (item.get("status") or "") == "approved":
            pago = item
            break
    if not pago and results:
        pago = results[0]
    if not pago:
        return {"encontrado": False, "status": sale.get("status"), **sale}

    status_mp = pago.get("status") or ""
    payment_id = str(pago.get("id") or "")
    if status_mp != "approved":
        update_mp_sale(sale_id, {"status": status_mp, "mp_payment_id": payment_id})
        return {"encontrado": True, "status": status_mp, "mp_payment_id": payment_id, **sale}

    applied = aplicar_cobro_sweeps(int(sale["loan_id"]), float(sale["finan_amount"]))
    update_mp_sale(
        sale_id,
        {
            "status": "cobrada",
            "mp_payment_id": payment_id,
            "cobrado_en": datetime.now().isoformat(timespec="seconds"),
        },
    )
    return {
        "encontrado": True,
        "status": "cobrada",
        "mp_payment_id": payment_id,
        "aplicado": applied,
        **sale,
    }


def _persist_tokens(merchant_id: int, data: dict[str, Any]) -> None:
    access = data.get("access_token") or ""
    refresh = data.get("refresh_token") or ""
    user_id = str(data.get("user_id") or "")
    if not access:
        raise MercadoPagoError("Mercado Pago no devolvió el acceso. Revisá las credenciales.")
    expires_in = int(data.get("expires_in") or 15552000)
    expires_at = (datetime.now(timezone.utc) + timedelta(seconds=expires_in)).isoformat()
    save_rbf_merchant_mp_tokens(
        merchant_id,
        user_id=user_id,
        access_token=access,
        refresh_token=refresh,
        expires_at=expires_at,
    )


def _token_request(payload: dict[str, Any]) -> dict[str, Any]:
    resp = requests.post(
        TOKEN_URL,
        headers={"Content-Type": "application/json", "Accept": "application/json"},
        json=payload,
        timeout=30,
    )
    return _json_or_error(resp, "Mercado Pago rechazó el pedido de acceso.")


def _json_or_error(resp: requests.Response, fallback: str) -> dict[str, Any]:
    try:
        data = resp.json()
    except ValueError:
        data = {}
    if resp.status_code >= 400:
        msg = data.get("message") or data.get("error_description") or data.get("error") or fallback
        cause = data.get("cause")
        if isinstance(cause, list) and cause:
            first = cause[0]
            extra = first.get("description") if isinstance(first, dict) else str(first)
            if extra:
                msg = f"{msg}: {extra}"
        raise MercadoPagoError(str(msg))
    if not isinstance(data, dict):
        raise MercadoPagoError(fallback)
    return data
