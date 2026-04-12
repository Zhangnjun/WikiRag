from __future__ import annotations

import time
import uuid
from typing import Any, Dict, List, Optional

from app.clients.internal_ai import InternalAIClient
from app.config import RAGSettings
from app.models.domain import RAGQueryLog, RAGSession
from app.repositories.rag_repository import RAGRepository
from app.services.retrieval_service import RetrievalService
from app.utils.time import now_iso
from app.utils.trace import log_event, new_trace_id

import logging

LOG = logging.getLogger(__name__)


class RAGService:
    def __init__(
        self,
        retrieval_service: RetrievalService,
        rag_repository: RAGRepository,
        chat_client: InternalAIClient,
        rag_settings: RAGSettings,
    ) -> None:
        self.retrieval_service = retrieval_service
        self.rag_repository = rag_repository
        self.chat_client = chat_client
        self.rag_settings = rag_settings

    def query(
        self,
        query: str,
        top_k: int,
        use_rerank: bool,
        use_ai: bool,
        filters: Dict[str, Any],
        debug: bool,
        session_id: Optional[str],
        trace_id: str = "",
    ) -> Dict[str, Any]:
        trace_id = trace_id or new_trace_id()
        started = time.time()
        session = self._load_session(session_id)
        rewritten_query = self._build_contextual_query(query, session)
        hits, debug_info = self.retrieval_service.hybrid_retrieve(rewritten_query, top_k=top_k, filters=filters)
        if use_rerank:
            hits = self._rerank_hits(rewritten_query, hits)[:top_k]
            debug_info["final_hits"] = hits

        answer, citations = self._build_answer(query, hits, use_ai)
        duration_ms = int((time.time() - started) * 1000)
        session.history.append({"query": query, "answer": answer, "created_at": now_iso()})
        session.history = session.history[-self.rag_settings.session_max_turns :]
        session.updated_at = now_iso()
        self.rag_repository.upsert_session(session)
        self.rag_repository.create_query_log(
            RAGQueryLog(
                id=str(uuid.uuid4()),
                session_id=session.session_id,
                query=query,
                answer=answer,
                retrieved_chunk_ids=[item["chunk_id"] for item in hits],
                citations=citations,
                status="success" if hits else "empty",
                latency_ms=duration_ms,
                created_at=now_iso(),
                debug_info=debug_info if debug else {},
            )
        )
        log_event(
            LOG,
            trace_id=trace_id,
            step="rag_query",
            status="success" if hits else "empty",
            doc_id=hits[0]["doc_id"] if hits else "",
            source_id=hits[0]["source_id"] if hits else "",
            error="",
            session_id=session.session_id,
        )

        retrieved_chunks = []
        for hit in hits:
            retrieved_chunks.append(
                {
                    "chunk_id": hit["chunk_id"],
                    "doc_id": hit["doc_id"],
                    "source_id": hit["source_id"],
                    "doc_title": hit["doc_title"],
                    "doc_type": hit["doc_type"],
                    "source_type": hit["source_type"],
                    "section_title": hit["section_title"],
                    "content": hit["content"],
                    "score": round(hit.get("hybrid_score", hit.get("vector_score", hit.get("keyword_score", 0.0))), 6),
                    "score_detail": {
                        "keyword_score": hit.get("keyword_score", 0.0),
                        "vector_score": hit.get("vector_score", 0.0),
                        "hybrid_score": hit.get("hybrid_score", 0.0),
                    },
                }
            )
        response = {
            "session_id": session.session_id,
            "status": "success" if hits else "empty",
            "latency_ms": duration_ms,
            "answer": answer,
            "citations": citations,
            "retrieved_chunks": retrieved_chunks,
            "debug_info": None,
        }
        if debug:
            response["debug_info"] = {
                "query_rewrite": rewritten_query,
                "keyword_hits": debug_info.get("keyword_hits", []),
                "vector_hits": debug_info.get("vector_hits", []),
                "final_hits": debug_info.get("final_hits", []),
            }
        return response

    def _load_session(self, session_id: Optional[str]) -> RAGSession:
        if session_id:
            existing = self.rag_repository.get_session(session_id)
            if existing:
                return existing
        now = now_iso()
        return RAGSession(session_id=session_id or str(uuid.uuid4()), history=[], created_at=now, updated_at=now)

    def _build_contextual_query(self, query: str, session: RAGSession) -> str:
        if not session.history:
            return query
        recent_queries = [item["query"] for item in session.history[-2:]]
        return " \n ".join(recent_queries + [query])

    def _rerank_hits(self, query: str, hits: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        query_terms = set(query.lower().split())
        for hit in hits:
            title_bonus = 0.15 if any(term in hit["doc_title"].lower() for term in query_terms if term) else 0.0
            section_bonus = 0.05 if any(term in hit["section_title"].lower() for term in query_terms if term) else 0.0
            hit["hybrid_score"] = hit.get("hybrid_score", 0.0) + title_bonus + section_bonus
        return sorted(hits, key=lambda item: item.get("hybrid_score", 0.0), reverse=True)

    def _build_answer(self, query: str, hits: List[Dict[str, Any]], use_ai: bool) -> tuple:
        if not hits:
            return (
                "未检索到足够相关的知识内容。建议换更具体的关键词，或先补充相关知识文档后再查询。",
                [],
            )
        citations = [
            {
                "chunk_id": hit["chunk_id"],
                "doc_id": hit["doc_id"],
                "source_id": hit["source_id"],
                "doc_title": hit["doc_title"],
                "section_title": hit["section_title"],
                "source_url": hit["source_url"],
                "chunk_summary": hit["content"][:180],
            }
            for hit in hits[: min(3, len(hits))]
        ]
        if use_ai and self.chat_client.is_enabled():
            prompt = self._build_grounded_prompt(query, hits)
            try:
                result = self.chat_client.normalize_document(prompt)
                if isinstance(result, dict):
                    explicit = result.get("explicit_answer") or ""
                    inferred = result.get("inference") or ""
                    answer = "知识明确给出：%s\n\n模型推断：%s" % (
                        explicit or "待补充",
                        inferred or "无额外推断",
                    )
                    return answer, citations
            except Exception:
                pass
        explicit_lines = []
        for hit in hits[: min(3, len(hits))]:
            explicit_lines.append("[%s] %s" % (hit["section_title"], hit["content"][:220]))
        inferred = "基于命中的文档片段，优先参考前两条引用来源，不建议脱离引用内容做更强结论。"
        answer = "知识明确给出：\n%s\n\n模型推断：\n%s" % ("\n".join(explicit_lines), inferred)
        return answer, citations

    def _build_grounded_prompt(self, query: str, hits: List[Dict[str, Any]]) -> str:
        context = []
        for hit in hits[: self.rag_settings.max_context_chunks]:
            context.append(
                "文档: {doc_title}\n章节: {section_title}\n内容: {content}".format(
                    doc_title=hit["doc_title"],
                    section_title=hit["section_title"],
                    content=hit["content"][:800],
                )
            )
        return (
            "请严格根据给定知识片段回答，不可编造。输出 JSON，字段包含 explicit_answer 和 inference。"
            "如果知识没有明确覆盖，explicit_answer 请说明未明确给出。\n"
            "问题：%s\n\n知识片段：\n%s" % (query, "\n\n".join(context))
        )
