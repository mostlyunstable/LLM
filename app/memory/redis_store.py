from __future__ import annotations

import json
import time
from dataclasses import asdict
from typing import Iterable

import redis

from app.core.config import Settings
from app.memory.store import MemoryMessage, MemoryStore


class RedisMemoryStore(MemoryStore):
    def __init__(self, *, client: redis.Redis, ttl_seconds: int) -> None:
        super().__init__(ttl_seconds=ttl_seconds)
        self._r = client

    @classmethod
    def from_settings(cls, settings: Settings) -> "RedisMemoryStore":
        client = redis.Redis.from_url(settings.REDIS_URL, decode_responses=True)
        return cls(client=client, ttl_seconds=settings.MEMORY_TTL_SECONDS)

    def _key(self, sender: str) -> str:
        return f"wa:mem:{sender}"

    def get(self, sender: str) -> list[MemoryMessage]:
        raw = self._r.get(self._key(sender))
        if not raw:
            return []
        data = json.loads(raw)
        return [MemoryMessage(**m) for m in data]

    def set(self, sender: str, messages: Iterable[MemoryMessage]) -> None:
        payload = json.dumps([asdict(m) for m in messages], ensure_ascii=False)
        self._r.set(self._key(sender), payload, ex=self.ttl_seconds)

    def cooldown_ok(self, sender: str, *, cooldown_seconds: float) -> bool:
        if cooldown_seconds <= 0:
            return True
        key = f"wa:cooldown:{sender}"
        # setnx with expiration
        return bool(self._r.set(key, str(time.time()), nx=True, ex=max(1, int(cooldown_seconds))))

