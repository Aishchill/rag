"""
ai_service.py  –  Powered by Google Gemini (FREE tier)
  • Embeddings : text-embedding-004  (768-dim, free)
  • Chat       : gemini-1.5-flash    (free tier: 15 req/min, 1M tokens/day)

Uses the Gemini REST API directly via `requests` — no extra packages needed.
"""

import os
import requests
import numpy as np
import faiss
from flask import current_app

_index = None
_index_size = 0
EMBED_DIM = 3072          # Gemini gemini-embedding-001 output dimension

GEMINI_BASE = "https://generativelanguage.googleapis.com/v1beta"


# ── API key helper ────────────────────────────────────────────────────
def _key():
    k = current_app.config.get("GEMINI_API_KEY", "").strip()
    if not k:
        raise RuntimeError(
            "GEMINI_API_KEY is not set. Add your Google AI key to .env."
        )
    return k


def _check_resp(resp, label):
    if resp.status_code == 400:
        raise RuntimeError(f"Gemini bad request ({label}): {resp.text[:300]}")
    if resp.status_code == 401 or resp.status_code == 403:
        raise RuntimeError(
            "Invalid or unauthorised GEMINI_API_KEY. "
            "Get a free key at https://aistudio.google.com/app/apikey"
        )
    if resp.status_code == 429:
        raise RuntimeError(
            "Gemini free-tier rate limit hit. Wait a moment and try again."
        )
    if not resp.ok:
        raise RuntimeError(f"Gemini API error {resp.status_code} ({label}): {resp.text[:300]}")
    return resp.json()


# ── FAISS helpers ─────────────────────────────────────────────────────
def _index_path():
    return os.path.join(current_app.config["VECTOR_STORE_PATH"], "faiss.index")


def load_index():
    global _index, _index_size
    p = _index_path()
    if os.path.exists(p):
        _index = faiss.read_index(p)
        _index_size = _index.ntotal
    else:
        _index = faiss.IndexFlatL2(EMBED_DIM)
        _index_size = 0
    return _index


def save_index():
    faiss.write_index(_index, _index_path())


# ── Embedding via Gemini text-embedding-004 ───────────────────────────
def get_embedding(text):
    url = f"{GEMINI_BASE}/models/gemini-embedding-001:embedContent?key={_key()}"
    payload = {
        "model": "models/gemini-embedding-001",
        "content": {"parts": [{"text": text[:8000]}]},
    }
    data = _check_resp(
        requests.post(url, json=payload, timeout=30),
        "embedding"
    )
    return np.array(data["embedding"]["values"], dtype="float32")


# ── Indexing ──────────────────────────────────────────────────────────
def add_embeddings(texts):
    global _index, _index_size
    if _index is None:
        load_index()
    vectors = np.array([get_embedding(t) for t in texts], dtype="float32")
    start_id = _index_size
    _index.add(vectors)
    _index_size += len(texts)
    save_index()
    return list(range(start_id, start_id + len(texts)))


# ── Search ────────────────────────────────────────────────────────────
def search_similar(query_text, k=4):
    global _index
    if _index is None:
        load_index()
    if _index.ntotal == 0:
        return []
    vec = get_embedding(query_text).reshape(1, -1)
    k = min(k, _index.ntotal)
    _, ids = _index.search(vec, k)
    return [int(i) for i in ids[0] if i >= 0]


# ── Answer generation via Gemini 1.5 Flash ───────────────────────────
def generate_answer(question, chunks):
    context = "\n\n---\n\n".join(
        f"[Source: {c['original_name']}]\n{c['chunk_text']}" for c in chunks
    )
    prompt = (
        "You are a helpful knowledge base assistant. "
        "Answer the question using ONLY the context below. "
        "If the answer is not in the context, say 'I couldn't find relevant information.'\n\n"
        f"Context:\n{context}\n\nQuestion: {question}\n\nAnswer:"
    )

    url = f"{GEMINI_BASE}/models/gemini-flash-lite-latest:generateContent?key={_key()}"
    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {
            "temperature": 0.2,
            "maxOutputTokens": 600,
        },
    }
    data = _check_resp(
        requests.post(url, json=payload, timeout=60),
        "chat"
    )
    return data["candidates"][0]["content"]["parts"][0]["text"].strip()
