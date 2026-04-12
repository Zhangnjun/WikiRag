from __future__ import annotations

import json
from typing import Any, Dict, List, Optional

from app.models.domain import SourceRecord
from app.repositories.sqlite import SQLiteRepository


class SourceRepository:
    def __init__(self, sqlite_repo: SQLiteRepository) -> None:
        self.sqlite_repo = sqlite_repo

    def create(self, record: SourceRecord) -> SourceRecord:
        with self.sqlite_repo.connect() as conn:
            conn.execute(
                """
                INSERT INTO source_records (
                    source_id, source_type, source_url, source_title, raw_content, updated_at,
                    owner, tags_json, created_at, is_archived, extra_notes, metadata_json,
                    import_status, normalize_status, last_error_message, last_synced_at, external_id
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    record.source_id,
                    record.source_type,
                    record.source_url,
                    record.source_title,
                    record.raw_content,
                    record.updated_at,
                    record.owner,
                    json.dumps(record.tags, ensure_ascii=False),
                    record.created_at,
                    int(record.is_archived),
                    record.extra_notes,
                    json.dumps(record.metadata, ensure_ascii=False),
                    record.import_status,
                    record.normalize_status,
                    record.last_error_message,
                    record.last_synced_at,
                    record.external_id,
                ),
            )
        return record

    def get(self, source_id: str) -> Optional[SourceRecord]:
        with self.sqlite_repo.connect() as conn:
            row = conn.execute("SELECT * FROM source_records WHERE source_id = ?", (source_id,)).fetchone()
            model = self._to_model(row) if row else None
            if model:
                model.linked_doc_types = self._fetch_doc_types(conn, source_id)
        return model

    def list_all(self) -> List[SourceRecord]:
        with self.sqlite_repo.connect() as conn:
            rows = conn.execute("SELECT * FROM source_records ORDER BY created_at DESC").fetchall()
            items = [self._to_model(row) for row in rows]
            for item in items:
                item.linked_doc_types = self._fetch_doc_types(conn, item.source_id)
        return items

    def list_filtered(self, filters: Dict[str, Any], page: int, page_size: int) -> tuple:
        clauses = ["1=1"]
        values: List[Any] = []
        if filters.get("title"):
            clauses.append("source_title LIKE ?")
            values.append("%%%s%%" % filters["title"])
        if filters.get("source_type"):
            clauses.append("source_type = ?")
            values.append(filters["source_type"])
        if filters.get("owner"):
            clauses.append("(owner LIKE ? OR metadata_json LIKE ?)")
            values.append("%%%s%%" % filters["owner"])
            values.append("%%%s%%" % filters["owner"])
        if filters.get("tags"):
            clauses.append("tags_json LIKE ?")
            values.append("%%%s%%" % filters["tags"])
        if filters.get("import_status"):
            clauses.append("import_status = ?")
            values.append(filters["import_status"])
        if filters.get("normalize_status"):
            clauses.append("normalize_status = ?")
            values.append(filters["normalize_status"])
        if filters.get("doc_type"):
            clauses.append(
                "EXISTS (SELECT 1 FROM knowledge_documents kd WHERE kd.source_id = source_records.source_id AND kd.doc_type = ?)"
            )
            values.append(filters["doc_type"])
        offset = max(page - 1, 0) * page_size
        with self.sqlite_repo.connect() as conn:
            total = conn.execute(
                "SELECT COUNT(*) AS total FROM source_records WHERE %s" % " AND ".join(clauses),
                values,
            ).fetchone()["total"]
            rows = conn.execute(
                "SELECT * FROM source_records WHERE %s ORDER BY updated_at DESC LIMIT ? OFFSET ?"
                % " AND ".join(clauses),
                values + [page_size, offset],
            ).fetchall()
            items = [self._to_model(row) for row in rows]
            for item in items:
                item.linked_doc_types = self._fetch_doc_types(conn, item.source_id)
        return items, total

    def update(self, source_id: str, fields: Dict[str, Any]) -> Optional[SourceRecord]:
        if not fields:
            return self.get(source_id)
        assignments = []
        values = []
        json_fields = {"tags", "metadata"}
        key_map = {"tags": "tags_json", "metadata": "metadata_json"}
        for key, value in fields.items():
            column = key_map.get(key, key)
            assignments.append("%s = ?" % column)
            if key in json_fields:
                values.append(json.dumps(value, ensure_ascii=False))
            elif key == "is_archived":
                values.append(int(bool(value)))
            else:
                values.append(value)
        values.append(source_id)
        with self.sqlite_repo.connect() as conn:
            conn.execute(
                "UPDATE source_records SET %s WHERE source_id = ?" % ", ".join(assignments),
                values,
            )
        return self.get(source_id)

    def find_by_url_or_external_id(self, source_url: str, external_id: str) -> Optional[SourceRecord]:
        clauses = []
        values: List[Any] = []
        if source_url:
            clauses.append("source_url = ?")
            values.append(source_url)
        if external_id:
            clauses.append("external_id = ?")
            values.append(external_id)
        if not clauses:
            return None
        with self.sqlite_repo.connect() as conn:
            row = conn.execute(
                "SELECT * FROM source_records WHERE %s ORDER BY created_at DESC LIMIT 1"
                % " OR ".join(clauses),
                values,
            ).fetchone()
            model = self._to_model(row) if row else None
            if model:
                model.linked_doc_types = self._fetch_doc_types(conn, model.source_id)
        return model

    def count_knowledge_by_source(self, source_id: str) -> int:
        with self.sqlite_repo.connect() as conn:
            row = conn.execute(
                "SELECT COUNT(*) AS total FROM knowledge_documents WHERE source_id = ?",
                (source_id,),
            ).fetchone()
        return row["total"]

    def _fetch_doc_types(self, conn, source_id: str) -> List[str]:
        rows = conn.execute(
            "SELECT DISTINCT doc_type FROM knowledge_documents WHERE source_id = ? ORDER BY doc_type",
            (source_id,),
        ).fetchall()
        return [row["doc_type"] for row in rows]

    def _to_model(self, row) -> SourceRecord:
        return SourceRecord(
            source_id=row["source_id"],
            source_type=row["source_type"],
            source_url=row["source_url"],
            source_title=row["source_title"],
            raw_content=row["raw_content"],
            updated_at=row["updated_at"],
            owner=row["owner"],
            tags=json.loads(row["tags_json"]),
            created_at=row["created_at"],
            is_archived=bool(row["is_archived"]),
            extra_notes=row["extra_notes"],
            metadata=json.loads(row["metadata_json"]),
            import_status=row["import_status"],
            normalize_status=row["normalize_status"],
            last_error_message=row["last_error_message"],
            last_synced_at=row["last_synced_at"],
            external_id=row["external_id"],
        )
