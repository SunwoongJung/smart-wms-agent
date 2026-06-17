"""FAISS 인덱스 생성/검색 (docs/03 §10). 임베딩 = text-embedding-3-small.

사용(앱 디렉토리에서):
    python -m rag.index            # 인덱스 빌드
"""
import json
from pathlib import Path

import faiss
import numpy as np

from config import settings
from llm import embed
from rag.chunker import load_chunks

IDX_DIR = Path(settings.faiss_index_dir)
IDX_FILE = IDX_DIR / "faiss.index"
META_FILE = IDX_DIR / "chunks.json"

_cache = None


def build_index() -> int:
    chunks = load_chunks()
    if not chunks:
        raise RuntimeError("청크가 없습니다. rag 문서 경로 확인.")
    vecs = np.array(embed([c["text"] for c in chunks]), dtype="float32")
    faiss.normalize_L2(vecs)
    index = faiss.IndexFlatIP(vecs.shape[1])
    index.add(vecs)
    IDX_DIR.mkdir(parents=True, exist_ok=True)
    faiss.write_index(index, str(IDX_FILE))
    META_FILE.write_text(json.dumps(chunks, ensure_ascii=False), encoding="utf-8")
    global _cache
    _cache = None
    return len(chunks)


def _load():
    global _cache
    if _cache is None:
        _cache = (faiss.read_index(str(IDX_FILE)),
                  json.loads(META_FILE.read_text(encoding="utf-8")))
    return _cache


def search(query: str, k: int = 5, intent: str | None = None) -> list[dict]:
    index, chunks = _load()
    qv = np.array(embed([query]), dtype="float32")
    faiss.normalize_L2(qv)
    scores, idxs = index.search(qv, min(k * 3, len(chunks)))
    out = []
    for s, i in zip(scores[0], idxs[0]):
        if i < 0:
            continue
        c = chunks[i]
        if intent and intent not in c["answerable_intents"] and "policy_question" not in c["answerable_intents"]:
            continue
        out.append({**c, "similarity": round(float(s), 4)})
        if len(out) >= k:
            break
    return out


if __name__ == "__main__":
    n = build_index()
    print(f"index built: {n} chunks → {IDX_FILE}")
