from __future__ import annotations

import logging

from twilio.rest import Client

from app.core.config import Settings

logger = logging.getLogger(__name__)


class TwilioWhatsAppClient:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        if not (settings.TWILIO_ACCOUNT_SID and settings.TWILIO_AUTH_TOKEN):
            self._client = None
        else:
            self._client = Client(settings.TWILIO_ACCOUNT_SID, settings.TWILIO_AUTH_TOKEN)

    def can_send(self) -> bool:
        return bool(self._client and self._settings.TWILIO_WHATSAPP_NUMBER)

    def send_text(self, *, to: str, body: str) -> None:
        if not self.can_send():
            raise RuntimeError("Twilio client not configured for outbound messages")
        self._client.messages.create(from_=self._settings.TWILIO_WHATSAPP_NUMBER, to=to, body=body)

