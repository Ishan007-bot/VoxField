"""RAG (Retrieval-Augmented Generation) engine for VoxField.

Uses Google Gemini embedding API for vectorizing asset documents and
scikit-learn cosine similarity for search. No torch/FAISS needed.

Falls back gracefully to keyword matching if embeddings can't be generated
(e.g. no API key, no network on startup).

Embeddings are built once on startup from the asset DB and cached in memory.
"""
import json
import os
import numpy as np
from typing import Optional

from dotenv import load_dotenv

load_dotenv()

from db import db

_embeddings = None       # np.ndarray of shape (N, dim)
_doc_map: list[dict] = []  # index position -> asset dict
_chunks: list[str] = []     # index position -> text chunk
_ready = False
_init_error: Optional[str] = None
_embed_fn = None         # callable: list[str] -> np.ndarray


def _build_doc_text(asset: dict, history: list[dict]) -> str:
    """Build a single searchable text block for one asset."""
    specs = json.loads(asset["specs"]) if isinstance(asset["specs"], str) else asset["specs"]
    procs = json.loads(asset["procedures"]) if isinstance(asset["procedures"], str) else asset["procedures"]

    lines = [
        f"Asset {asset['code']} {asset['name']}",
        f"Type: {asset['type']}",
        f"Location: {asset['location']}",
        "Specifications: " + "; ".join(f"{k.replace('_',' ')}: {v}" for k, v in specs.items()),
    ]
    for p in procs:
        lines.append(f"Procedure {p['name']}: " + " → ".join(p["steps"]))
    if history:
        lines.append("Maintenance history: " + "; ".join(
            f"{h['date']} by {h['technician']}: {h['summary']}" for h in history
        ))
    return "\n".join(lines)


def _init_gemini_embeddings():
    """Try to set up Gemini embedding function."""
    global _embed_fn

    # Try Vertex AI first
    use_vertex = os.getenv("USE_VERTEX", "false").strip().lower() == "true"
    cred_path = os.getenv("GOOGLE_APPLICATION_CREDENTIALS", "").strip()
    if cred_path and not os.path.isabs(cred_path):
        cred_path = os.path.join(os.path.dirname(__file__), cred_path)

    if use_vertex and cred_path and os.path.exists(cred_path):
        try:
            os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = cred_path
            from vertexai.language_models import TextEmbeddingModel
            model = TextEmbeddingModel.from_pretrained("gemini-embedding-001")

            def embed_vertex(texts):
                # Vertex embedding API accepts batches up to 250
                all_vecs = []
                for i in range(0, len(texts), 200):
                    batch = texts[i:i+200]
                    embeddings = model.get_embeddings(batch)
                    all_vecs.extend([e.values for e in embeddings])
                return np.array(all_vecs, dtype=np.float32)

            _embed_fn = embed_vertex
            return True
        except Exception as e:
            print(f"RAG: Vertex embeddings failed: {e}")

    # Try AI Studio (genai)
    api_key = os.getenv("GEMINI_API_KEY", "").strip()
    if api_key:
        try:
            import google.generativeai as genai
            genai.configure(api_key=api_key)

            def embed_studio(texts):
                all_vecs = []
                for i in range(0, len(texts), 100):
                    batch = texts[i:i+100]
                    result = genai.embed_content(
                        model="models/gemini-embedding-001",
                        content=batch,
                        task_type="retrieval_document",
                    )
                    all_vecs.extend(result["embedding"])
                return np.array(all_vecs, dtype=np.float32)

            _embed_fn = embed_studio
            return True
        except Exception as e:
            print(f"RAG: AI Studio embeddings failed: {e}")

    return False


def _cosine_similarity(query_vec, doc_vecs):
    """Compute cosine similarity between a query vector and document vectors."""
    from sklearn.metrics.pairwise import cosine_similarity as cs
    return cs(query_vec.reshape(1, -1), doc_vecs)[0]


def _init_rag():
    """Build embedding index from all assets. Idempotent."""
    global _embeddings, _doc_map, _chunks, _ready, _init_error
    if _ready or _init_error is not None:
        return _ready

    if not _init_gemini_embeddings():
        _init_error = "no embedding backend available"
        print("RAG: no embedding backend — will use keyword fallback")
        return False

    try:
        with db() as conn:
            assets = [dict(r) for r in conn.execute("SELECT * FROM assets").fetchall()]
            all_history = {}
            for row in conn.execute(
                "SELECT asset_code, date, summary, technician FROM maintenance_history ORDER BY date DESC"
            ).fetchall():
                all_history.setdefault(row["asset_code"], []).append(dict(row))

        if not assets:
            _init_error = "no assets in DB"
            return False

        texts = []
        for a in assets:
            hist = all_history.get(a["code"], [])
            doc_text = _build_doc_text(a, hist)
            texts.append(doc_text)
            _doc_map.append(a)
            _chunks.append(doc_text)

            # Also index individual procedures as separate chunks
            procs = json.loads(a["procedures"]) if isinstance(a["procedures"], str) else a["procedures"]
            for p in procs:
                proc_text = f"Asset {a['code']} {a['name']} procedure {p['name']}: " + " → ".join(p["steps"])
                texts.append(proc_text)
                _doc_map.append(a)
                _chunks.append(proc_text)

        _embeddings = _embed_fn(texts)
        _ready = True
        print(f"RAG index built: {len(texts)} chunks from {len(assets)} assets, dim={_embeddings.shape[1]}")
        return True

    except Exception as e:
        _init_error = str(e)
        print(f"RAG init failed (will use keyword fallback): {e}")
        return False


def rag_available() -> bool:
    """Check if the RAG engine is ready."""
    return _init_rag()


def search(query: str, top_k: int = 3) -> list[dict]:
    """Semantic search over asset documents.

    Returns list of {"asset": dict, "chunk": str, "score": float}
    sorted by relevance (highest first).
    """
    if not _init_rag():
        return []

    try:
        # Embed the query (use retrieval_query task type for AI Studio)
        import google.generativeai as genai
        try:
            result = genai.embed_content(
                model="models/gemini-embedding-001",
                content=query,
                task_type="retrieval_query",
            )
            query_vec = np.array(result["embedding"], dtype=np.float32)
        except Exception:
            query_vec = _embed_fn([query])[0]

        scores = _cosine_similarity(query_vec, _embeddings)

        # Get top-k unique assets
        ranked = np.argsort(scores)[::-1]
        results = []
        seen_codes = set()
        for idx in ranked:
            if len(results) >= top_k:
                break
            asset = _doc_map[idx]
            if asset["code"] in seen_codes:
                continue
            seen_codes.add(asset["code"])
            results.append({
                "asset": asset,
                "chunk": _chunks[idx],
                "score": float(scores[idx]),
            })
        return results
    except Exception as e:
        print(f"RAG search error: {e}")
        return []


def find_best_asset(query: str) -> Optional[dict]:
    """Return the single best-matching asset for a query, or None."""
    results = search(query, top_k=1)
    if results and results[0]["score"] > 0.25:
        return results[0]["asset"]
    return None
