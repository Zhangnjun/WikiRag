from __future__ import annotations

import json
from typing import Any, Dict, List, Optional

from app.models.domain import ChunkRecord
from app.repositories.sqlite import SQLiteRepository


class ChunkRepository:
    def __init__(self, sqlite_repo: SQLiteRepository) -> None:
        self.sqlite_repo = sqlite_repo

    def create_many(self, chunks: List[ChunkRecord]) -> List[ChunkRecord]:
        if not chunks:
            return []
        with self.sqlite_repo.connect() as conn:
            conn.executemany(
                """
                INSERT INTO chunk_records (
                    id, doc_id, source_id, chunk_index, section_title, content, token_count,
                    embedding_status, is_active, created_at, updated_at, error_message,
                    embedding_json, metadata_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    (
                        chunk.id,
                        chunk.doc_id,
                        chunk.source_id,
                        chunk.chunk_index,
                        chunk.section_title,
                        chunk.content,
                        chunk.token_count,
                        chunk.embedding_status,
                        int(chunk.is_active),
                        chunk.created_at,
                        chunk.updated_at,
                        chunk.error_message,
                        json.dumps(chunk.embedding_json),
                        json.dumps(chunk.metadata, ensure_ascii=False),
                    )
                    for chunk in chunks
                ],
            )
        return chunks

    def deactivate_by_doc_id(self, doc_id: str) -> None:
        with self.sqlite_repo.connect() as conn:
            conn.execute(
                "UPDATE chunk_records SET is_active = 0, updated_at = CURRENT_TIMESTAMP WHERE doc_id = ?",
                (doc_id,),
            )

    def list_by_doc_id(self, doc_id: str, active_only: bool = True) -> List[ChunkRecord]:
        query = "SELECT * FROM chunk_records WHERE doc_id = ?"
        values: List[Any] = [doc_id]
        if active_only:
            query += " AND is_active = 1"
        query += " ORDER BY chunk_index ASC"
        with self.sqlite_repo.connect() as conn:
            rows = conn.execute(query, values).fetchall()
        return [self._to_model(row) for row in rows]

    def update_embedding(self, chunk_id: str, embedding: List[float], status: str, error_message: str = "") -> None:
        with self.sqlite_repo.connect() as conn:
            conn.execute(
                """
                UPDATE chunk_records
                SET embedding_json = ?, embedding_status = ?, error_message = ?, updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
                """,
                (json.dumps(embedding), status, error_message, chunk_id),
            )

    def mark_embedding_status(self, chunk_id: str, status: str, error_message: str = "") -> None:
        with self.sqlite_repo.connect() as conn:
            conn.execute(
                "UPDATE chunk_records SET embedding_status = ?, error_message = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                (status, error_message, chunk_id),
            )

    def list_for_embedding(self, doc_id: Optional[str] = None, retry_failed: bool = False) -> List[ChunkRecord]:
        clauses = ["is_active = 1"]
        values: List[Any] = []
        if doc_id:
            clauses.append("doc_id = ?")
            values.append(doc_id)
        if retry_failed:
            clauses.append("(embedding_status = 'pending' OR embedding_status = 'failed')")
        else:
            clauses.append("embedding_status = 'pending'")
        with self.sqlite_repo.connect() as conn:
            rows = conn.execute(
                "SELECT * FROM chunk_records WHERE %s ORDER BY updated_at ASC, chunk_index ASC" % " AND ".join(clauses),
                values,
            ).fetchall()
        return [self._to_model(row) for row in rows]

    def fetch_active_chunks(self, filters: Dict[str, Any], require_embedding: bool = True) -> List[Dict[str, Any]]:
        clauses = ["c.is_active = 1"]
        if require_embedding:
            clauses.append("c.embedding_status = 'success'")
        values: List[Any] = []
        if filters.get("doc_type"):
            clauses.append("k.doc_type = ?")
            values.append(filters["doc_type"])
        if filters.get("source_type"):
            clauses.append("s.source_type = ?")
            values.append(filters["source_type"])
        if filters.get("product_line"):
            clauses.append("k.product_line_json LIKE ?")
            values.append("%%%s%%" % filters["product_line"])
        if filters.get("source_id"):
            clauses.append("c.source_id = ?")
            values.append(filters["source_id"])
        with self.sqlite_repo.connect() as conn:
            rows = conn.execute(
                """
                SELECT
                    c.*,
                    k.title AS doc_title,
                    k.doc_type AS doc_type,
                    k.product_line_json AS product_line_json,
                    k.source_url AS source_url,
                    s.source_type AS source_type
                FROM chunk_records c
                JOIN knowledge_documents k ON k.doc_id = c.doc_id
                JOIN source_records s ON s.source_id = c.source_id
                WHERE %s
                """ % " AND ".join(clauses),
                values,
            ).fetchall()
        return [dict(row) for row in rows]

    def _to_model(self, row) -> ChunkRecord:
        return ChunkRecord(
            id=row["id"],
            doc_id=row["doc_id"],
            source_id=row["source_id"],
            chunk_index=row["chunk_index"],
            section_title=row["section_title"],
            content=row["content"],
            token_count=row["token_count"],
            embedding_status=row["embedding_status"],
            is_active=bool(row["is_active"]),
            created_at=row["created_at"],
            updated_at=row["updated_at"],
            error_message=row["error_message"],
            embedding_json=json.loads(row["embedding_json"] or "[]"),
            metadata=json.loads(row["metadata_json"] or "{}"),
        )
