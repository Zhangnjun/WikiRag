from __future__ import annotations

import copy
import logging
import time
from typing import Any, Dict, List, Optional

import requests

from app.config import WikiSettings
from app.core.exceptions import AppError
from app.utils.text import html_to_markdownish

LOG = logging.getLogger(__name__)


class WikiService:
    def __init__(self, settings: WikiSettings) -> None:
        self.settings = settings

    def search(self, query: str, page: int = 1, page_size: int = 10) -> List[Dict[str, Any]]:
        payload = copy.deepcopy(self.settings.default_search_payload)
        payload["searchKey"] = query
        payload.setdefault("pagination", {})
        payload["pagination"]["current_page"] = page
        payload["pagination"]["page_size"] = page_size

        response = requests.post(
            self.settings.search_url,
            headers=self.settings.headers,
            json=payload,
            timeout=self.settings.timeout,
            verify=self.settings.verify_ssl,
        )
        response.raise_for_status()
        results = response.json().get("data", {}).get("result", [])
        if not isinstance(results, list):
            raise AppError("Wiki search response missing data.result", 502)
        return results

    def fetch_detail(self, wiki_sn: str, domain_id: Optional[int], kanban_id: Optional[int]) -> Dict[str, Any]:
        payload = {
            "wiki_sn": wiki_sn,
            "type": self.settings.detail_type,
            "request_tag": str(int(time.time() * 1000)),
            "domain_id": domain_id,
            "kanban_id": kanban_id,
        }
        response = requests.post(
            self.settings.detail_url,
            headers=self.settings.headers,
            json=payload,
            timeout=self.settings.timeout,
            verify=self.settings.verify_ssl,
        )
        response.raise_for_status()
        data = response.json().get("data")
        if not isinstance(data, dict):
            raise AppError("Wiki detail response missing data", 502)
        paragraphs = data.get("paragraphs") or []
        raw_html = "\n".join(item.get("content", "") for item in paragraphs if item.get("content")).strip()
        rendered_text, images = html_to_markdownish(raw_html)
        data["rendered_text"] = rendered_text
        data["raw_html"] = raw_html
        data["image_urls"] = images
        return data

    @staticmethod
    def build_url(domain_id: Optional[int], kanban_id: Optional[int], wiki_sn: Optional[str]) -> str:
        if domain_id and kanban_id and wiki_sn:
            return f"https://wiki.huawei.com/domains/{domain_id}/wiki/{kanban_id}/{wiki_sn}"
        return ""

    def normalize_search_results(self, query: str, page: int = 1, page_size: int = 10) -> Dict[str, Any]:
        items = self.search(query, page=page, page_size=page_size)
        normalized = []
        for item in items:
            assigned_domain = item.get("assigned_domain") or {}
            domain_id = assigned_domain.get("id")
            kanban_id = item.get("kanbanId")
            wiki_sn = item.get("sn")
            normalized.append(
                {
                    "id": str(item.get("id") or ""),
                    "sn": wiki_sn or "",
                    "title": item.get("title") or "",
                    "summary": item.get("descriptionNoMarksHighlight") or "",
                    "domain_id": domain_id,
                    "domain_title": assigned_domain.get("title") or "",
                    "kanban_id": kanban_id,
                    "kanban_title": item.get("kanbanTitle") or "",
                    "updated_at": item.get("last_update_time") or "",
                    "created_at": item.get("create_time") or "",
                    "url": self.build_url(domain_id, kanban_id, wiki_sn),
                    "raw": item,
                }
            )
        return {"items": normalized, "total": len(normalized), "page": page, "page_size": page_size}
