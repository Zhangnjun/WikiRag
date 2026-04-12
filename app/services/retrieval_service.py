from __future__ import annotations

from typing import Any, Dict, List, Tuple

from app.repositories.chunk_repository import ChunkRepository
from app.services.vector_search_service import VectorSearchService
from app.utils.text import tokenize


class RetrievalService:
    def __init__(
        self,
        chunk_repository: ChunkRepository,
        vector_search_service: VectorSearchService,
    ) -> None:
        self.chunk_repository = chunk_repository
        self.vector_search_service = vector_search_service

    def hybrid_retrieve(self, query: str, top_k: int = 5, filters: Dict[str, Any] = None) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
        filters = filters or {}
        keyword_hits = self._keyword_search(query, top_k=top_k * 2, filters=filters)
        vector_hits = self.vector_search_service.search(query, top_k=top_k * 2, filters=filters)
        merged = {}

        for rank, hit in enumerate(keyword_hits, start=1):
            entry = merged.setdefault(hit["chunk_id"], dict(hit))
            entry["keyword_rank"] = rank
            entry["keyword_score"] = hit["keyword_score"]
            entry["hybrid_score"] = entry.get("hybrid_score", 0.0) + (1.0 / (60 + rank)) + hit["keyword_score"]

        for rank, hit in enumerate(vector_hits, start=1):
            entry = merged.setdefault(hit["chunk_id"], dict(hit))
            entry["vector_rank"] = rank
            entry["vector_score"] = hit["vector_score"]
            entry["hybrid_score"] = entry.get("hybrid_score", 0.0) + (1.0 / (60 + rank)) + hit["vector_score"]

        final_hits = sorted(merged.values(), key=lambda item: item.get("hybrid_score", 0.0), reverse=True)[:top_k]
        debug_info = {
            "keyword_hits": keyword_hits[:top_k],
            "vector_hits": vector_hits[:top_k],
            "final_hits": final_hits,
        }
        return final_hits, debug_info

    def _keyword_search(self, query: str, top_k: int, filters: Dict[str, Any]) -> List[Dict[str, Any]]:
        chunks = self.chunk_repository.fetch_active_chunks(filters, require_embedding=False)
        query_tokens = set(tokenize(query.lower()))
        hits = []
        for row in chunks:
            chunk_tokens = tokenize((row["content"] or "").lower())
            overlap = sum(1 for token in chunk_tokens if token in query_tokens)
            if overlap <= 0:
                continue
            score = overlap / max(len(query_tokens), 1)
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
                    "product_line": row["product_line_json"],
                    "keyword_score": round(score, 6),
                    "keyword_hits": sorted(list(query_tokens & set(chunk_tokens))),
                }
            )
        hits.sort(key=lambda item: item["keyword_score"], reverse=True)
        return hits[:top_k]
