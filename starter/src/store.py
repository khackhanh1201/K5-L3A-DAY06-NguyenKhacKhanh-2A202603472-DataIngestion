"""Store and search vectors with Chroma (persistent, local on disk).

Chosen instead of PostgreSQL + pgvector because Docker Desktop needs WSL2,
which is not available on this machine. Chroma is an allowed alternative
(see ../../docs/README.md): persistent storage, vector search, metadata filter.

- One collection per index, e.g. ``chunks_A`` and ``chunks_B``.
  Strategy C searches index B with a metadata filter.
- Metric: cosine. Chroma uses an HNSW index, i.e. *approximate* search.
- Vectors come from our own embedder; Chroma's default embedding is disabled.
"""
import hashlib
from pathlib import Path
from typing import Any

import chromadb

from .models import Chunk

# Only metadata keys listed here may be used as filters (keep in sync with manifest).
ALLOWED_FILTERS = {"document_id", "chapter"}


def _clean_metadata(chunk: Chunk) -> dict[str, Any]:
    """Chroma accepts only flat str/int/float/bool values (no None, no nesting)."""
    meta: dict[str, Any] = {
        "document_id": chunk.document_id,
        "source": chunk.source,
        "page": int(chunk.page),
        "content_hash": hashlib.sha256(chunk.text.encode("utf-8")).hexdigest(),
    }
    for key, value in chunk.metadata.items():
        if value is None:
            continue
        if not isinstance(value, (str, int, float, bool)):
            raise ValueError(f"Metadata '{key}' must be a scalar, got {type(value).__name__}")
        meta[key] = value
    return meta


class ChromaStore:
    def __init__(self, persist_dir: str | Path, dimensions: int) -> None:
        self.persist_dir = Path(persist_dir)
        self.dim = dimensions
        self.client = chromadb.PersistentClient(path=str(self.persist_dir))

    def _collection(self, index: str):
        return self.client.get_or_create_collection(
            name=f"chunks_{index}",
            embedding_function=None,
            configuration={"hnsw": {"space": "cosine"}},
            metadata={"dimensions": self.dim},
        )

    def create_schema(self) -> None:
        """Chroma has no schema; collections are created lazily in ``_collection``."""

    def upsert(self, index: str, chunks: list[Chunk], vectors: list[list[float]]) -> None:
        if len(chunks) != len(vectors):
            raise ValueError("chunks/vectors length mismatch")
        if any(len(v) != self.dim for v in vectors):
            raise ValueError(f"every vector must have {self.dim} dimensions")
        ids = [c.chunk_id for c in chunks]
        if len(set(ids)) != len(ids):
            raise ValueError("duplicate chunk_id in one upsert")

        col = self._collection(index)
        # Remove chunks of these documents that no longer exist (document changed).
        new_ids_by_doc: dict[str, set[str]] = {}
        for c in chunks:
            new_ids_by_doc.setdefault(c.document_id, set()).add(c.chunk_id)
        for doc, new_ids in new_ids_by_doc.items():
            old_ids = col.get(where={"document_id": doc}, include=[])["ids"]
            obsolete = [i for i in old_ids if i not in new_ids]
            if obsolete:
                col.delete(ids=obsolete)

        batch = self.client.get_max_batch_size()
        for start in range(0, len(chunks), batch):
            part = chunks[start:start + batch]
            col.upsert(
                ids=[c.chunk_id for c in part],
                embeddings=vectors[start:start + batch],
                documents=[c.text for c in part],
                metadatas=[_clean_metadata(c) for c in part],
            )

    def count(self, index: str) -> int:
        return self._collection(index).count()

    def search(self, index: str, query_vector: list[float], top_k: int = 3,
               filters: dict[str, Any] | None = None) -> list[dict[str, Any]]:
        if len(query_vector) != self.dim:
            raise ValueError(f"query vector must have {self.dim} dimensions")
        clauses = []
        for key, value in (filters or {}).items():
            if key not in ALLOWED_FILTERS:
                raise ValueError(f"filter not allowed: {key}")
            clauses.append({key: value})
        where = None if not clauses else clauses[0] if len(clauses) == 1 else {"$and": clauses}

        res = self._collection(index).query(
            query_embeddings=[query_vector], n_results=top_k, where=where,
            include=["documents", "metadatas", "distances"],
        )
        hits = []
        for cid, text, meta, dist in zip(res["ids"][0], res["documents"][0],
                                          res["metadatas"][0], res["distances"][0]):
            hits.append({
                "chunk_id": cid,
                "document_id": meta["document_id"],
                "source": meta["source"],
                "page": meta["page"],
                "text": text,
                "metadata": meta,
                "score": 1.0 - float(dist),  # cosine similarity
            })
        return hits
