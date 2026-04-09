from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Iterable

from openai import OpenAI
from tenacity import retry, stop_after_attempt, wait_random_exponential

from app.core.config import Settings

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ChatMessage:
    role: str  # "user" | "assistant"
    content: str


class OpenAIResponder:
    def __init__(self, settings: Settings) -> None:
        if not settings.OPENAI_API_KEY:
            raise ValueError("OPENAI_API_KEY is required")
        self._settings = settings
        self._client = OpenAI(api_key=settings.OPENAI_API_KEY, timeout=settings.OPENAI_REQUEST_TIMEOUT_SECONDS)

    @retry(wait=wait_random_exponential(min=0.2, max=2.0), stop=stop_after_attempt(3))
    def generate(self, *, instructions: str, messages: Iterable[ChatMessage]) -> str:
        # Responses API accepts a string or an array of input message objects.
        input_items = [{"role": m.role, "content": m.content} for m in messages]
        resp = self._client.responses.create(
            model=self._settings.OPENAI_MODEL,
            instructions=instructions,
            input=input_items,
            max_output_tokens=self._settings.OPENAI_MAX_OUTPUT_TOKENS,
        )
        text = (resp.output_text or "").strip()
        return text
