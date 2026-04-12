from __future__ import annotations

import json
from typing import List, Optional

from app.models.domain import CandidateExpertRecord
from app.repositories.sqlite import SQLiteRepository


class CandidateExpertRepository:
    def __init__(self, sqlite_repo: SQLiteRepository) -> None:
        self.sqlite_repo = sqlite_repo

    def upsert(self, record: CandidateExpertRecord) -> CandidateExpertRecord:
        existing = self.find_by_topic_and_author(record.topic_query, record.created_by_name, record.created_by_account)
        candidate_id = existing.candidate_id if existing else record.candidate_id
        created_at = existing.created_at if existing else record.created_at
        status = existing.status if existing else record.status
        notes = existing.notes if existing else record.notes
        with self.sqlite_repo.connect() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO candidate_expert_records (
                    candidate_id, topic_query, created_by_name, created_by_account, article_count,
                    latest_updated_at, possible_skills_json, evidence_json, recommendation,
                    related_articles_json, status, notes, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    candidate_id,
                    record.topic_query,
                    record.created_by_name,
                    record.created_by_account,
                    record.article_count,
                    record.latest_updated_at,
                    json.dumps(record.possible_skills, ensure_ascii=False),
                    json.dumps(record.evidence, ensure_ascii=False),
                    record.recommendation,
                    json.dumps(record.related_articles, ensure_ascii=False),
                    status,
                    notes,
                    created_at,
                    record.updated_at,
                ),
            )
        return self.get(candidate_id)

    def get(self, candidate_id: str) -> Optional[CandidateExpertRecord]:
        with self.sqlite_repo.connect() as conn:
            row = conn.execute(
                "SELECT * FROM candidate_expert_records WHERE candidate_id = ?",
                (candidate_id,),
            ).fetchone()
        return self._to_model(row) if row else None

    def find_by_topic_and_author(
        self,
        topic_query: str,
        created_by_name: str,
        created_by_account: str,
    ) -> Optional[CandidateExpertRecord]:
        with self.sqlite_repo.connect() as conn:
            row = conn.execute(
                """
                SELECT * FROM candidate_expert_records
                WHERE topic_query = ? AND created_by_name = ? AND created_by_account = ?
                LIMIT 1
                """,
                (topic_query, created_by_name, created_by_account),
            ).fetchone()
        return self._to_model(row) if row else None

    def list_all(self, status: str | None = None, topic_query: str | None = None) -> List[CandidateExpertRecord]:
        clauses = ["1=1"]
        values: List[str] = []
        if status:
            clauses.append("status = ?")
            values.append(status)
        if topic_query:
            clauses.append("topic_query LIKE ?")
            values.append(f"%{topic_query}%")
        with self.sqlite_repo.connect() as conn:
            rows = conn.execute(
                "SELECT * FROM candidate_expert_records WHERE %s ORDER BY updated_at DESC, created_at DESC"
                % " AND ".join(clauses),
                values,
            ).fetchall()
        return [self._to_model(row) for row in rows]

    def update_status(self, candidate_id: str, status: str, notes: str, updated_at: str) -> Optional[CandidateExpertRecord]:
        with self.sqlite_repo.connect() as conn:
            conn.execute(
                "UPDATE candidate_expert_records SET status = ?, notes = ?, updated_at = ? WHERE candidate_id = ?",
                (status, notes, updated_at, candidate_id),
            )
        return self.get(candidate_id)

    def _to_model(self, row) -> CandidateExpertRecord:
        return CandidateExpertRecord(
            candidate_id=row["candidate_id"],
            topic_query=row["topic_query"],
            created_by_name=row["created_by_name"],
            created_by_account=row["created_by_account"],
            article_count=row["article_count"],
            latest_updated_at=row["latest_updated_at"],
            possible_skills=json.loads(row["possible_skills_json"]),
            evidence=json.loads(row["evidence_json"]),
            recommendation=row["recommendation"],
            related_articles=json.loads(row["related_articles_json"]),
            status=row["status"],
            notes=row["notes"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )
