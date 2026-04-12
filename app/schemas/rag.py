from __future__ import annotations

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class RAGFilter(BaseModel):
    doc_type: Optional[str] = None
    source_type: Optional[str] = None
    product_line: Optional[str] = None
    source_id: Optional[str] = None


class RAGQueryRequest(BaseModel):
    query: str
    top_k: int = 5
    use_rerank: bool = True
    use_ai: bool = False
    filters: RAGFilter = Field(default_factory=RAGFilter)
    debug: bool = False
    session_id: Optional[str] = None


class CitationResponse(BaseModel):
    chunk_id: str
    doc_id: str
    source_id: str
    doc_title: str
    section_title: str
    source_url: str
    chunk_summary: str


class RetrievedChunkResponse(BaseModel):
    chunk_id: str
    doc_id: str
    source_id: str
    doc_title: str
    doc_type: str
    source_type: str
    section_title: str
    content: str
    score: float
    score_detail: Dict[str, Any]


class RAGQueryResponse(BaseModel):
    session_id: str
    status: str
    latency_ms: int
    answer: str
    citations: List[CitationResponse]
    retrieved_chunks: List[RetrievedChunkResponse]
    debug_info: Optional[Dict[str, Any]] = None
