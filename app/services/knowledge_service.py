from __future__ import annotations

from app.core.exceptions import NotFoundError
from app.models.domain import KnowledgeDocument
from app.services.chunk_service import ChunkService
from app.services.embedding_service import EmbeddingService
from app.repositories.knowledge_repository import KnowledgeRepository
from app.repositories.source_repository import SourceRepository
from app.services.normalize_service import KnowledgeNormalizeService
from app.utils.time import now_iso
from app.utils.trace import log_event, new_trace_id

import logging

LOG = logging.getLogger(__name__)


class KnowledgeService:
    def __init__(
        self,
        knowledge_repository: KnowledgeRepository,
        source_repository: SourceRepository,
        normalize_service: KnowledgeNormalizeService,
        chunk_service: ChunkService,
        embedding_service: EmbeddingService,
    ) -> None:
        self.knowledge_repository = knowledge_repository
        self.source_repository = source_repository
        self.normalize_service = normalize_service
        self.chunk_service = chunk_service
        self.embedding_service = embedding_service

    def normalize_from_source(self, source, use_ai: bool, doc_type: str | None, trace_id: str = "") -> KnowledgeDocument:
        trace_id = trace_id or new_trace_id()
        try:
            document = self.normalize_service.normalize(source, use_ai=use_ai, doc_type=doc_type, trace_id=trace_id)
            created = self.knowledge_repository.create(document)
            self.chunk_service.rebuild_chunks_for_document(created, trace_id=trace_id)
            self.embedding_service.embed_pending_chunks(doc_id=created.doc_id, retry_failed=True, trace_id=trace_id)
            self.source_repository.update(
                source.source_id,
                {"normalize_status": "success", "last_error_message": ""},
            )
            log_event(LOG, trace_id=trace_id, step="knowledge_persist", status="success", source_id=source.source_id, external_id=source.external_id, doc_id=created.doc_id)
            return created
        except Exception as exc:  # noqa: BLE001
            self.source_repository.update(
                source.source_id,
                {"normalize_status": "failed", "last_error_message": str(exc)},
            )
            log_event(LOG, trace_id=trace_id, step="knowledge_persist", status="failed", source_id=source.source_id, external_id=source.external_id, error=str(exc))
            raise

    def get_document(self, doc_id: str) -> KnowledgeDocument:
        document = self.knowledge_repository.get(doc_id)
        if not document:
            raise NotFoundError(f"Knowledge document not found: {doc_id}")
        return document

    def list_documents(self, filters: dict) -> list[KnowledgeDocument]:
        return self.knowledge_repository.list_filtered(filters)

    def update_document(self, doc_id: str, fields: dict) -> KnowledgeDocument:
        fields["updated_at"] = now_iso()
        document = self.knowledge_repository.update(doc_id, fields)
        if not document:
            raise NotFoundError(f"Knowledge document not found: {doc_id}")
        if any(
            key in fields
            for key in [
                "title",
                "summary",
                "scenarios",
                "prerequisites",
                "core_content",
                "steps",
                "branch_logic",
                "risks",
                "best_practices",
                "related_docs",
                "faq",
                "appendix",
                "markdown_content",
            ]
        ):
            trace_id = new_trace_id()
            self.chunk_service.rebuild_chunks_for_document(document, trace_id=trace_id)
            self.embedding_service.embed_pending_chunks(doc_id=document.doc_id, retry_failed=True, trace_id=trace_id)
        return document

    def archive_document(self, doc_id: str) -> KnowledgeDocument:
        return self.update_document(doc_id, {"is_archived": True})

    def search_documents(self, query: str, filters: dict) -> list[KnowledgeDocument]:
        return self.knowledge_repository.search(query, filters)

    def renormalize_document(self, doc_id: str, use_ai: bool, doc_type: str | None, trace_id: str = "") -> KnowledgeDocument:
        trace_id = trace_id or new_trace_id()
        current = self.get_document(doc_id)
        source = self.source_repository.get(current.source_id)
        if not source:
            raise NotFoundError("Source not found for document: %s" % current.source_id)
        regenerated = self.normalize_service.normalize(source, use_ai=use_ai, doc_type=doc_type or current.doc_type, trace_id=trace_id)
        updated = self.knowledge_repository.update(
            doc_id,
            {
                "title": regenerated.title,
                "doc_type": regenerated.doc_type,
                "knowledge_domain": regenerated.knowledge_domain,
                "applicable_mode": regenerated.applicable_mode,
                "product_line": regenerated.product_line,
                "roles": regenerated.roles,
                "owner": regenerated.owner,
                "keywords": regenerated.keywords,
                "summary": regenerated.summary,
                "scenarios": regenerated.scenarios,
                "prerequisites": regenerated.prerequisites,
                "core_content": regenerated.core_content,
                "steps": regenerated.steps,
                "branch_logic": regenerated.branch_logic,
                "risks": regenerated.risks,
                "best_practices": regenerated.best_practices,
                "related_docs": regenerated.related_docs,
                "faq": regenerated.faq,
                "appendix": regenerated.appendix,
                "image_notes": regenerated.image_notes,
                "markdown_content": regenerated.markdown_content,
                "updated_at": now_iso(),
                "normalize_mode": regenerated.normalize_mode,
                "ai_enhanced": regenerated.ai_enhanced,
                "metadata": regenerated.metadata,
            },
        )
        self.chunk_service.rebuild_chunks_for_document(updated, trace_id=trace_id)
        self.embedding_service.embed_pending_chunks(doc_id=updated.doc_id, retry_failed=True, trace_id=trace_id)
        self.source_repository.update(source.source_id, {"normalize_status": "success", "last_error_message": ""})
        log_event(LOG, trace_id=trace_id, step="knowledge_renormalize", status="success", source_id=source.source_id, external_id=source.external_id, doc_id=doc_id)
        return updated
