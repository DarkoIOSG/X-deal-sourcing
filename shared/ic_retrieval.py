import pickle
import numpy as np
from pathlib import Path
from voyageai import Client
from dotenv import load_dotenv

load_dotenv()
INDEX_PATH = Path("data/ic_index.pkl")
_voyage = Client()
_records = None
_matrix = None

def _ensure_loaded():
    global _records, _matrix
    if _records is not None:
        return
    with open(INDEX_PATH, "rb") as f:
        _records = pickle.load(f)
    m = np.array([r["embedding"] for r in _records])
    _matrix = m / np.linalg.norm(m, axis=1, keepdims=True)

def retrieve_ic_context(query: str, top_k: int = 4) -> list[dict]:
    _ensure_loaded()
    q = np.array(_voyage.embed([query], model="voyage-4-lite", input_type="query").embeddings[0])
    q = q / np.linalg.norm(q)
    sims = _matrix @ q
    top = np.argsort(-sims)[:top_k]
    return [
        {
            "text": _records[i].get("raw_text") or _records[i]["text"],
            "source_type": _records[i]["source_type"],
            "source_file": _records[i]["source_file"],
            "date": _records[i]["date"],
            "score": float(sims[i]),
        }
        for i in top
    ]
