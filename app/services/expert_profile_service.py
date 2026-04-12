from __future__ import annotations

from typing import List

from app.repositories.source_repository import SourceRepository
from app.utils.text import extract_keywords


class ExpertProfileService:
    def __init__(self, source_repository: SourceRepository) -> None:
        self.source_repository = source_repository

    def preview_scan(self, person_name: str, focus_topics: List[str] | None = None) -> dict:
        focus_topics = [item.strip() for item in (focus_topics or []) if item and item.strip()]
        local_sources = [
            source
            for source in self.source_repository.list_all()
            if person_name.strip().lower() in (source.owner or "").lower()
        ]
        joined_text = "\n".join(
            [source.source_title for source in local_sources] + [source.raw_content[:500] for source in local_sources]
        )
        inferred_skills = extract_keywords(joined_text, limit=12) if joined_text else []
        recommended_scan_queries = self._build_queries(person_name, focus_topics, inferred_skills)

        notes = [
            "当前版本先预留“按人扫描 Wiki -> 生成人员 Skill 画像”的独立服务结构。",
            "如果 Wiki 搜索接口未来支持作者过滤，可以直接把 recommended_scan_queries 作为候选扫描策略。",
            "当前 preview 结果优先基于本地已导入 source 的 owner 字段和文本内容生成。",
        ]
        return {
            "person_name": person_name,
            "status": "preview_ready",
            "local_source_count": len(local_sources),
            "inferred_skills": inferred_skills,
            "recommended_scan_queries": recommended_scan_queries,
            "notes": notes,
        }

    @staticmethod
    def _build_queries(person_name: str, focus_topics: List[str], inferred_skills: List[str]) -> List[str]:
        candidates = [person_name] + focus_topics + inferred_skills[:8]
        queries: List[str] = []
        seen = set()
        for item in candidates:
            normalized = item.strip()
            if len(normalized) < 2:
                continue
            lowered = normalized.lower()
            if lowered in seen:
                continue
            seen.add(lowered)
            queries.append(normalized)
        return queries[:12]
