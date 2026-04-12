from __future__ import annotations

import copy
import logging
import time
from typing import Any, Dict, List, Optional

import requests

from app.config import WikiSettings
from app.core.exceptions import AppError
from app.utils.text import html_to_markdownish
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
        log_event(
            LOG,
            trace_id=trace_id,
            step=f"{step}_request",
            status="started",
            method="POST",
            url=url,
            payload=payload,
            timeout=timeout,
            verify_ssl=verify_ssl,
            headers=self._sanitize_headers(headers),
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
                payload=payload,
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
                payload=payload,
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
                payload=payload,
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
            raise AppError(
                f"Wiki request failed with status {response.status_code}: {response_text_preview[:180]}",
                502 if response.status_code >= 500 else response.status_code,
            )
        if not isinstance(response_data, dict):
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
        cookie_override: Optional[str] = None,
        trace_id: str = "",
    ) -> List[Dict[str, Any]]:
        trace_id = trace_id or new_trace_id()
        payload = copy.deepcopy(self.settings.default_search_payload)
        payload["searchKey"] = query
        payload.setdefault("pagination", {})
        payload["pagination"]["current_page"] = page
        payload["pagination"]["page_size"] = page_size

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
        cookie_override: Optional[str] = None,
        trace_id: str = "",
    ) -> Dict[str, Any]:
        trace_id = trace_id or new_trace_id()
        items = self.search(query, page=page, page_size=page_size, cookie_override=cookie_override, trace_id=trace_id)
        normalized = []
        field_type_summary: Dict[str, Dict[str, int]] = {
            "title": {},
            "summary": {},
            "domain_title": {},
            "kanban_title": {},
        }
        for item in items:
            assigned_domain = item.get("assigned_domain") or {}
            raw_title = item.get("title")
            raw_summary = item.get("descriptionNoMarksHighlight")
            raw_domain_title = assigned_domain.get("title")
            raw_kanban_title = item.get("kanbanTitle")

            for field_name, raw_value in {
                "title": raw_title,
                "summary": raw_summary,
                "domain_title": raw_domain_title,
                "kanban_title": raw_kanban_title,
            }.items():
                field_type = type(raw_value).__name__
                field_type_summary[field_name][field_type] = field_type_summary[field_name].get(field_type, 0) + 1

            domain_id = assigned_domain.get("id")
            kanban_id = item.get("kanbanId")
            wiki_sn = item.get("sn")
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
                    "updated_at": self._normalize_text(item.get("last_update_time")),
                    "created_at": self._normalize_text(item.get("create_time")),
                    "url": self.build_url(domain_id, kanban_id, wiki_sn),
                    "raw": item,
                }
            )

        log_event(
            LOG,
            trace_id=trace_id,
            step="wiki_search_normalize",
            status="success",
            query=query,
            items_count=len(normalized),
            field_type_summary=field_type_summary,
        )
        return {"items": normalized, "total": len(normalized), "page": page, "page_size": page_size}
