from __future__ import annotations

import json
from typing import Any, Dict, List, Optional

from app.models.domain import RAGQueryLog, RAGSession
from app.repositories.sqlite import SQLiteRepository


class RAGRepository:
    def __init__(self, sqlite_repo: SQLiteRepository) -> None:
        self.sqlite_repo = sqlite_repo

    def get_session(self, session_id: str) -> Optional[RAGSession]:
        with self.sqlite_repo.connect() as conn:
            row = conn.execute("SELECT * FROM rag_sessions WHERE session_id = ?", (session_id,)).fetchone()
        if not row:
            return None
        return RAGSession(
            session_id=row["session_id"],
            history=json.loads(row["history_json"]),
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )

    def upsert_session(self, session: RAGSession) -> RAGSession:
        with self.sqlite_repo.connect() as conn:
            conn.execute(
                """
                INSERT INTO rag_sessions (session_id, history_json, created_at, updated_at)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(session_id) DO UPDATE SET
                    history_json = excluded.history_json,
                    updated_at = excluded.updated_at
                """,
                (
                    session.session_id,
                    json.dumps(session.history, ensure_ascii=False),
                    session.created_at,
                    session.updated_at,
                ),
            )
        return session

    def create_query_log(self, query_log: RAGQueryLog) -> RAGQueryLog:
        with self.sqlite_repo.connect() as conn:
            conn.execute(
                """
                INSERT INTO rag_query_logs (
                    id, session_id, query, answer, retrieved_chunk_ids_json, citations_json,
                    status, latency_ms, created_at, debug_info_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    query_log.id,
                    query_log.session_id,
                    query_log.query,
                    query_log.answer,
                    json.dumps(query_log.retrieved_chunk_ids, ensure_ascii=False),
                    json.dumps(query_log.citations, ensure_ascii=False),
                    query_log.status,
                    query_log.latency_ms,
                    query_log.created_at,
                    json.dumps(query_log.debug_info, ensure_ascii=False),
                ),
            )
        return query_log
