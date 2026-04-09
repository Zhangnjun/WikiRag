from __future__ import annotations

import json
from typing import Any

from app.models.domain import KnowledgeDocument
from app.repositories.sqlite import SQLiteRepository


class KnowledgeRepository:
    def __init__(self, sqlite_repo: SQLiteRepository) -> None:
        self.sqlite_repo = sqlite_repo

    def create(self, document: KnowledgeDocument) -> KnowledgeDocument:
        with self.sqlite_repo.connect() as conn:
            conn.execute(
                """
                INSERT INTO knowledge_documents (
                    doc_id, title, doc_type, knowledge_domain, applicable_mode, product_line_json,
                    roles_json, owner, keywords_json, summary, scenarios, prerequisites, core_content,
                    steps, branch_logic, risks, best_practices, related_docs, faq, appendix,
                    image_notes_json, markdown_content, source_id, source_url, created_at,
                    updated_at, is_archived, normalize_mode, ai_enhanced, source_title, metadata_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    document.doc_id,
                    document.title,
                    document.doc_type,
                    document.knowledge_domain,
                    document.applicable_mode,
                    json.dumps(document.product_line, ensure_ascii=False),
                    json.dumps(document.roles, ensure_ascii=False),
                    document.owner,
                    json.dumps(document.keywords, ensure_ascii=False),
                    document.summary,
                    document.scenarios,
                    document.prerequisites,
                    document.core_content,
                    document.steps,
                    document.branch_logic,
                    document.risks,
                    document.best_practices,
                    document.related_docs,
                    document.faq,
                    document.appendix,
                    json.dumps(document.image_notes, ensure_ascii=False),
                    document.markdown_content,
                    document.source_id,
                    document.source_url,
                    document.created_at,
                    document.updated_at,
                    int(document.is_archived),
                    document.normalize_mode,
                    int(document.ai_enhanced),
                    document.source_title,
                    json.dumps(document.metadata, ensure_ascii=False),
                ),
            )
        return document

    def get(self, doc_id: str) -> KnowledgeDocument | None:
        with self.sqlite_repo.connect() as conn:
            row = conn.execute("SELECT * FROM knowledge_documents WHERE doc_id = ?", (doc_id,)).fetchone()
        return self._to_model(row) if row else None

    def get_by_source_id(self, source_id: str) -> list:
        with self.sqlite_repo.connect() as conn:
            rows = conn.execute(
                "SELECT * FROM knowledge_documents WHERE source_id = ? ORDER BY updated_at DESC",
                (source_id,),
            ).fetchall()
        return [self._to_model(row) for row in rows]

    def update(self, doc_id: str, fields: dict[str, Any]) -> KnowledgeDocument | None:
        if not fields:
            return self.get(doc_id)

        assignments = []
        values = []
        json_fields = {"product_line", "roles", "keywords", "image_notes", "metadata"}
        bool_fields = {"is_archived", "ai_enhanced"}
        key_map = {
            "product_line": "product_line_json",
            "roles": "roles_json",
            "keywords": "keywords_json",
            "image_notes": "image_notes_json",
            "metadata": "metadata_json",
        }
        for key, value in fields.items():
            column = key_map.get(key, key)
            assignments.append(f"{column} = ?")
            if key in json_fields:
                values.append(json.dumps(value, ensure_ascii=False))
            elif key in bool_fields:
                values.append(int(bool(value)))
            else:
                values.append(value)
        values.append(doc_id)

        with self.sqlite_repo.connect() as conn:
            conn.execute(f"UPDATE knowledge_documents SET {', '.join(assignments)} WHERE doc_id = ?", values)
        return self.get(doc_id)

    def list_filtered(self, filters: dict[str, Any]) -> list[KnowledgeDocument]:
        clauses = ["1=1"]
        values: list[Any] = []
        if filters.get("doc_type"):
            clauses.append("doc_type = ?")
            values.append(filters["doc_type"])
        if filters.get("knowledge_domain"):
            clauses.append("knowledge_domain LIKE ?")
            values.append(f"%{filters['knowledge_domain']}%")
        if filters.get("product_line"):
            clauses.append("product_line_json LIKE ?")
            values.append(f"%{filters['product_line']}%")
        if filters.get("role"):
            clauses.append("roles_json LIKE ?")
            values.append(f"%{filters['role']}%")
        if filters.get("keyword"):
            clauses.append("keywords_json LIKE ?")
            values.append(f"%{filters['keyword']}%")
        if filters.get("is_archived") is not None:
            clauses.append("is_archived = ?")
            values.append(int(bool(filters["is_archived"])))

        with self.sqlite_repo.connect() as conn:
            rows = conn.execute(
                f"SELECT * FROM knowledge_documents WHERE {' AND '.join(clauses)} ORDER BY updated_at DESC",
                values,
            ).fetchall()
        return [self._to_model(row) for row in rows]

    def search(self, query: str, filters: dict[str, Any]) -> list[KnowledgeDocument]:
        clauses = ["(title LIKE ? OR markdown_content LIKE ? OR keywords_json LIKE ?)"]
        values: list[Any] = [f"%{query}%", f"%{query}%", f"%{query}%"]
        if filters.get("doc_type"):
            clauses.append("doc_type = ?")
            values.append(filters["doc_type"])
        if filters.get("product_line"):
            clauses.append("product_line_json LIKE ?")
            values.append(f"%{filters['product_line']}%")
        if filters.get("role"):
            clauses.append("roles_json LIKE ?")
            values.append(f"%{filters['role']}%")
        if filters.get("keyword"):
            clauses.append("keywords_json LIKE ?")
            values.append(f"%{filters['keyword']}%")
        with self.sqlite_repo.connect() as conn:
            rows = conn.execute(
                f"SELECT * FROM knowledge_documents WHERE {' AND '.join(clauses)} ORDER BY updated_at DESC",
                values,
            ).fetchall()
        return [self._to_model(row) for row in rows]

    def _to_model(self, row) -> KnowledgeDocument:
        return KnowledgeDocument(
            doc_id=row["doc_id"],
            title=row["title"],
            doc_type=row["doc_type"],
            knowledge_domain=row["knowledge_domain"],
            applicable_mode=row["applicable_mode"],
            product_line=json.loads(row["product_line_json"]),
            roles=json.loads(row["roles_json"]),
            owner=row["owner"],
            keywords=json.loads(row["keywords_json"]),
            summary=row["summary"],
            scenarios=row["scenarios"],
            prerequisites=row["prerequisites"],
            core_content=row["core_content"],
            steps=row["steps"],
            branch_logic=row["branch_logic"],
            risks=row["risks"],
            best_practices=row["best_practices"],
            related_docs=row["related_docs"],
            faq=row["faq"],
            appendix=row["appendix"],
            image_notes=json.loads(row["image_notes_json"]),
            markdown_content=row["markdown_content"],
            source_id=row["source_id"],
            source_url=row["source_url"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
            is_archived=bool(row["is_archived"]),
            normalize_mode=row["normalize_mode"],
            ai_enhanced=bool(row["ai_enhanced"]),
            source_title=row["source_title"],
            metadata=json.loads(row["metadata_json"]),
        )
