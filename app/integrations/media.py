from __future__ import annotations

import logging
import mimetypes
import os
import tempfile
from dataclasses import dataclass

import httpx
from openai import OpenAI

from app.core.config import Settings

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class MediaItem:
    url: str
    content_type: str


class TwilioMediaFetcher:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    async def fetch_bytes(self, url: str, *, max_bytes: int) -> bytes:
        # Twilio media URLs generally require Basic Auth with Account SID + Auth Token.
        auth = None
        if self._settings.TWILIO_ACCOUNT_SID and self._settings.TWILIO_AUTH_TOKEN:
            auth = (self._settings.TWILIO_ACCOUNT_SID, self._settings.TWILIO_AUTH_TOKEN)

        async with httpx.AsyncClient(timeout=self._settings.OPENAI_REQUEST_TIMEOUT_SECONDS) as client:
            async with client.stream("GET", url, auth=auth) as r:
                r.raise_for_status()
                chunks: list[bytes] = []
                size = 0
                async for part in r.aiter_bytes():
                    size += len(part)
                    if size > max_bytes:
                        raise ValueError("media too large")
                    chunks.append(part)
                return b"".join(chunks)


class OpenAIMediaProcessor:
    def __init__(self, settings: Settings) -> None:
        if not settings.OPENAI_API_KEY:
            raise ValueError("OPENAI_API_KEY is required")
        self._settings = settings
        self._client = OpenAI(api_key=settings.OPENAI_API_KEY, timeout=settings.OPENAI_REQUEST_TIMEOUT_SECONDS)

    def transcribe_audio(self, *, audio_bytes: bytes, content_type: str) -> str:
        suffix = mimetypes.guess_extension(content_type) or ".audio"
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as f:
            f.write(audio_bytes)
            tmp_path = f.name
        try:
            with open(tmp_path, "rb") as audio_file:
                transcript = self._client.audio.transcriptions.create(model=self._settings.OPENAI_STT_MODEL, file=audio_file)
            return (getattr(transcript, "text", "") or "").strip()
        finally:
            try:
                os.unlink(tmp_path)
            except OSError:
                pass

    def analyze_image(self, *, image_bytes: bytes, prompt: str, content_type: str) -> str:
        suffix = mimetypes.guess_extension(content_type) or ".img"
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as f:
            f.write(image_bytes)
            tmp_path = f.name
        try:
            with open(tmp_path, "rb") as file_content:
                uploaded = self._client.files.create(file=file_content, purpose="vision")
            resp = self._client.responses.create(
                model=self._settings.OPENAI_VISION_MODEL,
                input=[
                    {
                        "role": "user",
                        "content": [
                            {"type": "input_text", "text": prompt},
                            {"type": "input_image", "file_id": uploaded.id},
                        ],
                    }
                ],
                max_output_tokens=200,
            )
            return (resp.output_text or "").strip()
        finally:
            try:
                os.unlink(tmp_path)
            except OSError:
                pass

