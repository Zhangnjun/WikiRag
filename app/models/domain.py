from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


PENDING = "待补充"

DOC_TYPES = {
    "新手知识库",
    "运维知识库",
    "内部研发协作知识库",
    "配置与治理知识库",
}


@dataclass
class SourceRecord:
    source_id: str
    source_type: str
    source_url: str
    source_title: str
    raw_content: str
    updated_at: str
    owner: str
    tags: List[str] = field(default_factory=list)
    created_at: str = ""
    is_archived: bool = False
    extra_notes: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)
    import_status: str = "pending"
    normalize_status: str = "pending"
    last_error_message: str = ""
    last_synced_at: str = ""
    external_id: str = ""
    linked_doc_types: List[str] = field(default_factory=list)


@dataclass
class KnowledgeDocument:
    doc_id: str
    title: str
    doc_type: str
    knowledge_domain: str
    applicable_mode: str
    product_line: List[str]
    roles: List[str]
    owner: str
    keywords: List[str]
    summary: str
    scenarios: str
    prerequisites: str
    core_content: str
    steps: str
    branch_logic: str
    risks: str
    best_practices: str
    related_docs: str
    faq: str
    appendix: str
    image_notes: Dict[str, str]
    markdown_content: str
    source_id: str
    source_url: str
    created_at: str
    updated_at: str
    is_archived: bool
    normalize_mode: str
    ai_enhanced: bool
    source_title: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ChunkRecord:
    id: str
    doc_id: str
    source_id: str
    chunk_index: int
    section_title: str
    content: str
    token_count: int
    embedding_status: str
    is_active: bool
    created_at: str
    updated_at: str
    error_message: str = ""
    embedding_json: List[float] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class RAGSession:
    session_id: str
    history: List[Dict[str, Any]]
    created_at: str
    updated_at: str


@dataclass
class RAGQueryLog:
    id: str
    session_id: str
    query: str
    answer: str
    retrieved_chunk_ids: List[str]
    citations: List[Dict[str, Any]]
    status: str
    latency_ms: int
    created_at: str
    debug_info: Dict[str, Any] = field(default_factory=dict)
