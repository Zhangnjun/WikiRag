from __future__ import annotations

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class WikiSearchRequest(BaseModel):
    search_query: str
    page: int = 1
    page_size: int = 10
    search_scope: str = "ALL"
    is_accurate: bool = False
    wiki_sn: Optional[str] = None
    domain_id: Optional[int] = None
    kanban_id: Optional[str] = None
    sort_field: Optional[str] = None
    sort_way: Optional[str] = None
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
    created_by_name: str = ""
    created_by_account: str = ""
    updated_at: str = ""
    created_at: str = ""
    url: str = ""
    raw: Dict[str, Any]


class WikiSearchResponse(BaseModel):
    items: List[WikiSearchItemResponse]
    total: int
    page: int
    page_size: int


class WikiAuthorSearchRequest(BaseModel):
    author_query: str
    page_size: int = 10
    max_pages: int = 3
    wiki_sn: Optional[str] = None
    kanban_id: Optional[str] = None
    cookie: Optional[str] = None


class WikiAuthorStatsResponse(BaseModel):
    author_query: str
    article_count: int
    latest_updated_at: str = ""
    wiki_titles: List[str] = Field(default_factory=list)
    high_frequency_keywords: List[str] = Field(default_factory=list)


class WikiAuthorSearchResponse(BaseModel):
    stats: WikiAuthorStatsResponse
    items: List[WikiSearchItemResponse]


class WikiAuthorCandidateRequest(BaseModel):
    topic_query: str
    page_size: int = 10
    candidate_limit: int = 5
    author_page_size: int = 20
    author_max_pages: int = 3
    wiki_sn: Optional[str] = None
    kanban_id: Optional[str] = None
    cookie: Optional[str] = None


class WikiAuthorCandidateItemResponse(BaseModel):
    created_by_name: str = ""
    created_by_account: str = ""
    article_count: int
    latest_updated_at: str = ""
    possible_skills: List[str] = Field(default_factory=list)
    evidence: List[str] = Field(default_factory=list)
    topic_concentration: float = 0.0
    recommendation: str = ""
    related_articles: List[WikiSearchItemResponse] = Field(default_factory=list)


class WikiAuthorCandidateResponse(BaseModel):
    topic_query: str
    candidates: List[WikiAuthorCandidateItemResponse]


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
    project_fit: str = ""
    project_evidence: List[str] = Field(default_factory=list)


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
