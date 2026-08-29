import os
from typing import List, Dict, Any, Optional

import chromadb
from chromadb.config import Settings
from sentence_transformers import SentenceTransformer

CHROMA_PATH = os.path.join(os.path.dirname(__file__), "chroma_store")
COLLECTION_NAME = "growth_entries"
EMBED_MODEL_NAME = "all-MiniLM-L6-v2"

_client: Optional[chromadb.PersistentClient] = None
_collection = None
_embedder: Optional[SentenceTransformer] = None


def _get_client() -> chromadb.PersistentClient:
    global _client
    if _client is None:
        _client = chromadb.PersistentClient(
            path=CHROMA_PATH,
            settings=Settings(anonymized_telemetry=False),
        )
    return _client


def _get_collection():
    global _collection
    if _collection is None:
        client = _get_client()
        _collection = client.get_or_create_collection(
            name=COLLECTION_NAME,
            metadata={"hnsw:space": "cosine"},
        )
    return _collection


def _get_embedder() -> SentenceTransformer:
    global _embedder
    if _embedder is None:
        # Use the local cache with no network calls.
        # Falls back to downloading only if the model isn't cached yet.
        try:
            _embedder = SentenceTransformer(EMBED_MODEL_NAME, local_files_only=True)
        except Exception:
            _embedder = SentenceTransformer(EMBED_MODEL_NAME)
    return _embedder


def embed_text(text: str) -> List[float]:
    return _get_embedder().encode(text, normalize_embeddings=True).tolist()


def _entry_to_document(entry: Dict[str, Any]) -> str:
    parts = [
        entry.get("context", ""),
        entry.get("insight", ""),
        entry.get("skill_area", ""),
        entry.get("entry_type", ""),
        entry.get("emotion", ""),
        entry.get("project", ""),
        entry.get("impact") or "",
        " ".join(entry.get("tags", [])),
    ]
    return " | ".join(p for p in parts if p)


def get_indexed_ids() -> set:
    """Return the set of entry IDs already stored in ChromaDB."""
    collection = _get_collection()
    result = collection.get(include=[])
    return set(result["ids"])


def add_entry(entry_id: str, entry: Dict[str, Any]) -> None:
    """Embed an entry and upsert it into ChromaDB."""
    collection = _get_collection()
    document = _entry_to_document(entry)
    vector = embed_text(document)

    flat_meta = {
        "date": entry.get("date", ""),
        "entry_type": entry.get("entry_type", ""),
        "skill_area": entry.get("skill_area", ""),
        "project": entry.get("project", ""),
        "emotion": entry.get("emotion", ""),
        "tags": ",".join(entry.get("tags", [])),
    }

    collection.upsert(
        ids=[entry_id],
        embeddings=[vector],
        documents=[document],
        metadatas=[flat_meta],
    )


def search(query: str, n_results: int = 5) -> List[Dict[str, Any]]:
    collection = _get_collection()
    total = collection.count()
    if total == 0:
        return []

    effective_n = min(n_results, total)
    query_vector = embed_text(query)

    results = collection.query(
        query_embeddings=[query_vector],
        n_results=effective_n,
        include=["documents", "metadatas", "distances"],
    )

    hits = []
    for entry_id, distance, meta, doc in zip(
        results["ids"][0],
        results["distances"][0],
        results["metadatas"][0],
        results["documents"][0],
    ):
        hits.append(
            {
                "id": entry_id,
                "similarity": round(1 - distance, 4),
                "document": doc,
                "meta": meta,
            }
        )
    return hits
