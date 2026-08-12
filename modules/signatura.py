"""
Cliente Signatura (Flex / API REST).

Docs: https://docs.signatura.co/
Base: https://connect.signatura.co/api/v2
"""

from __future__ import annotations

import base64
import os
from typing import Any, Optional

import requests

API_BASE = "https://connect.signatura.co/api/v2"
SETTING_KEY = "signatura_api_key"


class SignaturaError(Exception):
    """Error de comunicación o configuración con Signatura."""


def get_api_key() -> str:
    """Prioridad: variable de entorno → setting local en DB."""
    from modules.database import get_setting

    env = (os.environ.get("SIGNATURA_API_KEY") or "").strip()
    if env:
        return env
    return (get_setting(SETTING_KEY) or "").strip()


def save_api_key(api_key: str) -> None:
    from modules.database import set_setting

    set_setting(SETTING_KEY, api_key.strip())


def is_configured() -> bool:
    return bool(get_api_key())


def _headers() -> dict[str, str]:
    key = get_api_key()
    if not key:
        raise SignaturaError(
            "Falta API key de Signatura. Cargala en Trazabilidad → Configuración "
            "o en la variable SIGNATURA_API_KEY."
        )
    return {
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json",
    }


def pdf_to_base64(pdf_bytes: bytes) -> str:
    return base64.b64encode(pdf_bytes).decode("ascii")


def create_document(
    title: str,
    pdf_bytes: bytes,
    signatures: list[dict[str, Any]],
    complete_url: Optional[str] = None,
) -> dict[str, Any]:
    """
    Crea un documento en Signatura.

    signatures: lista según API, ej.:
      [{"validations": {"EM": "a@b.com"}, "invite_channel": ["EM"]}]
    Validaciones: EM (email), PH (tel), BI (biometría), AF (ARCA/AFIP CUIT).
    """
    payload: dict[str, Any] = {
        "title": title,
        "file_content": pdf_to_base64(pdf_bytes),
        "signatures": signatures,
    }
    if complete_url:
        payload["complete_url"] = complete_url

    try:
        resp = requests.post(
            f"{API_BASE}/documents/create",
            headers=_headers(),
            json=payload,
            timeout=60,
        )
    except requests.RequestException as exc:
        raise SignaturaError(f"No se pudo contactar Signatura: {exc}") from exc

    if resp.status_code >= 400:
        raise SignaturaError(f"Signatura {resp.status_code}: {resp.text[:500]}")

    data = resp.json()
    return data if isinstance(data, dict) else {"raw": data}


def get_document(document_id: str) -> dict[str, Any]:
    try:
        resp = requests.get(
            f"{API_BASE}/documents/{document_id}",
            headers=_headers(),
            timeout=30,
        )
    except requests.RequestException as exc:
        raise SignaturaError(f"No se pudo contactar Signatura: {exc}") from exc

    if resp.status_code >= 400:
        raise SignaturaError(f"Signatura {resp.status_code}: {resp.text[:500]}")

    data = resp.json()
    return data if isinstance(data, dict) else {"raw": data}


def list_documents() -> Any:
    try:
        resp = requests.get(
            f"{API_BASE}/documents",
            headers=_headers(),
            timeout=30,
        )
    except requests.RequestException as exc:
        raise SignaturaError(f"No se pudo contactar Signatura: {exc}") from exc

    if resp.status_code >= 400:
        raise SignaturaError(f"Signatura {resp.status_code}: {resp.text[:500]}")
    return resp.json()


def build_signer(
    email: Optional[str] = None,
    phone: Optional[str] = None,
    cuit_afip: Optional[str] = None,
    invite_email: bool = True,
    invite_sms: bool = False,
    biometric: bool = False,
) -> dict[str, Any]:
    """Arma un firmante para create_document."""
    validations: dict[str, Any] = {}
    invite: list[str] = []

    if email:
        validations["EM"] = email
        if invite_email:
            invite.append("EM")
    if phone:
        validations["PH"] = phone
        if invite_sms:
            invite.append("PH")
    if cuit_afip:
        # Clave fiscal ARCA/AFIP — refuerzo de autoría
        validations["AF"] = cuit_afip.replace("-", "").strip()
    if biometric:
        validations["BI"] = None

    if not validations:
        raise SignaturaError("Cada firmante necesita al menos email, teléfono, CUIT AFIP o biometría.")

    signer: dict[str, Any] = {"validations": validations}
    if invite:
        signer["invite_channel"] = invite
    return signer


def extract_document_id(response: dict[str, Any]) -> str:
    """Normaliza el id del documento según posibles formas de respuesta."""
    for key in ("id", "document_id", "documentId"):
        if response.get(key):
            return str(response[key])
    doc = response.get("document")
    if isinstance(doc, dict) and doc.get("id"):
        return str(doc["id"])
    raise SignaturaError(f"Respuesta de Signatura sin document id: {list(response.keys())}")
