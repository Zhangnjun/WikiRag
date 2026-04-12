from __future__ import annotations

import logging
import uuid
from typing import List

from app.models.domain import ChunkRecord, KnowledgeDocument
from app.repositories.chunk_repository import ChunkRepository
from app.utils.text import clean_text, tokenize
from app.utils.time import now_iso
from app.utils.trace import log_event, new_trace_id

LOG = logging.getLogger(__name__)


class ChunkService:
    def __init__(self, chunk_repository: ChunkRepository) -> None:
        self.chunk_repository = chunk_repository

    def rebuild_chunks_for_document(self, document: KnowledgeDocument, trace_id: str = "") -> List[ChunkRecord]:
        trace_id = trace_id or new_trace_id()
        self.chunk_repository.deactivate_by_doc_id(document.doc_id)
        chunks = self._split_markdown(document)
        created = self.chunk_repository.create_many(chunks)
        for chunk in created:
            log_event(
                LOG,
                trace_id=trace_id,
                step="chunk_create",
                status="success",
                doc_id=document.doc_id,
                source_id=document.source_id,
                chunk_id=chunk.id,
            )
        return created

    def list_chunks(self, doc_id: str) -> List[ChunkRecord]:
        return self.chunk_repository.list_by_doc_id(doc_id)

    def _split_markdown(self, document: KnowledgeDocument) -> List[ChunkRecord]:
        lines = document.markdown_content.splitlines()
        sections = []
        current_title = document.title
        current_lines = []
        for line in lines:
            if line.startswith("## "):
                if current_lines:
                    sections.append((current_title, "\n".join(current_lines).strip()))
                current_title = clean_text(line.lstrip("# "))
                current_lines = []
            else:
                current_lines.append(line)
        if current_lines:
            sections.append((current_title, "\n".join(current_lines).strip()))

        chunks = []
        index = 0
        timestamp = now_iso()
        for section_title, section_content in sections:
            parts = self._split_section_content(section_title, section_content)
            for part in parts:
                content = clean_text(part.replace("\n\n", "\n"))
                if not content:
                    continue
                chunks.append(
                    ChunkRecord(
                        id=str(uuid.uuid4()),
                        doc_id=document.doc_id,
                        source_id=document.source_id,
                        chunk_index=index,
                        section_title=section_title,
                        content=content,
                        token_count=len(tokenize(content)),
                        embedding_status="pending",
                        is_active=True,
                        created_at=timestamp,
                        updated_at=timestamp,
                        metadata={"doc_type": document.doc_type},
                    )
                )
                index += 1
        return chunks

    def _split_section_content(self, section_title: str, content: str) -> List[str]:
        if not content:
            return []
        paragraph_groups = []
        buffer = []
        current_size = 0
        for block in content.split("\n"):
            cleaned = clean_text(block)
            if not cleaned:
                continue
            block_tokens = len(tokenize(cleaned))
            if current_size + block_tokens > 180 and buffer:
                paragraph_groups.append("\n".join(buffer))
                buffer = [cleaned]
                current_size = block_tokens
            else:
                buffer.append(cleaned)
                current_size += block_tokens
        if buffer:
            paragraph_groups.append("\n".join(buffer))
        return paragraph_groups or [content]
