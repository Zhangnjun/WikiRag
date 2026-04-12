from __future__ import annotations

import json
import math
from typing import Any, Dict, List

from app.clients.internal_embedding import InternalEmbeddingClient
from app.config import RAGSettings
from app.repositories.chunk_repository import ChunkRepository


class VectorSearchService:
    def __init__(
        self,
        embedding_client: InternalEmbeddingClient,
        chunk_repository: ChunkRepository,
        rag_settings: RAGSettings,
    ) -> None:
        self.embedding_client = embedding_client
        self.chunk_repository = chunk_repository
        self.rag_settings = rag_settings

    def search(self, query: str, top_k: int = 5, filters: Dict[str, Any] = None) -> List[Dict[str, Any]]:
        filters = filters or {}
        query_vector = self.embedding_client.embed_texts([query], dimension=self.rag_settings.embedding_dimension)[0]
        chunks = self.chunk_repository.fetch_active_chunks(filters)
        hits = []
        for row in chunks:
            vector = json.loads(row["embedding_json"] or "[]")
            if not vector:
                continue
            score = self._cosine_similarity(query_vector, vector)
            hits.append(
                {
                    "chunk_id": row["id"],
                    "doc_id": row["doc_id"],
                    "source_id": row["source_id"],
                    "section_title": row["section_title"],
                    "content": row["content"],
                    "doc_title": row["doc_title"],
                    "doc_type": row["doc_type"],
                    "source_type": row["source_type"],
                    "source_url": row["source_url"],
                    "product_line": json.loads(row["product_line_json"] or "[]"),
                    "vector_score": round(score, 6),
                }
            )
        hits.sort(key=lambda item: item["vector_score"], reverse=True)
        return hits[:top_k]

    @staticmethod
    def _cosine_similarity(left: List[float], right: List[float]) -> float:
        if not left or not right or len(left) != len(right):
            return 0.0
        dot = sum(a * b for a, b in zip(left, right))
        left_norm = math.sqrt(sum(a * a for a in left)) or 1.0
        right_norm = math.sqrt(sum(b * b for b in right)) or 1.0
        return dot / (left_norm * right_norm)
