from __future__ import annotations

import logging
from typing import Mapping

from fastapi import Request
from twilio.request_validator import RequestValidator

logger = logging.getLogger(__name__)


def _public_url(request: Request) -> str:
    """
    Twilio validates against the full webhook URL.
    In production you'll often be behind a reverse proxy, so honor forwarded headers.
    """
    proto = request.headers.get("x-forwarded-proto") or request.url.scheme
    host = request.headers.get("x-forwarded-host") or request.headers.get("host") or request.url.netloc
    path = request.url.path
    query = request.url.query
    if query:
        return f"{proto}://{host}{path}?{query}"
    return f"{proto}://{host}{path}"


def verify_twilio_signature(*, request: Request, form_data: Mapping[str, str], auth_token: str) -> bool:
    signature = request.headers.get("X-Twilio-Signature", "")
    if not signature:
        return False
    validator = RequestValidator(auth_token)
    url = _public_url(request)
    try:
        return bool(validator.validate(url, dict(form_data), signature))
    except Exception:
        logger.exception("Twilio signature validation failed unexpectedly")
        return False

