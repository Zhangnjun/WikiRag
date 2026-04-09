from __future__ import annotations

from fastapi import Header

from app.config import get_settings
from app.core.exceptions import UnauthorizedError


def require_api_key(x_api_key: str = Header(...)) -> None:
    settings = get_settings()
    if x_api_key != settings.app.api_key:
        raise UnauthorizedError()
