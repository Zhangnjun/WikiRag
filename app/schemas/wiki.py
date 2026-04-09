from __future__ import annotations

from typing import Any, Dict, List, Optional

from pydantic import BaseModel


class WikiSearchRequest(BaseModel):
    search_query: str
    page: int = 1
    page_size: int = 10


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
