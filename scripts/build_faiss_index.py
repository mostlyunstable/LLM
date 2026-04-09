from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

from openai import OpenAI


def iter_text_files(root: Path) -> list[Path]:
    exts = {".txt", ".md"}
    return [p for p in root.rglob("*") if p.is_file() and p.suffix.lower() in exts]


def chunk_text(text: str, *, max_chars: int = 900) -> list[str]:
    text = re.sub(r"\r\n?", "\n", text).strip()
    if not text:
        return []
    paras = [p.strip() for p in text.split("\n\n") if p.strip()]
    chunks: list[str] = []
    cur: list[str] = []
    cur_len = 0
    for p in paras:
        if cur_len + len(p) + 2 > max_chars and cur:
            chunks.append("\n\n".join(cur).strip())
            cur = [p]
            cur_len = len(p)
        else:
            cur.append(p)
            cur_len += len(p) + 2
    if cur:
        chunks.append("\n\n".join(cur).strip())
    return chunks


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--docs", default="data/docs", help="Folder with .txt/.md files")
    ap.add_argument("--out", default="data/faiss.index", help="Output FAISS index path")
    ap.add_argument("--embedding-model", default="text-embedding-3-small")
    args = ap.parse_args()

    docs_root = Path(args.docs)
    out_path = Path(args.out)
    meta_path = out_path.with_suffix(".meta.json")

    files = iter_text_files(docs_root)
    if not files:
        raise SystemExit(f"No .txt/.md files found under {docs_root}")

    client = OpenAI()

    # Optional heavy deps.
    import faiss  # type: ignore
    import numpy as np  # type: ignore

    chunks: list[dict[str, str]] = []
    vectors: list[list[float]] = []
    for fp in files:
        text = fp.read_text(encoding="utf-8", errors="ignore")
        for c in chunk_text(text):
            emb = client.embeddings.create(model=args.embedding_model, input=c)
            vec = list(emb.data[0].embedding)
            chunks.append({"text": c, "source": str(fp.relative_to(docs_root))})
            vectors.append(vec)

    dim = len(vectors[0])
    mat = np.array(vectors, dtype="float32")
    index = faiss.IndexFlatL2(dim)
    index.add(mat)

    out_path.parent.mkdir(parents=True, exist_ok=True)
    faiss.write_index(index, str(out_path))
    meta_path.write_text(json.dumps(chunks, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Wrote {out_path} and {meta_path} with {len(chunks)} chunks.")


if __name__ == "__main__":
    main()

