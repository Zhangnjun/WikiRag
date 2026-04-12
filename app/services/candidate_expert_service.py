from __future__ import annotations

from typing import Optional
from uuid import uuid4

from app.core.exceptions import AppError
from app.models.domain import CandidateExpertRecord
from app.repositories.candidate_expert_repository import CandidateExpertRepository
from app.services.expert_profile_service import ExpertProfileService
from app.utils.time import now_iso


class CandidateExpertService:
    def __init__(
        self,
        repository: CandidateExpertRepository,
        expert_profile_service: ExpertProfileService,
    ) -> None:
        self.repository = repository
        self.expert_profile_service = expert_profile_service

    def save_candidate(self, payload: dict) -> CandidateExpertRecord:
        timestamp = now_iso()
        record = CandidateExpertRecord(
            candidate_id=str(uuid4()),
            topic_query=payload.get("topic_query", "").strip(),
            created_by_name=payload.get("created_by_name", "").strip(),
            created_by_account=payload.get("created_by_account", "").strip(),
            article_count=int(payload.get("article_count", 0) or 0),
            latest_updated_at=payload.get("latest_updated_at", "").strip(),
            possible_skills=list(payload.get("possible_skills", []) or []),
            evidence=list(payload.get("evidence", []) or []),
            recommendation=payload.get("recommendation", "").strip(),
            related_articles=list(payload.get("related_articles", []) or []),
            status="待确认",
            notes=payload.get("notes", "").strip(),
            created_at=timestamp,
            updated_at=timestamp,
        )
        if not record.created_by_name and not record.created_by_account:
            raise AppError("candidate missing author identity", 400)
        return self.repository.upsert(record)

    def list_candidates(self, status: Optional[str] = None, topic_query: Optional[str] = None) -> list[CandidateExpertRecord]:
        return self.repository.list_all(status=status, topic_query=topic_query)

    def update_status(self, candidate_id: str, status: str, notes: str = "") -> CandidateExpertRecord:
        if status not in {"待确认", "已采纳", "已忽略"}:
            raise AppError("unsupported candidate status", 400)
        record = self.repository.update_status(candidate_id, status, notes.strip(), now_iso())
        if not record:
            raise AppError("candidate not found", 404)
        return record

    def preview_candidate_profile(self, candidate_id: str) -> dict:
        record = self.repository.get(candidate_id)
        if not record:
            raise AppError("candidate not found", 404)
        person_name = record.created_by_name or record.created_by_account
        focus_topics = [record.topic_query] + list(record.possible_skills[:6])
        preview = self.expert_profile_service.preview_scan(person_name=person_name, focus_topics=focus_topics)
        return {
            "candidate": record,
            "profile_preview": preview,
        }
