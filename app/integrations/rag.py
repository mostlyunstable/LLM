from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple

from openai import OpenAI

from app.core.config import Settings

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class RAGChunk:
    text: str
    source: str


class RAGRetriever:
    def __init__(self, *, settings: Settings) -> None:
        self._settings = settings
        self._index_path = Path(settings.RAG_INDEX_PATH)
        self._meta_path = self._index_path.with_suffix(".meta.json")
        self._client = OpenAI(api_key=settings.OPENAI_API_KEY, timeout=settings.OPENAI_REQUEST_TIMEOUT_SECONDS)

        # Optional heavy deps
        try:
            import faiss  # type: ignore
            import numpy as np  # type: ignore
        except Exception as e:  # pragma: no cover
            raise RuntimeError(
                "RAG requires optional deps. Install `requirements-optional.txt` (faiss-cpu, numpy)."
            ) from e

        self._faiss = faiss
        self._np = np

        self._index = None
        self._chunks: list[RAGChunk] = []

    def _load(self) -> None:
        if self._index is not None:
            return
        if not self._index_path.exists() or not self._meta_path.exists():
            logger.warning("RAG index missing: %s or %s", self._index_path, self._meta_path)
            self._index = None
            self._chunks = []
            return

        self._index = self._faiss.read_index(str(self._index_path))
        meta = json.loads(self._meta_path.read_text(encoding="utf-8"))
        self._chunks = [RAGChunk(text=m["text"], source=m.get("source", "doc")) for m in meta]

    def _embed(self, text: str) -> list[float]:
        emb = self._client.embeddings.create(model=self._settings.OPENAI_EMBEDDING_MODEL, input=text)
        return list(emb.data[0].embedding)

    def retrieve(self, query: str, *, k: int) -> list[RAGChunk]:
        self._load()
        if not self._index or not self._chunks or k <= 0:
            return []

        vec = self._np.array([self._embed(query)], dtype="float32")
        scores, idxs = self._index.search(vec, k)
        _ = scores  # distance scores
        out: list[RAGChunk] = []
        for i in idxs[0].tolist():
            if 0 <= i < len(self._chunks):
                out.append(self._chunks[i])
        return out


_RETRIEVER_CACHE: Dict[Tuple[str, str], RAGRetriever] = {}


def get_retriever(settings: Settings) -> Optional[RAGRetriever]:
    if not settings.RAG_ENABLED:
        return None
    key = (settings.RAG_INDEX_PATH, settings.OPENAI_EMBEDDING_MODEL)
    if key in _RETRIEVER_CACHE:
        return _RETRIEVER_CACHE[key]
    retriever = RAGRetriever(settings=settings)
    _RETRIEVER_CACHE[key] = retriever
    return retriever


def format_context(chunks: Iterable[RAGChunk], *, max_chars: int = 1200) -> str:
    parts: List[str] = []
    remaining = max_chars
    for c in chunks:
        snippet = c.text.strip().replace("\n\n", "\n")
        line = f"[{c.source}] {snippet}"
        if len(line) > remaining:
            break
        parts.append(line)
        remaining -= len(line) + 1
    return "\n".join(parts).strip()
