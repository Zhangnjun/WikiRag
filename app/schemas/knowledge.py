from __future__ import annotations

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class NormalizeInlineSource(BaseModel):
    source_title: str
    source_type: str
    source_url: str
    raw_content: str
    owner: Optional[str] = None
    tags: List[str] = Field(default_factory=list)
    updated_at: Optional[str] = None
    extra_notes: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


class KnowledgeNormalizeRequest(BaseModel):
    source_id: Optional[str] = None
    source: Optional[NormalizeInlineSource] = None
    use_ai: bool = False
    doc_type: Optional[str] = None


class KnowledgeDocumentResponse(BaseModel):
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
    source_title: str
    metadata: Dict[str, Any]


class KnowledgeListResponse(BaseModel):
    items: List[KnowledgeDocumentResponse]
    total: int


class KnowledgeUpdateRequest(BaseModel):
    title: Optional[str] = None
    doc_type: Optional[str] = None
    knowledge_domain: Optional[str] = None
    applicable_mode: Optional[str] = None
    product_line: Optional[List[str]] = None
    roles: Optional[List[str]] = None
    owner: Optional[str] = None
    keywords: Optional[List[str]] = None
    summary: Optional[str] = None
    scenarios: Optional[str] = None
    prerequisites: Optional[str] = None
    core_content: Optional[str] = None
    steps: Optional[str] = None
    branch_logic: Optional[str] = None
    risks: Optional[str] = None
    best_practices: Optional[str] = None
    related_docs: Optional[str] = None
    faq: Optional[str] = None
    appendix: Optional[str] = None
    image_notes: Optional[Dict[str, str]] = None
    markdown_content: Optional[str] = None
    is_archived: Optional[bool] = None
    metadata: Optional[Dict[str, Any]] = None


class KnowledgeSearchRequest(BaseModel):
    query: str
    doc_type: Optional[str] = None
    product_line: Optional[str] = None
    role: Optional[str] = None
    keyword: Optional[str] = None


class KnowledgeRenormalizeRequest(BaseModel):
    use_ai: bool = False
    doc_type: Optional[str] = None
