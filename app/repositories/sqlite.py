from __future__ import annotations

import sqlite3
from pathlib import Path


class SQLiteRepository:
    def __init__(self, db_path: Path) -> None:
        self.db_path = db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize()

    def connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.db_path)
        connection.row_factory = sqlite3.Row
        return connection

    def _initialize(self) -> None:
        with self.connect() as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS source_records (
                    source_id TEXT PRIMARY KEY,
                    source_type TEXT NOT NULL,
                    source_url TEXT NOT NULL,
                    source_title TEXT NOT NULL,
                    raw_content TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    owner TEXT NOT NULL,
                    tags_json TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    is_archived INTEGER NOT NULL,
                    extra_notes TEXT NOT NULL,
                    metadata_json TEXT NOT NULL,
                    import_status TEXT NOT NULL DEFAULT 'pending',
                    normalize_status TEXT NOT NULL DEFAULT 'pending',
                    last_error_message TEXT NOT NULL DEFAULT '',
                    last_synced_at TEXT NOT NULL DEFAULT '',
                    external_id TEXT NOT NULL DEFAULT ''
                );

                CREATE TABLE IF NOT EXISTS knowledge_documents (
                    doc_id TEXT PRIMARY KEY,
                    title TEXT NOT NULL,
                    doc_type TEXT NOT NULL,
                    knowledge_domain TEXT NOT NULL,
                    applicable_mode TEXT NOT NULL,
                    product_line_json TEXT NOT NULL,
                    roles_json TEXT NOT NULL,
                    owner TEXT NOT NULL,
                    keywords_json TEXT NOT NULL,
                    summary TEXT NOT NULL,
                    scenarios TEXT NOT NULL,
                    prerequisites TEXT NOT NULL,
                    core_content TEXT NOT NULL,
                    steps TEXT NOT NULL,
                    branch_logic TEXT NOT NULL,
                    risks TEXT NOT NULL,
                    best_practices TEXT NOT NULL,
                    related_docs TEXT NOT NULL,
                    faq TEXT NOT NULL,
                    appendix TEXT NOT NULL,
                    image_notes_json TEXT NOT NULL,
                    markdown_content TEXT NOT NULL,
                    source_id TEXT NOT NULL,
                    source_url TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    is_archived INTEGER NOT NULL,
                    normalize_mode TEXT NOT NULL,
                    ai_enhanced INTEGER NOT NULL,
                    source_title TEXT NOT NULL,
                    metadata_json TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS chunk_records (
                    id TEXT PRIMARY KEY,
                    doc_id TEXT NOT NULL,
                    source_id TEXT NOT NULL,
                    chunk_index INTEGER NOT NULL,
                    section_title TEXT NOT NULL,
                    content TEXT NOT NULL,
                    token_count INTEGER NOT NULL,
                    embedding_status TEXT NOT NULL,
                    is_active INTEGER NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    error_message TEXT NOT NULL DEFAULT '',
                    embedding_json TEXT NOT NULL DEFAULT '[]',
                    metadata_json TEXT NOT NULL DEFAULT '{}'
                );

                CREATE TABLE IF NOT EXISTS rag_sessions (
                    session_id TEXT PRIMARY KEY,
                    history_json TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS rag_query_logs (
                    id TEXT PRIMARY KEY,
                    session_id TEXT NOT NULL,
                    query TEXT NOT NULL,
                    answer TEXT NOT NULL,
                    retrieved_chunk_ids_json TEXT NOT NULL,
                    citations_json TEXT NOT NULL,
                    status TEXT NOT NULL,
                    latency_ms INTEGER NOT NULL,
                    created_at TEXT NOT NULL,
                    debug_info_json TEXT NOT NULL DEFAULT '{}'
                );

                CREATE TABLE IF NOT EXISTS candidate_expert_records (
                    candidate_id TEXT PRIMARY KEY,
                    topic_query TEXT NOT NULL,
                    created_by_name TEXT NOT NULL,
                    created_by_account TEXT NOT NULL,
                    article_count INTEGER NOT NULL DEFAULT 0,
                    latest_updated_at TEXT NOT NULL DEFAULT '',
                    possible_skills_json TEXT NOT NULL DEFAULT '[]',
                    evidence_json TEXT NOT NULL DEFAULT '[]',
                    recommendation TEXT NOT NULL DEFAULT '',
                    related_articles_json TEXT NOT NULL DEFAULT '[]',
                    status TEXT NOT NULL DEFAULT '待确认',
                    notes TEXT NOT NULL DEFAULT '',
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
                """
            )
            self._ensure_columns(
                conn,
                "source_records",
                {
                    "import_status": "TEXT NOT NULL DEFAULT 'pending'",
                    "normalize_status": "TEXT NOT NULL DEFAULT 'pending'",
                    "last_error_message": "TEXT NOT NULL DEFAULT ''",
                    "last_synced_at": "TEXT NOT NULL DEFAULT ''",
                    "external_id": "TEXT NOT NULL DEFAULT ''",
                },
            )
            self._ensure_columns(
                conn,
                "chunk_records",
                {
                    "error_message": "TEXT NOT NULL DEFAULT ''",
                    "embedding_json": "TEXT NOT NULL DEFAULT '[]'",
                    "metadata_json": "TEXT NOT NULL DEFAULT '{}'",
                },
            )
            self._ensure_columns(
                conn,
                "candidate_expert_records",
                {
                    "status": "TEXT NOT NULL DEFAULT '待确认'",
                    "notes": "TEXT NOT NULL DEFAULT ''",
                    "related_articles_json": "TEXT NOT NULL DEFAULT '[]'",
                },
            )

    def _ensure_columns(self, conn: sqlite3.Connection, table_name: str, columns: dict) -> None:
        existing = {
            row["name"]
            for row in conn.execute("PRAGMA table_info(%s)" % table_name).fetchall()
        }
        for column_name, ddl in columns.items():
            if column_name not in existing:
                conn.execute("ALTER TABLE %s ADD COLUMN %s %s" % (table_name, column_name, ddl))
