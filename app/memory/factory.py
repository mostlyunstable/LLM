from __future__ import annotations

from app.core.config import Settings
from app.memory.store import MemoryStore


def build_memory_store(settings: Settings) -> MemoryStore:
    backend = (settings.MEMORY_BACKEND or "memory").lower()
    if backend == "redis":
        from app.memory.redis_store import RedisMemoryStore

        return RedisMemoryStore.from_settings(settings)
    return MemoryStore.in_memory(ttl_seconds=settings.MEMORY_TTL_SECONDS)

