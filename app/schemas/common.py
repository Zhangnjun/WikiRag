from __future__ import annotations

from pydantic import BaseModel


class MessageResponse(BaseModel):
    message: str


class HealthResponse(BaseModel):
    status: str


class DeleteResponse(BaseModel):
    message: str
    deleted: bool
