from __future__ import annotations

import logging
from typing import List, Optional

from app.clients.internal_embedding import InternalEmbeddingClient
from app.config import RAGSettings
from app.repositories.chunk_repository import ChunkRepository
from app.utils.trace import log_event, new_trace_id

LOG = logging.getLogger(__name__)


class EmbeddingService:
    def __init__(
        self,
        embedding_client: InternalEmbeddingClient,
        chunk_repository: ChunkRepository,
        rag_settings: RAGSettings,
    ) -> None:
        self.embedding_client = embedding_client
        self.chunk_repository = chunk_repository
        self.rag_settings = rag_settings

    def embed_pending_chunks(self, doc_id: Optional[str] = None, retry_failed: bool = False, trace_id: str = "") -> int:
        trace_id = trace_id or new_trace_id()
        chunks = self.chunk_repository.list_for_embedding(doc_id=doc_id, retry_failed=retry_failed)
        if not chunks:
            return 0
        texts = [chunk.content for chunk in chunks]
        try:
            vectors = self.embedding_client.embed_texts(texts, dimension=self.rag_settings.embedding_dimension)
        except Exception as exc:  # noqa: BLE001
            for chunk in chunks:
                self.chunk_repository.mark_embedding_status(chunk.id, "failed", str(exc))
                log_event(
                    LOG,
                    trace_id=trace_id,
                    step="embedding_batch",
                    status="failed",
                    doc_id=chunk.doc_id,
                    source_id=chunk.source_id,
                    chunk_id=chunk.id,
                    error=str(exc),
                )
            raise

        for chunk, vector in zip(chunks, vectors):
            self.chunk_repository.update_embedding(chunk.id, vector, "success", "")
            log_event(
                LOG,
                trace_id=trace_id,
                step="embedding_chunk",
                status="success",
                doc_id=chunk.doc_id,
                source_id=chunk.source_id,
                chunk_id=chunk.id,
            )
        return len(chunks)
