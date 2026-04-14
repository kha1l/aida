"""Подписанные ссылки для web-отчетов Aida."""

from __future__ import annotations

import hashlib
import hmac
import base64
import time
import uuid
from dataclasses import dataclass
from urllib.parse import urlencode


@dataclass(frozen=True, slots=True)
class ReportLinkParams:
    request_id: str
    report_type: str
    unit_uuid: str
    account_id: int
    message_date: str
    threshold_minutes: int | None = None


def build_report_url(
    *,
    base_url: str | None,
    direct_link_url: str | None = None,
    signing_secret: str | None,
    params: ReportLinkParams,
    ttl_seconds: int = 3600,
) -> str | None:
    """Возвращает signed URL для открытия web-отчета."""
    if not base_url or not signing_secret:
        return None

    payload: dict[str, str] = {
        "request_id": params.request_id,
        "report_type": params.report_type,
        "unit_uuid": params.unit_uuid,
        "account_id": str(params.account_id),
        "message_date": params.message_date,
        "exp": str(int(time.time()) + ttl_seconds),
    }
    if params.threshold_minutes is not None:
        payload["threshold_minutes"] = str(params.threshold_minutes)

    payload["sig"] = sign_payload(payload, signing_secret)
    query = urlencode(payload)
    if direct_link_url:
        startapp = encode_startapp_payload(query)
        separator = "&" if "?" in direct_link_url else "?"
        return f"{direct_link_url.rstrip()}{separator}startapp={startapp}"

    separator = "&" if "?" in base_url else "?"
    return f"{base_url.rstrip()}{separator}{query}"


def new_request_id() -> str:
    """Генерирует UUID для корреляции WebApp-страницы и Dagster run."""
    return uuid.uuid4().hex


def sign_payload(payload: dict[str, str], signing_secret: str) -> str:
    """Подписывает query payload без поля `sig`."""
    canonical = _canonical_payload(payload)
    return hmac.new(
        signing_secret.encode("utf-8"),
        canonical.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()


def encode_startapp_payload(query: str) -> str:
    """Кодирует query в формат, разрешенный Telegram `startapp`."""
    return base64.urlsafe_b64encode(query.encode("utf-8")).decode("ascii").rstrip("=")


def _canonical_payload(payload: dict[str, str]) -> str:
    parts = []
    for key in sorted(payload):
        if key == "sig":
            continue
        parts.append(f"{key}={payload[key]}")
    return "\n".join(parts)
