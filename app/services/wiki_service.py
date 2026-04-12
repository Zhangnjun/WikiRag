from __future__ import annotations

import copy
import logging
import time
from collections import Counter
from typing import Any, Dict, List, Optional

import requests

from app.config import WikiSettings
from app.core.exceptions import AppError
from app.utils.text import extract_keywords, html_to_markdownish
from app.utils.trace import log_event, new_trace_id

LOG = logging.getLogger(__name__)


class WikiService:
    def __init__(self, settings: WikiSettings) -> None:
        self.settings = settings

    def _build_headers(self, cookie_override: Optional[str] = None) -> Dict[str, str]:
        headers = dict(self.settings.headers)
        if cookie_override:
            headers["Cookie"] = cookie_override
        return headers

    @staticmethod
    def _mask_secret(value: str) -> str:
        if not value:
            return ""
        if len(value) <= 8:
            return "***"
        return f"{value[:4]}***{value[-4:]}"

    def _sanitize_headers(self, headers: Dict[str, str]) -> Dict[str, str]:
        sanitized: Dict[str, str] = {}
        for key, value in headers.items():
            if key.lower() in {"cookie", "authorization", "x-api-key", "api-key"}:
                sanitized[key] = self._mask_secret(value)
            else:
                sanitized[key] = value
        return sanitized

    def _verify_ssl_value(self) -> bool | str:
        verify_ssl = self.settings.verify_ssl
        if isinstance(verify_ssl, str):
            lowered = verify_ssl.strip().lower()
            if lowered in {"true", "1", "yes"}:
                return True
            if lowered in {"false", "0", "no"}:
                return False
            return verify_ssl
        return bool(verify_ssl)

    @staticmethod
    def _normalize_text(value: Any) -> str:
        if value is None:
            return ""
        if isinstance(value, str):
            return value
        if isinstance(value, list):
            parts = [WikiService._normalize_text(item).strip() for item in value]
            return "\n".join(part for part in parts if part)
        if isinstance(value, dict):
            return " ".join(
                part for part in [WikiService._normalize_text(item).strip() for item in value.values()] if part
            )
        return str(value)

    def _post_json_with_logging(
        self,
        *,
        url: str,
        headers: Dict[str, str],
        payload: Dict[str, Any],
        trace_id: str,
        step: str,
    ) -> Dict[str, Any]:
        verify_ssl = self._verify_ssl_value()
        timeout = self.settings.timeout
        payload_for_log = self._summarize_search_payload(payload) if step == "wiki_search" else payload
        log_event(
            LOG,
            trace_id=trace_id,
            step=f"{step}_request",
            status="started",
            method="POST",
            url=url,
            headers=self._sanitize_headers(headers),
            timeout=timeout,
            verify_ssl=verify_ssl,
            payload=payload_for_log,
        )

        started_at = time.perf_counter()
        try:
            response = requests.post(
                url,
                headers=headers,
                json=payload,
                timeout=timeout,
                verify=verify_ssl,
            )
        except requests.exceptions.SSLError as exc:
            log_event(
                LOG,
                trace_id=trace_id,
                step=f"{step}_request",
                status="failed",
                error=str(exc),
                exception_type=type(exc).__name__,
                url=url,
                payload=payload_for_log,
                verify_ssl=verify_ssl,
            )
            raise AppError(f"Wiki request SSL failed: {exc}", 502) from exc
        except requests.exceptions.Timeout as exc:
            log_event(
                LOG,
                trace_id=trace_id,
                step=f"{step}_request",
                status="failed",
                error=str(exc),
                exception_type=type(exc).__name__,
                url=url,
                payload=payload_for_log,
                verify_ssl=verify_ssl,
            )
            raise AppError(f"Wiki request timeout: {exc}", 504) from exc
        except requests.RequestException as exc:
            log_event(
                LOG,
                trace_id=trace_id,
                step=f"{step}_request",
                status="failed",
                error=str(exc),
                exception_type=type(exc).__name__,
                url=url,
                payload=payload_for_log,
                verify_ssl=verify_ssl,
            )
            raise AppError(f"Wiki request failed: {exc}", 502) from exc

        elapsed_ms = round((time.perf_counter() - started_at) * 1000, 2)
        response_text_preview = response.text[:1000]
        response_json_parse_ok = False
        response_data: Dict[str, Any] | List[Any] | None = None
        try:
            response_data = response.json()
            response_json_parse_ok = True
        except ValueError:
            response_data = None

        log_event(
            LOG,
            trace_id=trace_id,
            step=f"{step}_response",
            status="success" if response.ok else "http_error",
            status_code=response.status_code,
            elapsed_ms=elapsed_ms,
            response_text_preview=response_text_preview,
            response_json_parse_ok=response_json_parse_ok,
            response_content_type=response.headers.get("Content-Type", ""),
            response_top_level_keys=list(response_data.keys()) if isinstance(response_data, dict) else [],
        )

        if not response.ok:
            log_event(
                LOG,
                trace_id=trace_id,
                step=f"{step}_response",
                status="failed",
                error=f"http status {response.status_code}",
                status_code=response.status_code,
                elapsed_ms=elapsed_ms,
            )
            raise AppError(
                f"Wiki request failed with status {response.status_code}: {response_text_preview[:180]}",
                502 if response.status_code >= 500 else response.status_code,
            )
        if not isinstance(response_data, dict):
            log_event(
                LOG,
                trace_id=trace_id,
                step=f"{step}_response",
                status="failed",
                error="response is not valid JSON object",
                elapsed_ms=elapsed_ms,
                response_content_type=response.headers.get("Content-Type", ""),
            )
            raise AppError(
                f"Wiki response is not valid JSON object, content_type={response.headers.get('Content-Type', '')}",
                502,
            )
        return response_data

    def search(
        self,
        query: str,
        page: int = 1,
        page_size: int = 10,
        search_scope: str = "ALL",
        is_accurate: bool = False,
        wiki_sn: Optional[str] = None,
        domain_id: Optional[int] = None,
        kanban_id: Optional[str] = None,
        sort_field: Optional[str] = None,
        sort_way: Optional[str] = None,
        cookie_override: Optional[str] = None,
        trace_id: str = "",
    ) -> List[Dict[str, Any]]:
        trace_id = trace_id or new_trace_id()
        payload = copy.deepcopy(self.settings.default_search_payload)
        payload["searchKey"] = query
        payload.setdefault("pagination", {})
        payload["pagination"]["current_page"] = page
        payload["pagination"]["page_size"] = page_size
        payload["searchScope"] = search_scope
        payload["isAccurate"] = bool(is_accurate)
        payload["wikiSn"] = wiki_sn if wiki_sn is not None else payload.get("wikiSn")
        payload["domainId"] = domain_id if domain_id is not None else payload.get("domainId")
        payload["kanbanId"] = kanban_id if kanban_id is not None else payload.get("kanbanId")
        if sort_field:
            payload["sortFiled"] = sort_field
        else:
            payload.pop("sortFiled", None)
        if sort_way:
            payload["sortWay"] = sort_way
        else:
            payload.pop("sortWay", None)

        response_data = self._post_json_with_logging(
            url=self.settings.search_url,
            headers=self._build_headers(cookie_override),
            payload=payload,
            trace_id=trace_id,
            step="wiki_search",
        )
        results = response_data.get("data", {}).get("result", [])
        if not isinstance(results, list):
            log_event(
                LOG,
                trace_id=trace_id,
                step="wiki_search_parse",
                status="failed",
                error="data.result is not list",
                result_type=type(results).__name__,
                top_level_keys=list(response_data.keys()),
            )
            raise AppError("Wiki search response missing data.result", 502)
        log_event(
            LOG,
            trace_id=trace_id,
            step="wiki_search_parse",
            status="success",
            query=query,
            page=page,
            page_size=page_size,
            search_scope=search_scope,
            result_count=len(results),
        )
        return results

    def fetch_detail(
        self,
        wiki_sn: str,
        domain_id: Optional[int],
        kanban_id: Optional[int],
        cookie_override: Optional[str] = None,
        trace_id: str = "",
    ) -> Dict[str, Any]:
        trace_id = trace_id or new_trace_id()
        payload = {
            "wiki_sn": wiki_sn,
            "type": self.settings.detail_type,
            "request_tag": str(int(time.time() * 1000)),
            "domain_id": domain_id,
            "kanban_id": kanban_id,
        }
        response_data = self._post_json_with_logging(
            url=self.settings.detail_url,
            headers=self._build_headers(cookie_override),
            payload=payload,
            trace_id=trace_id,
            step="wiki_detail",
        )
        data = response_data.get("data")
        if not isinstance(data, dict):
            log_event(
                LOG,
                trace_id=trace_id,
                step="wiki_detail_parse",
                status="failed",
                error="data is not dict",
                data_type=type(data).__name__,
            )
            raise AppError("Wiki detail response missing data", 502)
        paragraphs = data.get("paragraphs") or []
        raw_html = "\n".join(self._normalize_text(item.get("content", "")) for item in paragraphs if item.get("content")).strip()
        rendered_text, images = html_to_markdownish(raw_html)
        data["rendered_text"] = rendered_text
        data["raw_html"] = raw_html
        data["image_urls"] = images
        log_event(
            LOG,
            trace_id=trace_id,
            step="wiki_detail_parse",
            status="success",
            wiki_sn=wiki_sn,
            paragraph_count=len(paragraphs),
            rendered_text_length=len(rendered_text),
            image_count=len(images),
        )
        return data

    @staticmethod
    def build_url(domain_id: Optional[int], kanban_id: Optional[int], wiki_sn: Optional[str]) -> str:
        if domain_id and kanban_id and wiki_sn:
            return f"https://wiki.huawei.com/domains/{domain_id}/wiki/{kanban_id}/{wiki_sn}"
        return ""

    def normalize_search_results(
        self,
        query: str,
        page: int = 1,
        page_size: int = 10,
        search_scope: str = "ALL",
        is_accurate: bool = False,
        wiki_sn: Optional[str] = None,
        domain_id: Optional[int] = None,
        kanban_id: Optional[str] = None,
        sort_field: Optional[str] = None,
        sort_way: Optional[str] = None,
        cookie_override: Optional[str] = None,
        trace_id: str = "",
    ) -> Dict[str, Any]:
        trace_id = trace_id or new_trace_id()
        items = self.search(
            query,
            page=page,
            page_size=page_size,
            search_scope=search_scope,
            is_accurate=is_accurate,
            wiki_sn=wiki_sn,
            domain_id=domain_id,
            kanban_id=kanban_id,
            sort_field=sort_field,
            sort_way=sort_way,
            cookie_override=cookie_override,
            trace_id=trace_id,
        )
        normalized = []
        field_type_summary: Dict[str, Dict[str, int]] = {
            "title": {},
            "summary": {},
            "domain_title": {},
            "kanban_title": {},
            "created_by": {},
        }
        for item in items:
            assigned_domain = item.get("assigned_domain") or {}
            raw_title = item.get("title")
            raw_summary = item.get("descriptionNoMarksHighlight")
            raw_domain_title = assigned_domain.get("title")
            raw_kanban_title = item.get("kanbanTitle")
            raw_created_by = item.get("createdBySimpleInfo")

            for field_name, raw_value in {
                "title": raw_title,
                "summary": raw_summary,
                "domain_title": raw_domain_title,
                "kanban_title": raw_kanban_title,
                "created_by": raw_created_by,
            }.items():
                field_type = type(raw_value).__name__
                field_type_summary[field_name][field_type] = field_type_summary[field_name].get(field_type, 0) + 1

            domain_id = assigned_domain.get("id")
            kanban_id = item.get("kanbanId")
            wiki_sn = item.get("sn")
            created_by_name, created_by_account = self._extract_author_info(raw_created_by)
            normalized.append(
                {
                    "id": self._normalize_text(item.get("id")),
                    "sn": self._normalize_text(wiki_sn),
                    "title": self._normalize_text(raw_title),
                    "summary": self._normalize_text(raw_summary),
                    "domain_id": domain_id,
                    "domain_title": self._normalize_text(raw_domain_title),
                    "kanban_id": kanban_id,
                    "kanban_title": self._normalize_text(raw_kanban_title),
                    "created_by_name": created_by_name,
                    "created_by_account": created_by_account,
                    "updated_at": self._normalize_text(item.get("last_update_time")),
                    "created_at": self._normalize_text(item.get("create_time")),
                    "url": self.build_url(domain_id, kanban_id, wiki_sn),
                    "raw": item,
                }
            )

        top_items = [
            {
                "title": item["title"],
                "kanbanId": item["kanban_id"],
                "kanbanTitle": item["kanban_title"],
                "create_time": item["created_at"],
                "last_update_time": item["updated_at"],
            }
            for item in normalized[:3]
        ]
        log_event(
            LOG,
            trace_id=trace_id,
            step="wiki_search_normalize",
            status="success",
            query=query,
            items_count=len(normalized),
            field_type_summary=field_type_summary,
            top_items=top_items,
        )
        return {"items": normalized, "total": len(normalized), "page": page, "page_size": page_size}

    def search_by_author(
        self,
        author_query: str,
        page_size: int = 10,
        max_pages: int = 3,
        wiki_sn: Optional[str] = None,
        kanban_id: Optional[str] = None,
        cookie_override: Optional[str] = None,
        trace_id: str = "",
    ) -> Dict[str, Any]:
        trace_id = trace_id or new_trace_id()
        normalized_items: List[Dict[str, Any]] = []
        for page in range(1, max_pages + 1):
            payload = self.normalize_search_results(
                author_query,
                page=page,
                page_size=page_size,
                search_scope="AUTHOR",
                is_accurate=False,
                wiki_sn=wiki_sn,
                kanban_id=kanban_id,
                cookie_override=cookie_override,
                trace_id=trace_id,
            )
            page_items = payload["items"]
            normalized_items.extend(page_items)
            if len(page_items) < page_size:
                break

        deduped = self._dedupe_items(normalized_items)
        keyword_text = "\n".join(
            f"{item['title']} {item['summary']} {item['kanban_title']}" for item in deduped
        )
        stats = {
            "author_query": author_query,
            "article_count": len(deduped),
            "latest_updated_at": max((item["updated_at"] for item in deduped), default=""),
            "wiki_titles": [item["title"] for item in deduped[:10]],
            "high_frequency_keywords": extract_keywords(keyword_text, limit=8) if keyword_text else [],
        }
        return {"stats": stats, "items": deduped}

    def suggest_candidates_by_topic(
        self,
        topic_query: str,
        page_size: int = 10,
        candidate_limit: int = 5,
        author_page_size: int = 20,
        author_max_pages: int = 3,
        wiki_sn: Optional[str] = None,
        kanban_id: Optional[str] = None,
        cookie_override: Optional[str] = None,
        trace_id: str = "",
    ) -> Dict[str, Any]:
        trace_id = trace_id or new_trace_id()
        topic_payload = self.normalize_search_results(
            topic_query,
            page=1,
            page_size=page_size,
            search_scope="ALL",
            is_accurate=False,
            wiki_sn=wiki_sn,
            kanban_id=kanban_id,
            cookie_override=cookie_override,
            trace_id=trace_id,
        )
        author_counter: Counter[tuple[str, str]] = Counter()
        author_seed_items: Dict[tuple[str, str], List[Dict[str, Any]]] = {}
        for item in topic_payload["items"]:
            key = (item.get("created_by_name", ""), item.get("created_by_account", ""))
            if not key[0] and not key[1]:
                continue
            author_counter[key] += 1
            author_seed_items.setdefault(key, []).append(item)

        candidates = []
        for (created_by_name, created_by_account), _ in author_counter.most_common(candidate_limit):
            author_query = created_by_account or created_by_name
            author_payload = self.search_by_author(
                author_query=author_query,
                page_size=author_page_size,
                max_pages=author_max_pages,
                wiki_sn=wiki_sn,
                kanban_id=kanban_id,
                cookie_override=cookie_override,
                trace_id=trace_id,
            )
            author_items = author_payload["items"]
            keywords = author_payload["stats"]["high_frequency_keywords"]
            topic_hits = sum(
                1 for keyword in keywords if keyword and keyword.lower() in topic_query.lower()
            )
            topic_concentration = round(topic_hits / max(len(keywords), 1), 2) if keywords else 0.0
            evidence = [
                f"主题搜索命中 {author_counter[(created_by_name, created_by_account)]} 篇",
                f"创建人文章总数 {author_payload['stats']['article_count']} 篇",
            ]
            if author_payload["stats"]["latest_updated_at"]:
                evidence.append(f"最近更新时间 {author_payload['stats']['latest_updated_at']}")
            if keywords:
                evidence.append("高频关键词: " + "、".join(keywords[:6]))
            recommendation = self._build_candidate_recommendation(
                article_count=author_payload["stats"]["article_count"],
                topic_concentration=topic_concentration,
            )
            candidates.append(
                {
                    "created_by_name": created_by_name,
                    "created_by_account": created_by_account,
                    "article_count": author_payload["stats"]["article_count"],
                    "latest_updated_at": author_payload["stats"]["latest_updated_at"],
                    "possible_skills": keywords[:6],
                    "evidence": evidence,
                    "topic_concentration": topic_concentration,
                    "recommendation": recommendation,
                    "related_articles": author_items[:5],
                }
            )
        return {"topic_query": topic_query, "candidates": candidates}

    @staticmethod
    def _summarize_search_payload(payload: Dict[str, Any]) -> Dict[str, Any]:
        pagination = payload.get("pagination") or {}
        return {
            "pagination": {
                "current_page": pagination.get("current_page"),
                "page_size": pagination.get("page_size"),
            },
            "searchKey": payload.get("searchKey"),
            "status": payload.get("status"),
            "searchType": payload.get("searchType"),
            "wikiSn": payload.get("wikiSn"),
            "searchScope": payload.get("searchScope"),
            "domainId": payload.get("domainId"),
            "kanbanId": payload.get("kanbanId"),
            "isAccurate": payload.get("isAccurate"),
            "sortFiled": payload.get("sortFiled"),
            "sortWay": payload.get("sortWay"),
        }

    @staticmethod
    def _extract_author_info(raw_created_by: Any) -> tuple[str, str]:
        if isinstance(raw_created_by, dict):
            name = WikiService._normalize_text(
                raw_created_by.get("name")
                or raw_created_by.get("userName")
                or raw_created_by.get("displayName")
            )
            account = WikiService._normalize_text(
                raw_created_by.get("account")
                or raw_created_by.get("employeeNo")
                or raw_created_by.get("employeeCode")
                or raw_created_by.get("userId")
            )
            return name, account
        if isinstance(raw_created_by, list):
            text = WikiService._normalize_text(raw_created_by)
        else:
            text = WikiService._normalize_text(raw_created_by)
        if not text:
            return "", ""
        parts = text.split()
        if len(parts) >= 2 and parts[-1].isdigit():
            return " ".join(parts[:-1]), parts[-1]
        return text, ""

    @staticmethod
    def _dedupe_items(items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        deduped: List[Dict[str, Any]] = []
        seen: set[str] = set()
        for item in items:
            key = item.get("sn") or item.get("id") or item.get("url")
            if not key or key in seen:
                continue
            seen.add(key)
            deduped.append(item)
        return deduped

    @staticmethod
    def _build_candidate_recommendation(article_count: int, topic_concentration: float) -> str:
        if article_count >= 20 and topic_concentration >= 0.3:
            return "高潜候选，可作为专家/skill 建议对象，但仍需人工复核文章质量与主题边界。"
        if article_count >= 8:
            return "中等潜力，建议结合文章质量、是否持续更新和是否为原创内容继续判断。"
        return "仅作线索，不建议直接标记为专家。"
