from __future__ import annotations

import logging
from typing import Any, Dict, List

from app.services.classifier import DocumentClassifier
from app.services.wiki_service import WikiService
from app.utils.trace import log_event, new_trace_id
from app.utils.text import extract_keywords

LOG = logging.getLogger(__name__)


class WikiRecommendService:
    def __init__(self, wiki_service: WikiService, classifier: DocumentClassifier) -> None:
        self.wiki_service = wiki_service
        self.classifier = classifier

    def recommend(
        self,
        profile_text: str,
        focus_topics: List[str] | None = None,
        page_size: int = 5,
        max_queries: int = 5,
        cookie_override: str | None = None,
    ) -> Dict[str, Any]:
        focus_topics = [item.strip() for item in (focus_topics or []) if item.strip()]
        keywords = extract_keywords(profile_text, limit=16)
        classification = self.classifier.classify(f"{profile_text}\n{' '.join(focus_topics)}")
        query_candidates = self._build_queries(profile_text, keywords, focus_topics, max_queries)

        aggregated: Dict[str, Dict[str, Any]] = {}
        for query in query_candidates:
            payload = self.wiki_service.normalize_search_results(
                query,
                page=1,
                page_size=page_size,
                cookie_override=cookie_override,
            )
            for item in payload["items"]:
                result_key = item.get("sn") or item.get("id") or item.get("url")
                title = item.get("title") or ""
                summary = item.get("summary") or ""
                domain_title = item.get("domain_title") or ""
                kanban_title = item.get("kanban_title") or ""
                haystack = "\n".join([title, summary, domain_title, kanban_title]).lower()
                matched_terms = self._match_terms(haystack, keywords + focus_topics)
                score = self._score_item(item, matched_terms, query, classification.doc_type)
                reason = self._build_reason(matched_terms, item, classification.doc_type)
                skill_feasibility, skill_reason = self._skill_feasibility(item)
                candidate = {
                    **item,
                    "score": score,
                    "reason": reason,
                    "matched_terms": matched_terms,
                    "query_used": query,
                    "skill_feasibility": skill_feasibility,
                    "skill_reason": skill_reason,
                }
                existing = aggregated.get(result_key)
                if not existing or candidate["score"] > existing["score"]:
                    aggregated[result_key] = candidate

        ranked = sorted(aggregated.values(), key=lambda item: item["score"], reverse=True)
        return {
            "query_candidates": query_candidates,
            "detected_doc_type": classification.doc_type,
            "items": ranked[: max(page_size * 2, 8)],
        }

    def recommend_expanded(
        self,
        profile_text: str,
        focus_topics: List[str] | None = None,
        page_size: int = 10,
        max_queries: int = 8,
        pages_per_query: int = 2,
        min_score: float = 2.5,
        cookie_override: str | None = None,
        trace_id: str = "",
    ) -> Dict[str, Any]:
        trace_id = trace_id or new_trace_id()
        focus_topics = [item.strip() for item in (focus_topics or []) if item.strip()]
        keywords = extract_keywords(profile_text, limit=20)
        classification = self.classifier.classify(f"{profile_text}\n{' '.join(focus_topics)}")
        query_candidates = self._build_queries(profile_text, keywords, focus_topics, max_queries)

        aggregated: Dict[str, Dict[str, Any]] = {}
        total_candidates = 0
        log_event(
            LOG,
            trace_id=trace_id,
            step="wiki_recommend_expanded_start",
            status="started",
            query_count=len(query_candidates),
            detected_doc_type=classification.doc_type,
        )

        for query in query_candidates:
            for page in range(1, max(pages_per_query, 1) + 1):
                payload = self.wiki_service.normalize_search_results(
                    query,
                    page=page,
                    page_size=page_size,
                    cookie_override=cookie_override,
                )
                items = payload["items"]
                total_candidates += len(items)
                if not items:
                    continue
                for item in items:
                    result_key = item.get("sn") or item.get("id") or item.get("url")
                    title = item.get("title") or ""
                    summary = item.get("summary") or ""
                    domain_title = item.get("domain_title") or ""
                    kanban_title = item.get("kanban_title") or ""
                    haystack = "\n".join([title, summary, domain_title, kanban_title]).lower()
                    matched_terms = self._match_terms(haystack, keywords + focus_topics)
                    score = self._score_item(item, matched_terms, query, classification.doc_type)
                    reason = self._build_reason(matched_terms, item, classification.doc_type)
                    skill_feasibility, skill_reason = self._skill_feasibility(item)
                    candidate = {
                        **item,
                        "score": score,
                        "reason": reason,
                        "matched_terms": matched_terms,
                        "query_used": query,
                        "skill_feasibility": skill_feasibility,
                        "skill_reason": skill_reason,
                    }
                    existing = aggregated.get(result_key)
                    if not existing or candidate["score"] > existing["score"]:
                        aggregated[result_key] = candidate

        ranked = sorted(aggregated.values(), key=lambda item: item["score"], reverse=True)
        filtered = [item for item in ranked if item["score"] >= min_score]
        summary = {
            "total_candidates": total_candidates,
            "deduped_candidates": len(ranked),
            "high_relevance": len([item for item in ranked if item["score"] >= 7]),
            "medium_relevance": len([item for item in ranked if 4 <= item["score"] < 7]),
            "low_relevance": len([item for item in ranked if item["score"] < 4]),
        }
        log_event(
            LOG,
            trace_id=trace_id,
            step="wiki_recommend_expanded_finish",
            status="success",
            total_candidates=summary["total_candidates"],
            deduped_candidates=summary["deduped_candidates"],
            kept_candidates=len(filtered),
        )
        return {
            "query_candidates": query_candidates,
            "detected_doc_type": classification.doc_type,
            "summary": summary,
            "items": filtered,
        }

    @staticmethod
    def _build_queries(profile_text: str, keywords: List[str], focus_topics: List[str], max_queries: int) -> List[str]:
        profile_lines = [line.strip() for line in profile_text.splitlines() if line.strip()]
        candidates: List[str] = []
        candidates.extend(focus_topics)
        candidates.extend(keywords[: max_queries * 2])
        for line in profile_lines[:2]:
            if 2 <= len(line) <= 24:
                candidates.append(line)
        seen = set()
        queries: List[str] = []
        for item in candidates:
            normalized = item.strip()
            if len(normalized) < 2:
                continue
            lowered = normalized.lower()
            if lowered in seen:
                continue
            seen.add(lowered)
            queries.append(normalized)
            if len(queries) >= max_queries:
                break
        return queries

    @staticmethod
    def _match_terms(haystack: str, terms: List[str]) -> List[str]:
        matches: List[str] = []
        seen = set()
        for term in terms:
            normalized = term.strip()
            if len(normalized) < 2:
                continue
            lowered = normalized.lower()
            if lowered in haystack and lowered not in seen:
                seen.add(lowered)
                matches.append(normalized)
        return matches

    @staticmethod
    def _score_item(item: Dict[str, Any], matched_terms: List[str], query: str, detected_doc_type: str) -> float:
        title = (item.get("title") or "").lower()
        summary = (item.get("summary") or "").lower()
        domain_title = (item.get("domain_title") or "").lower()
        kanban_title = (item.get("kanban_title") or "").lower()

        score = len(matched_terms) * 2.0
        query_lower = query.lower()
        if query_lower in title:
            score += 4.0
        if query_lower in summary:
            score += 2.0
        if any(token in title for token in ["回滚", "排查", "接入", "skill", "告警", "权限", "配置"]):
            score += 1.5
        if detected_doc_type == "配置与治理知识库" and any(token in title + summary for token in ["回滚", "配置", "权限", "发布", "灰度"]):
            score += 1.5
        if detected_doc_type == "运维知识库" and any(token in title + summary for token in ["告警", "异常", "排查", "日志", "恢复"]):
            score += 1.5
        if detected_doc_type == "内部研发协作知识库" and any(token in title + summary for token in ["skill", "接入", "联调", "仓库", "工具链"]):
            score += 1.5
        if any(token in domain_title + kanban_title for token in ["平台", "研发", "运维", "治理"]):
            score += 0.5
        return round(score, 2)

    @staticmethod
    def _build_reason(matched_terms: List[str], item: Dict[str, Any], detected_doc_type: str) -> str:
        if matched_terms:
            return "命中关键词：%s；候选类型偏向 %s。" % ("、".join(matched_terms[:6]), detected_doc_type)
        return "标题或摘要与当前背景存在弱相关，建议人工复核。"

    @staticmethod
    def _skill_feasibility(item: Dict[str, Any]) -> tuple[str, str]:
        text = "\n".join(
            [
                item.get("title") or "",
                item.get("summary") or "",
                item.get("domain_title") or "",
                item.get("kanban_title") or "",
            ]
        )
        strong_signals = ["步骤", "接入", "排查", "回滚", "权限", "配置", "skill", "联调", "告警"]
        score = sum(1 for token in strong_signals if token.lower() in text.lower())
        if score >= 3:
            return "high", "标题或摘要具备明确步骤/排障/接入特征，适合后续生成 skill 草稿。"
        if score >= 1:
            return "medium", "存在操作型或排障型信息，可作为 skill 草稿候选，但仍需人工确认。"
        return "low", "更像一般说明或资料页，不建议直接生成 skill。"
