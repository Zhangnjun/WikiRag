from __future__ import annotations

import logging
import uuid
from typing import Any, Dict, List

from app.core.exceptions import AppError, NotFoundError
from app.models.domain import SourceRecord
from app.repositories.source_repository import SourceRepository
from app.services.wiki_service import WikiService
from app.utils.time import now_iso
from app.utils.trace import log_event, new_trace_id

LOG = logging.getLogger(__name__)


class SourceService:
    def __init__(self, repository: SourceRepository, wiki_service: WikiService) -> None:
        self.repository = repository
        self.wiki_service = wiki_service

    def import_source(self, payload: dict, trace_id: str = "") -> SourceRecord:
        trace_id = trace_id or new_trace_id()
        source_type = payload["source_type"]
        source_title = payload.get("source_title") or "待补充"
        source_url = payload.get("source_url") or ""
        raw_content = payload.get("raw_content") or ""
        metadata = payload.get("metadata", {}).copy()
        external_id = payload.get("wiki_sn") or payload.get("external_id") or ""
        skip_if_exists = payload.get("skip_if_exists", True)
        overwrite_if_exists = payload.get("overwrite_if_exists", False)
        log_event(LOG, trace_id=trace_id, step="source_import_start", status="started", external_id=external_id, source_type=source_type)

        if payload.get("fetch_from_wiki"):
            wiki_sn = payload.get("wiki_sn")
            domain_id = payload.get("domain_id")
            kanban_id = payload.get("kanban_id")
            cookie_override = payload.get("cookie")
            if not wiki_sn:
                raise AppError("wiki_sn is required when fetch_from_wiki=true; use /api/wiki/search first to choose result")
            detail = self.wiki_service.fetch_detail(
                wiki_sn,
                domain_id,
                kanban_id,
                cookie_override=cookie_override,
                trace_id=trace_id,
            )
            source_title = detail.get("title") or source_title
            source_url = self.wiki_service.build_url(domain_id, kanban_id, wiki_sn)
            raw_content = detail.get("rendered_text") or raw_content
            external_id = wiki_sn
            metadata.update(
                {
                    "wiki_sn": wiki_sn,
                    "domain_id": domain_id,
                    "kanban_id": kanban_id,
                    "image_urls": detail.get("image_urls", []),
                    "raw_html": detail.get("raw_html", ""),
                    "wiki_detail_url": self.wiki_service.settings.detail_url,
                }
            )

        if not raw_content:
            raise AppError("raw_content is required unless fetch_from_wiki provides content")

        existing = self.repository.find_by_url_or_external_id(source_url, external_id)
        if existing and skip_if_exists and not overwrite_if_exists:
            log_event(
                LOG,
                trace_id=trace_id,
                step="source_import_dedupe",
                status="skipped",
                source_id=existing.source_id,
                external_id=existing.external_id,
            )
            return existing

        if existing and not overwrite_if_exists:
            log_event(
                LOG,
                trace_id=trace_id,
                step="source_import_dedupe",
                status="exists",
                source_id=existing.source_id,
                external_id=existing.external_id,
            )
            return existing

        if existing and overwrite_if_exists:
            updated = self.repository.update(
                existing.source_id,
                {
                    "source_type": source_type,
                    "source_url": source_url,
                    "source_title": source_title,
                    "raw_content": raw_content,
                    "updated_at": payload.get("updated_at") or now_iso(),
                    "owner": payload.get("owner") or existing.owner or "待补充",
                    "tags": payload.get("tags", []),
                    "extra_notes": payload.get("extra_notes") or "",
                    "metadata": metadata,
                    "import_status": "success",
                    "last_error_message": "",
                    "last_synced_at": now_iso(),
                    "external_id": external_id,
                    "is_archived": False,
                },
            )
            log_event(
                LOG,
                trace_id=trace_id,
                step="source_import_upsert",
                status="success",
                source_id=updated.source_id,
                external_id=external_id,
            )
            return updated

        timestamp = payload.get("updated_at") or now_iso()
        record = SourceRecord(
            source_id=str(uuid.uuid4()),
            source_type=source_type,
            source_url=source_url,
            source_title=source_title,
            raw_content=raw_content,
            updated_at=timestamp,
            owner=payload.get("owner") or "待补充",
            tags=payload.get("tags", []),
            created_at=now_iso(),
            is_archived=False,
            extra_notes=payload.get("extra_notes") or "",
            metadata=metadata,
            import_status="success",
            normalize_status="pending",
            last_error_message="",
            last_synced_at=now_iso(),
            external_id=external_id,
        )
        created = self.repository.create(record)
        log_event(
            LOG,
            trace_id=trace_id,
            step="source_import_finish",
            status="success",
            source_id=created.source_id,
            external_id=external_id,
        )
        return created

    def get_source(self, source_id: str) -> SourceRecord:
        record = self.repository.get(source_id)
        if not record:
            raise NotFoundError(f"Source not found: {source_id}")
        return record

    def list_sources(self, filters: Dict[str, Any], page: int, page_size: int):
        return self.repository.list_filtered(filters, page, page_size)

    def delete_source(self, source_id: str, trace_id: str = "") -> Dict[str, Any]:
        trace_id = trace_id or new_trace_id()
        source = self.get_source(source_id)
        linked_count = self.repository.count_knowledge_by_source(source_id)
        if linked_count > 0:
            self.repository.update(
                source_id,
                {
                    "is_archived": True,
                    "last_error_message": "Source archived because linked knowledge documents exist",
                },
            )
            log_event(LOG, trace_id=trace_id, step="source_delete", status="soft_deleted", source_id=source_id, external_id=source.external_id)
            return {"deleted": False, "message": "Source has linked knowledge documents and was archived instead of hard deleted"}

        self.repository.update(source_id, {"is_archived": True})
        log_event(LOG, trace_id=trace_id, step="source_delete", status="soft_deleted", source_id=source_id, external_id=source.external_id)
        return {"deleted": True, "message": "Source archived successfully"}

    def batch_import(self, payload: dict, trace_id: str = "") -> List[Dict[str, str]]:
        trace_id = trace_id or new_trace_id()
        results = []
        items = list(payload.get("items", []))
        for wiki_sn in payload.get("wiki_sns", []):
            items.append(
                {
                    "source_type": "wiki_api",
                    "fetch_from_wiki": True,
                    "wiki_sn": wiki_sn,
                    "source_title": "",
                    "owner": "",
                    "tags": [],
                    "metadata": {},
                    "skip_if_exists": payload.get("skip_if_exists", True),
                    "overwrite_if_exists": payload.get("overwrite_if_exists", False),
                }
            )
        for wiki_item in payload.get("wiki_items", []):
            items.append(
                {
                    "source_type": "wiki_api",
                    "fetch_from_wiki": True,
                    "wiki_sn": wiki_item.get("wiki_sn") or wiki_item.get("sn"),
                    "domain_id": wiki_item.get("domain_id"),
                    "kanban_id": wiki_item.get("kanban_id"),
                    "source_title": wiki_item.get("source_title") or wiki_item.get("title"),
                    "owner": wiki_item.get("owner"),
                    "tags": wiki_item.get("tags", []),
                    "updated_at": wiki_item.get("updated_at"),
                    "extra_notes": wiki_item.get("extra_notes"),
                    "metadata": wiki_item.get("metadata", {}),
                    "cookie": wiki_item.get("cookie") or payload.get("cookie"),
                    "skip_if_exists": payload.get("skip_if_exists", True),
                    "overwrite_if_exists": payload.get("overwrite_if_exists", False),
                }
            )

        for item in items:
            try:
                record = self.import_source(
                    {
                        **item,
                        "skip_if_exists": payload.get("skip_if_exists", True),
                        "overwrite_if_exists": payload.get("overwrite_if_exists", False),
                    },
                    trace_id=trace_id,
                )
                results.append(
                    {
                        "source_id": record.source_id,
                        "source_title": record.source_title,
                        "external_id": record.external_id,
                        "status": "success",
                        "message": "Imported successfully",
                    }
                )
            except Exception as exc:  # noqa: BLE001
                log_event(
                    LOG,
                    trace_id=trace_id,
                    step="source_batch_import_item",
                    status="failed",
                    external_id=item.get("wiki_sn") or "",
                    error=str(exc),
                )
                results.append(
                    {
                        "source_id": "",
                        "source_title": item.get("source_title") or "",
                        "external_id": item.get("wiki_sn") or "",
                        "status": "failed",
                        "message": str(exc),
                    }
                )
        return results
