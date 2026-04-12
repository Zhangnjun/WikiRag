from __future__ import annotations

from typing import List

from pydantic import BaseModel, Field


class ExpertProfilePreviewRequest(BaseModel):
    person_name: str
    focus_topics: List[str] = Field(default_factory=list)


class ExpertProfilePreviewResponse(BaseModel):
    person_name: str
    status: str
    local_source_count: int
    inferred_skills: List[str] = Field(default_factory=list)
    recommended_scan_queries: List[str] = Field(default_factory=list)
    notes: List[str] = Field(default_factory=list)
