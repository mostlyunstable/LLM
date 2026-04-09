from __future__ import annotations

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # OpenAI
    OPENAI_API_KEY: str = Field(default="", repr=False)
    OPENAI_MODEL: str = Field(default="gpt-4o-mini")
    OPENAI_MAX_OUTPUT_TOKENS: int = Field(default=300, ge=32, le=2000)
    OPENAI_REQUEST_TIMEOUT_SECONDS: float = Field(default=20.0, gt=1)
    OPENAI_EMBEDDING_MODEL: str = Field(default="text-embedding-3-small")

    # Twilio
    TWILIO_ACCOUNT_SID: str = Field(default="", repr=False)
    TWILIO_AUTH_TOKEN: str = Field(default="", repr=False)
    TWILIO_WHATSAPP_NUMBER: str = Field(default="", description='Like "whatsapp:+15551234567"')
    TWILIO_VALIDATE_SIGNATURE: bool = Field(default=True)

    # Replying strategy
    ASYNC_REPLY: bool = Field(
        default=False,
        description="If true, ack the webhook fast and reply via Twilio REST in background.",
    )

    # Conversation memory
    MEMORY_BACKEND: str = Field(default="memory", description="memory|redis")
    MEMORY_TTL_SECONDS: int = Field(default=60 * 60 * 6, ge=60)  # 6 hours
    MEMORY_MAX_TURNS: int = Field(default=8, ge=0, le=50)
    REDIS_URL: str = Field(default="redis://localhost:6379/0")
    DEDUP_TTL_SECONDS: int = Field(default=60 * 60 * 24, ge=60)  # 24 hours

    # WhatsApp-friendly response shaping
    WHATSAPP_MAX_CHARS: int = Field(default=700, ge=80, le=1600)

    # Basic abuse controls
    PER_SENDER_COOLDOWN_SECONDS: float = Field(default=0.5, ge=0)

    # Optional media support (image/audio)
    MEDIA_ENABLED: bool = Field(default=False)
    MEDIA_MAX_BYTES: int = Field(default=8 * 1024 * 1024, ge=1024)  # 8MB
    OPENAI_VISION_MODEL: str = Field(default="gpt-4.1-mini")
    OPENAI_STT_MODEL: str = Field(default="whisper-1")

    # Optional RAG
    RAG_ENABLED: bool = Field(default=False)
    RAG_INDEX_PATH: str = Field(default="data/faiss.index")
    RAG_DOCS_PATH: str = Field(default="data/docs")
    RAG_TOP_K: int = Field(default=4, ge=0, le=20)


@lru_cache
def get_settings() -> Settings:
    return Settings()
