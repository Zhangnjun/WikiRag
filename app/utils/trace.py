from __future__ import annotations

import json
import logging
import uuid
from typing import Any, Dict, Optional


def new_trace_id() -> str:
    return str(uuid.uuid4())


def log_event(
    logger: logging.Logger,
    *,
    trace_id: str,
    step: str,
    status: str,
    source_id: Optional[str] = None,
    external_id: Optional[str] = None,
    error: Optional[str] = None,
    **extra: Any
) -> None:
    payload: Dict[str, Any] = {
        "trace_id": trace_id,
        "source_id": source_id or "",
        "external_id": external_id or "",
        "step": step,
        "status": status,
        "error": error or "",
    }
    payload.update(extra)
    logger.info(json.dumps(payload, ensure_ascii=False))
