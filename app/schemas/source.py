from __future__ import annotations

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class SourceImportRequest(BaseModel):
    source_title: Optional[str] = None
    source_type: str
    source_url: Optional[str] = None
    raw_content: Optional[str] = None
    owner: Optional[str] = None
    tags: List[str] = Field(default_factory=list)
    updated_at: Optional[str] = None
    extra_notes: Optional[str] = None
    fetch_from_wiki: bool = False
    wiki_sn: Optional[str] = None
    domain_id: Optional[int] = None
    kanban_id: Optional[int] = None
    search_query: Optional[str] = None
    wiki_items: List[Dict[str, Any]] = Field(default_factory=list)
    skip_if_exists: bool = True
    overwrite_if_exists: bool = False
    cookie: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


class SourceRecordResponse(BaseModel):
    source_id: str
    source_type: str
    source_url: str
    source_title: str
    raw_content: str
    updated_at: str
    owner: str
    tags: List[str]
    created_at: str
    is_archived: bool
    extra_notes: str
    metadata: Dict[str, Any]
    import_status: str
    normalize_status: str
    last_error_message: str
    last_synced_at: str
    external_id: str
    linked_doc_types: List[str]


class SourceListResponse(BaseModel):
    items: List[SourceRecordResponse]
    total: int
    page: int
    page_size: int


class BatchImportItem(BaseModel):
    source_title: Optional[str] = None
    source_type: str
    source_url: Optional[str] = None
    raw_content: Optional[str] = None
    owner: Optional[str] = None
    tags: List[str] = Field(default_factory=list)
    updated_at: Optional[str] = None
    extra_notes: Optional[str] = None
    fetch_from_wiki: bool = False
    wiki_sn: Optional[str] = None
    domain_id: Optional[int] = None
    kanban_id: Optional[int] = None
    cookie: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


class BatchImportRequest(BaseModel):
    items: List[BatchImportItem] = Field(default_factory=list)
    wiki_sns: List[str] = Field(default_factory=list)
    wiki_items: List[Dict[str, Any]] = Field(default_factory=list)
    skip_if_exists: bool = True
    overwrite_if_exists: bool = False
    cookie: Optional[str] = None


class BatchImportItemResult(BaseModel):
    source_id: str = ""
    source_title: str = ""
    external_id: str = ""
    status: str
    message: str


class BatchImportResponse(BaseModel):
    results: List[BatchImportItemResult]
