from __future__ import annotations

import logging
import time

from fastapi import APIRouter, BackgroundTasks, Request, Response
from fastapi.responses import PlainTextResponse
from twilio.twiml.messaging_response import MessagingResponse

from app.core.config import get_settings
from app.integrations.twilio_client import TwilioWhatsAppClient
from app.integrations.twilio_signature import verify_twilio_signature
from app.memory.factory import build_memory_store
from app.services.assistant import AssistantService

router = APIRouter()
logger = logging.getLogger(__name__)


@router.post("/webhooks/twilio/whatsapp")
async def twilio_whatsapp_webhook(request: Request, background_tasks: BackgroundTasks) -> Response:
    settings = get_settings()

    form = await request.form()
    form_data: dict[str, str] = {k: str(v) for k, v in form.items()}

    # Basic fields documented by Twilio for WhatsApp inbound messages.
    sender = form_data.get("From", "").strip()
    message_sid = form_data.get("MessageSid", "").strip()
    body = (form_data.get("Body") or "").strip()
    num_media = int(form_data.get("NumMedia") or "0")
    media: list[dict[str, str]] = []
    for i in range(num_media):
        url = (form_data.get(f"MediaUrl{i}") or "").strip()
        content_type = (form_data.get(f"MediaContentType{i}") or "").strip()
        if url:
            media.append({"url": url, "content_type": content_type})

    if settings.TWILIO_VALIDATE_SIGNATURE and settings.TWILIO_AUTH_TOKEN:
        is_valid = verify_twilio_signature(
            request=request,
            form_data=form_data,
            auth_token=settings.TWILIO_AUTH_TOKEN,
        )
        if not is_valid:
            return PlainTextResponse("forbidden", status_code=403)
    elif settings.TWILIO_VALIDATE_SIGNATURE and not settings.TWILIO_AUTH_TOKEN:
        logger.warning("TWILIO_VALIDATE_SIGNATURE=true but TWILIO_AUTH_TOKEN is empty; skipping validation")

    if not sender:
        return PlainTextResponse("missing From", status_code=400)

    if not body and not media:
        resp = MessagingResponse()
        resp.message("Send me a question (text), and I’ll answer.")
        return Response(content=str(resp), media_type="application/xml")

    memory_store = build_memory_store(settings)
    assistant = AssistantService(
        settings=settings,
        memory=memory_store,
        twilio=TwilioWhatsAppClient(settings),
    )

    if settings.ASYNC_REPLY:
        background_tasks.add_task(
            assistant.handle_and_send,
            sender=sender,
            body=body,
            media=media,
            message_id=message_sid,
        )
        # Ack fast; send the actual reply via Twilio REST API from the background task.
        return Response(content=str(MessagingResponse()), media_type="application/xml")

    started = time.monotonic()
    reply = await assistant.handle(sender=sender, body=body, media=media, message_id=message_sid)
    if reply is None:
        return Response(content=str(MessagingResponse()), media_type="application/xml")
    took_ms = int((time.monotonic() - started) * 1000)

    resp = MessagingResponse()
    resp.message(reply)
    response = Response(content=str(resp), media_type="application/xml")
    response.headers["X-Response-Time-ms"] = str(took_ms)
    return response
