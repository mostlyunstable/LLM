from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Dict, Iterable, List, Tuple


@dataclass(frozen=True)
class MemoryMessage:
    role: str  # "user" | "assistant"
    content: str
    ts: float


class MemoryStore:
    """
    Minimal conversation memory:
    - stores the last N messages per sender
    - TTL-based eviction
    - optional per-sender cooldown (best-effort)
    """

    def __init__(self, *, ttl_seconds: int) -> None:
        self.ttl_seconds = ttl_seconds

    @classmethod
    def in_memory(cls, *, ttl_seconds: int) -> "InMemoryStore":
        return InMemoryStore(ttl_seconds=ttl_seconds)

    def get(self, sender: str) -> list[MemoryMessage]:  # pragma: no cover
        raise NotImplementedError

    def set(self, sender: str, messages: Iterable[MemoryMessage]) -> None:  # pragma: no cover
        raise NotImplementedError

    def cooldown_ok(self, sender: str, *, cooldown_seconds: float) -> bool:  # pragma: no cover
        return True

    def message_id_ok(self, sender: str, *, message_id: str, ttl_seconds: int) -> bool:  # pragma: no cover
        return True


class InMemoryStore(MemoryStore):
    def __init__(self, *, ttl_seconds: int) -> None:
        super().__init__(ttl_seconds=ttl_seconds)
        self._data: Dict[str, Tuple[float, List[MemoryMessage]]] = {}
        self._cooldown_until: Dict[str, float] = {}
        self._seen_message_ids: Dict[str, Dict[str, float]] = {}

    def _evict_if_needed(self, sender: str) -> None:
        now = time.time()
        expires_at, _ = self._data.get(sender, (0.0, []))
        if expires_at and now > expires_at:
            self._data.pop(sender, None)

    def get(self, sender: str) -> list[MemoryMessage]:
        self._evict_if_needed(sender)
        return list(self._data.get(sender, (0.0, []))[1])

    def set(self, sender: str, messages: Iterable[MemoryMessage]) -> None:
        now = time.time()
        self._data[sender] = (now + self.ttl_seconds, list(messages))

    def cooldown_ok(self, sender: str, *, cooldown_seconds: float) -> bool:
        if cooldown_seconds <= 0:
            return True
        now = time.time()
        until = self._cooldown_until.get(sender, 0.0)
        if now < until:
            return False
        self._cooldown_until[sender] = now + cooldown_seconds
        return True

    def message_id_ok(self, sender: str, *, message_id: str, ttl_seconds: int) -> bool:
        if not message_id:
            return True
        now = time.time()
        bucket = self._seen_message_ids.setdefault(sender, {})
        # prune expired
        for mid, exp in list(bucket.items()):
            if now > exp:
                bucket.pop(mid, None)
        if message_id in bucket:
            return False
        bucket[message_id] = now + max(60, int(ttl_seconds))
        return True
