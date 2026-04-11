from __future__ import annotations

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class WikiSearchRequest(BaseModel):
    search_query: str
    page: int = 1
    page_size: int = 10
    cookie: Optional[str] = None


class WikiSearchItemResponse(BaseModel):
    id: str = ""
    sn: str = ""
    title: str = ""
    summary: str = ""
    domain_id: Optional[int] = None
    domain_title: str = ""
    kanban_id: Optional[int] = None
    kanban_title: str = ""
    updated_at: str = ""
    created_at: str = ""
    url: str = ""
    raw: Dict[str, Any]


class WikiSearchResponse(BaseModel):
    items: List[WikiSearchItemResponse]
    total: int
    page: int
    page_size: int


class WikiRecommendRequest(BaseModel):
    profile_text: str
    focus_topics: List[str] = Field(default_factory=list)
    page_size: int = 5
    max_queries: int = 5
    cookie: Optional[str] = None


class WikiRecommendItemResponse(WikiSearchItemResponse):
    score: float = 0.0
    reason: str = ""
    matched_terms: List[str] = Field(default_factory=list)
    query_used: str = ""
    skill_feasibility: str = ""
    skill_reason: str = ""


class WikiRecommendResponse(BaseModel):
    query_candidates: List[str]
    detected_doc_type: str
    items: List[WikiRecommendItemResponse]


class WikiRecommendExpandedRequest(BaseModel):
    profile_text: str
    focus_topics: List[str] = Field(default_factory=list)
    page_size: int = 10
    max_queries: int = 8
    pages_per_query: int = 2
    min_score: float = 2.5
    cookie: Optional[str] = None


class WikiRecommendSummaryResponse(BaseModel):
    total_candidates: int
    deduped_candidates: int
    high_relevance: int
    medium_relevance: int
    low_relevance: int


class WikiRecommendExpandedResponse(BaseModel):
    query_candidates: List[str]
    detected_doc_type: str
    summary: WikiRecommendSummaryResponse
    items: List[WikiRecommendItemResponse]
