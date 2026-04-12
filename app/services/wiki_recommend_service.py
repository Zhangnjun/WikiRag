from __future__ import annotations

import logging
from typing import Any, Dict, List

from app.services.classifier import DocumentClassifier
from app.services.wiki_service import WikiService
from app.utils.text import extract_keywords
from app.utils.trace import log_event, new_trace_id

LOG = logging.getLogger(__name__)

JOB_SEARCH_EXPANSIONS: Dict[str, List[str]] = {
    "微调": ["SFT", "LoRA", "QLoRA", "指令微调", "训练集", "样本构造", "数据清洗", "checkpoint", "评测", "Qwen", "GLM"],
    "模型微调": ["SFT", "LoRA", "QLoRA", "指令微调", "训练集", "样本构造", "数据清洗", "checkpoint", "评测", "Qwen", "GLM"],
    "rag": ["知识库", "检索增强", "embedding", "rerank", "chunk", "向量检索", "文档切分", "引用来源", "问答系统"],
    "agent": ["智能助手", "多轮对话", "工具调用", "插件调用", "function calling", "skill", "工作流", "编排", "自动化处理", "Copilot"],
    "智能助手": ["Agent", "多轮对话", "工具调用", "skill", "工作流", "自动化处理"],
    "推理": ["推理服务", "模型部署", "服务发布", "在线推理", "模型接入", "GPU", "NPU", "MindIE", "灰度发布", "扩缩容", "资源配置"],
    "推理服务": ["模型部署", "在线推理", "模型接入", "GPU", "NPU", "MindIE", "灰度发布", "扩缩容", "资源配置"],
    "部署": ["模型部署", "服务发布", "在线推理", "灰度发布", "扩缩容", "资源配置"],
}


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
        trace_id: str = "",
    ) -> Dict[str, Any]:
        trace_id = trace_id or new_trace_id()
        focus_topics = [self._normalize_text(item).strip() for item in (focus_topics or []) if self._normalize_text(item).strip()]
        keywords = extract_keywords(profile_text, limit=16)
        classification = self.classifier.classify(f"{profile_text}\n{' '.join(focus_topics)}")
        query_candidates = self._build_queries(profile_text, keywords, focus_topics, max_queries)

        aggregated: Dict[str, Dict[str, Any]] = {}
        log_event(
            LOG,
            trace_id=trace_id,
            step="wiki_recommend_start",
            status="started",
            detected_doc_type=classification.doc_type,
            query_candidates=query_candidates,
        )

        for query in query_candidates:
            payload = self.wiki_service.normalize_search_results(
                query,
                page=1,
                page_size=page_size,
                cookie_override=cookie_override,
                trace_id=trace_id,
            )
            for item in payload["items"]:
                candidate = self._build_candidate(
                    item=item,
                    keywords=keywords,
                    focus_topics=focus_topics,
                    query=query,
                    detected_doc_type=classification.doc_type,
                )
                result_key = candidate["sn"] or candidate["id"] or candidate["url"] or candidate["title"]
                existing = aggregated.get(result_key)
                if not existing or candidate["score"] > existing["score"]:
                    aggregated[result_key] = candidate

        ranked = sorted(aggregated.values(), key=lambda item: item["score"], reverse=True)
        log_event(
            LOG,
            trace_id=trace_id,
            step="wiki_recommend_finish",
            status="success",
            item_count=len(ranked),
            detected_doc_type=classification.doc_type,
        )
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
        focus_topics = [self._normalize_text(item).strip() for item in (focus_topics or []) if self._normalize_text(item).strip()]
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
                    trace_id=trace_id,
                )
                items = payload["items"]
                total_candidates += len(items)
                for item in items:
                    candidate = self._build_candidate(
                        item=item,
                        keywords=keywords,
                        focus_topics=focus_topics,
                        query=query,
                        detected_doc_type=classification.doc_type,
                    )
                    result_key = candidate["sn"] or candidate["id"] or candidate["url"] or candidate["title"]
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

    @classmethod
    def _build_queries(cls, profile_text: str, keywords: List[str], focus_topics: List[str], max_queries: int) -> List[str]:
        profile_lines = [line.strip() for line in profile_text.splitlines() if line.strip()]
        candidates: List[str] = []
        expanded_terms = cls._expand_job_search_terms(profile_text, focus_topics)
        candidates.extend(focus_topics)
        candidates.extend(expanded_terms)
        candidates.extend(keywords[: max_queries * 2])
        for line in profile_lines[:2]:
            if 2 <= len(line) <= 24:
                candidates.append(line)
        seen = set()
        queries: List[str] = []
        for item in candidates:
            normalized = cls._normalize_text(item).strip()
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

    @classmethod
    def _expand_job_search_terms(cls, profile_text: str, focus_topics: List[str]) -> List[str]:
        haystack = f"{profile_text}\n{' '.join(focus_topics)}".lower()
        expanded: List[str] = []
        for key, values in JOB_SEARCH_EXPANSIONS.items():
            if key.lower() in haystack:
                expanded.extend(values)
        return expanded

    @staticmethod
    def _normalize_text(value: Any) -> str:
        if value is None:
            return ""
        if isinstance(value, str):
            return value
        if isinstance(value, list):
            parts = [WikiRecommendService._normalize_text(item).strip() for item in value]
            return "\n".join(part for part in parts if part)
        if isinstance(value, dict):
            parts = [WikiRecommendService._normalize_text(item).strip() for item in value.values()]
            return " ".join(part for part in parts if part)
        return str(value)

    @classmethod
    def _normalize_candidate_fields(cls, item: Dict[str, Any]) -> Dict[str, Any]:
        normalized = dict(item)
        normalized["id"] = cls._normalize_text(item.get("id"))
        normalized["sn"] = cls._normalize_text(item.get("sn"))
        normalized["title"] = cls._normalize_text(item.get("title"))
        normalized["summary"] = cls._normalize_text(item.get("summary"))
        normalized["domain_title"] = cls._normalize_text(item.get("domain_title"))
        normalized["kanban_title"] = cls._normalize_text(item.get("kanban_title"))
        normalized["updated_at"] = cls._normalize_text(item.get("updated_at"))
        normalized["created_at"] = cls._normalize_text(item.get("created_at"))
        normalized["url"] = cls._normalize_text(item.get("url"))
        return normalized

    @classmethod
    def _build_candidate(
        cls,
        *,
        item: Dict[str, Any],
        keywords: List[str],
        focus_topics: List[str],
        query: str,
        detected_doc_type: str,
    ) -> Dict[str, Any]:
        normalized_item = cls._normalize_candidate_fields(item)
        haystack = "\n".join(
            [
                normalized_item["title"],
                normalized_item["summary"],
                normalized_item["domain_title"],
                normalized_item["kanban_title"],
            ]
        ).lower()
        matched_terms = cls._match_terms(haystack, keywords + focus_topics)
        score = cls._score_item(normalized_item, matched_terms, query, detected_doc_type)
        reason = cls._build_reason(matched_terms, normalized_item, detected_doc_type)
        skill_feasibility, skill_reason = cls._skill_feasibility(normalized_item)
        project_fit, project_evidence = cls._project_fit(normalized_item, matched_terms)
        return {
            **normalized_item,
            "score": score,
            "reason": reason,
            "matched_terms": matched_terms,
            "query_used": query,
            "skill_feasibility": skill_feasibility,
            "skill_reason": skill_reason,
            "project_fit": project_fit,
            "project_evidence": project_evidence,
        }

    @staticmethod
    def _match_terms(haystack: str, terms: List[str]) -> List[str]:
        matches: List[str] = []
        seen = set()
        for term in terms:
            normalized = WikiRecommendService._normalize_text(term).strip()
            if len(normalized) < 2:
                continue
            lowered = normalized.lower()
            if lowered in haystack and lowered not in seen:
                seen.add(lowered)
                matches.append(normalized)
        return matches

    @classmethod
    def _score_item(cls, item: Dict[str, Any], matched_terms: List[str], query: str, detected_doc_type: str) -> float:
        title = cls._normalize_text(item.get("title")).lower()
        summary = cls._normalize_text(item.get("summary")).lower()
        domain_title = cls._normalize_text(item.get("domain_title")).lower()
        kanban_title = cls._normalize_text(item.get("kanban_title")).lower()

        score = len(matched_terms) * 2.0
        query_lower = query.lower()
        if query_lower in title:
            score += 4.0
        if query_lower in summary:
            score += 2.0
        if any(token in title for token in ["回滚", "排查", "接入", "skill", "告警", "权限", "配置", "部署", "推理", "微调", "agent", "rag"]):
            score += 1.5
        if detected_doc_type == "配置与治理知识库" and any(token in title + summary for token in ["回滚", "配置", "权限", "发布", "灰度"]):
            score += 1.5
        if detected_doc_type == "运维知识库" and any(token in title + summary for token in ["告警", "异常", "排查", "日志", "恢复"]):
            score += 1.5
        if detected_doc_type == "内部研发协作知识库" and any(token in title + summary for token in ["skill", "接入", "联调", "仓库", "工具链"]):
            score += 1.5
        if any(token in title + summary for token in ["rag", "embedding", "agent", "微调", "推理", "部署", "qwen", "glm", "mindie", "lora"]):
            score += 2.0
        if any(token in domain_title + kanban_title for token in ["平台", "研发", "运维", "治理", "模型", "推理"]):
            score += 0.5
        return round(score, 2)

    @staticmethod
    def _build_reason(matched_terms: List[str], item: Dict[str, Any], detected_doc_type: str) -> str:
        if matched_terms:
            return "命中关键词：%s；候选类型偏向 %s。" % ("、".join(matched_terms[:6]), detected_doc_type)
        title = item.get("title") or "该条目"
        return f"{title} 与当前背景存在弱相关，建议人工复核。"

    @classmethod
    def _skill_feasibility(cls, item: Dict[str, Any]) -> tuple[str, str]:
        text = "\n".join(
            [
                cls._normalize_text(item.get("title")),
                cls._normalize_text(item.get("summary")),
                cls._normalize_text(item.get("domain_title")),
                cls._normalize_text(item.get("kanban_title")),
            ]
        ).lower()
        strong_signals = ["步骤", "接入", "排查", "回滚", "权限", "配置", "skill", "联调", "告警", "部署", "发布", "灰度"]
        score = sum(1 for token in strong_signals if token.lower() in text)
        if score >= 3:
            return "high", "标题或摘要具备明确步骤、排障或接入特征，适合后续生成 skill 草稿。"
        if score >= 1:
            return "medium", "存在操作型或排障型信息，可作为 skill 草稿候选，但仍需人工确认。"
        return "low", "更像一般说明或资料页，不建议直接生成 skill。"

    @classmethod
    def _project_fit(cls, item: Dict[str, Any], matched_terms: List[str]) -> tuple[str, List[str]]:
        text = "\n".join(
            [
                cls._normalize_text(item.get("title")),
                cls._normalize_text(item.get("summary")),
                cls._normalize_text(item.get("domain_title")),
                cls._normalize_text(item.get("kanban_title")),
            ]
        ).lower()
        evidence_signals = [
            ("模型", ["qwen", "glm", "mindie", "llm"]),
            ("检索增强", ["rag", "embedding", "rerank", "chunk", "向量"]),
            ("agent", ["agent", "智能助手", "skill", "工具调用", "工作流"]),
            ("部署运维", ["推理", "部署", "灰度", "扩缩容", "告警", "日志"]),
            ("工程实现", ["配置", "发布", "接入", "联调", "权限"]),
        ]
        evidence: List[str] = []
        for label, signals in evidence_signals:
            if any(signal.lower() in text for signal in signals):
                evidence.append(label)
        if len(evidence) >= 3 or len(matched_terms) >= 4:
            return "high", evidence[:5]
        if evidence or matched_terms:
            return "medium", (evidence + matched_terms)[:5]
        return "low", []
