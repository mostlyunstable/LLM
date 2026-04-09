from __future__ import annotations

import logging
import time
from typing import Iterable

from anyio import to_thread

from app.core.config import Settings
from app.integrations.openai_client import ChatMessage, OpenAIResponder
from app.integrations.rag import format_context, get_retriever
from app.integrations.twilio_client import TwilioWhatsAppClient
from app.integrations.media import MediaItem, OpenAIMediaProcessor, TwilioMediaFetcher
from app.memory.store import MemoryMessage, MemoryStore
from app.prompts.system import system_instructions
from app.utils.text import truncate_for_whatsapp

logger = logging.getLogger(__name__)


class AssistantService:
    def __init__(self, *, settings: Settings, memory: MemoryStore, twilio: TwilioWhatsAppClient) -> None:
        self._settings = settings
        self._memory = memory
        self._twilio = twilio
        self._llm = OpenAIResponder(settings)

    def _trim_history(self, history: list[MemoryMessage]) -> list[MemoryMessage]:
        # Keep only recent messages, counting turns as user+assistant pairs.
        if self._settings.MEMORY_MAX_TURNS <= 0:
            return []
        max_messages = self._settings.MEMORY_MAX_TURNS * 2
        return history[-max_messages:]

    def _to_chat_messages(self, history: Iterable[MemoryMessage], user_text: str) -> list[ChatMessage]:
        msgs: list[ChatMessage] = []
        for m in history:
            if m.role in ("user", "assistant") and m.content.strip():
                msgs.append(ChatMessage(role=m.role, content=m.content))
        msgs.append(ChatMessage(role="user", content=user_text))
        return msgs

    async def handle(
        self, *, sender: str, body: str, media: list[dict[str, str]], message_id: str = ""
    ) -> str | None:
        if message_id and not self._memory.message_id_ok(
            sender, message_id=message_id, ttl_seconds=self._settings.DEDUP_TTL_SECONDS
        ):
            logger.info("duplicate_message_ignored sender=%s message_id=%s", sender, message_id)
            return None
        if not self._memory.cooldown_ok(sender, cooldown_seconds=self._settings.PER_SENDER_COOLDOWN_SECONDS):
            return "One sec—please wait a moment and try again."

        user_text = body

        # Optional: turn WhatsApp media (audio/image) into text for the assistant.
        if media and self._settings.MEDIA_ENABLED:
            fetcher = TwilioMediaFetcher(self._settings)
            processor = OpenAIMediaProcessor(self._settings)
            for m in [MediaItem(url=x["url"], content_type=x.get("content_type", "")) for x in media]:
                try:
                    data = await fetcher.fetch_bytes(m.url, max_bytes=self._settings.MEDIA_MAX_BYTES)
                except Exception:
                    logger.exception("Failed to download media")
                    continue

                if m.content_type.startswith("audio/"):
                    try:
                        transcript = await to_thread.run_sync(
                            processor.transcribe_audio, audio_bytes=data, content_type=m.content_type
                        )
                        if transcript:
                            user_text += f"\n\n[Audio transcript]\n{transcript}"
                    except Exception:
                        logger.exception("Audio transcription failed")
                elif m.content_type.startswith("image/"):
                    try:
                        desc = await to_thread.run_sync(
                            processor.analyze_image,
                            image_bytes=data,
                            content_type=m.content_type,
                            prompt=f"Describe this image clearly and concisely for answering the user's question: {body}",
                        )
                        if desc:
                            user_text += f"\n\n[Image description]\n{desc}"
                    except Exception:
                        logger.exception("Image analysis failed")
                else:
                    logger.info("Unsupported media type: %s", m.content_type)
        elif media:
            user_text += "\n\n(Attachments received. Enable MEDIA_ENABLED=true to analyze images/audio.)"

        # Optional: RAG from your own documents.
        if self._settings.RAG_ENABLED and body.strip():
            try:
                retriever = get_retriever(self._settings)
                if retriever:
                    chunks = await to_thread.run_sync(retriever.retrieve, body.strip(), k=self._settings.RAG_TOP_K)
                    ctx = format_context(chunks)
                    if ctx:
                        user_text = (
                            "Use this context if it helps. If it doesn't contain the answer, say you don't know.\n\n"
                            f"{ctx}\n\nUser question: {body}"
                        )
            except Exception:
                logger.exception("RAG retrieval failed")

        history = self._trim_history(self._memory.get(sender))
        messages = self._to_chat_messages(history, user_text=user_text)

        started = time.monotonic()
        try:
            raw = await to_thread.run_sync(
                self._llm.generate, instructions=system_instructions(self._settings), messages=messages
            )
        except Exception:
            logger.exception("LLM call failed")
            return "Sorry—I’m having trouble right now. Please try again in a minute."
        finally:
            took_ms = int((time.monotonic() - started) * 1000)
            logger.info("llm_response_ms=%s sender=%s", took_ms, sender)

        reply = truncate_for_whatsapp(raw or "Sorry—I couldn't generate an answer.", self._settings.WHATSAPP_MAX_CHARS)

        now = time.time()
        new_history = history + [
            MemoryMessage(role="user", content=body, ts=now),
            MemoryMessage(role="assistant", content=reply, ts=now),
        ]
        self._memory.set(sender, self._trim_history(new_history))
        return reply

    async def handle_and_send(
        self, *, sender: str, body: str, media: list[dict[str, str]], message_id: str = ""
    ) -> None:
        reply = await self.handle(sender=sender, body=body, media=media, message_id=message_id)
        if reply is None:
            return
        if not self._twilio.can_send():
            logger.warning("ASYNC_REPLY enabled but Twilio outbound not configured; dropping reply")
            return
        self._twilio.send_text(to=sender, body=reply)
