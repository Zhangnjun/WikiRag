from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict

import yaml
from pydantic import BaseModel, Field


def _expand_env(value: Any) -> Any:
    if isinstance(value, str):
        return os.path.expandvars(value)
    if isinstance(value, list):
        return [_expand_env(item) for item in value]
    if isinstance(value, dict):
        return {key: _expand_env(item) for key, item in value.items()}
    return value


class AppSettings(BaseModel):
    name: str = "WikiRag"
    host: str = "0.0.0.0"
    port: int = 8000
    api_key: str = "change-me"
    log_level: str = "INFO"


class StorageSettings(BaseModel):
    sqlite_path: str = "./app/data/wikirag.db"


class WikiSettings(BaseModel):
    search_url: str
    detail_url: str
    headers: Dict[str, str] = Field(default_factory=dict)
    default_search_payload: Dict[str, Any] = Field(default_factory=dict)
    detail_type: str = "UI"
    timeout: int = 20
    verify_ssl: bool = True


class AISettings(BaseModel):
    enabled: bool = False
    chat_base_url: str = "https://api.openai.com/v1"
    chat_api_key: str = ""
    chat_model_name: str = ""
    chat_timeout: int = 60
    embedding_base_url: str = "https://api.openai.com/v1"
    embedding_api_key: str = ""
    embedding_model_name: str = ""
    embedding_timeout: int = 30


class RAGSettings(BaseModel):
    embedding_dimension: int = 64
    session_max_turns: int = 4
    max_context_chunks: int = 6


class Settings(BaseModel):
    app: AppSettings
    storage: StorageSettings
    wiki: WikiSettings
    ai: AISettings
    rag: RAGSettings

    @property
    def sqlite_abspath(self) -> Path:
        root = Path(__file__).resolve().parents[1]
        return (root / self.storage.sqlite_path).resolve()


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    root = Path(__file__).resolve().parents[1]
    config_path = Path(os.getenv("WIKIRAG_CONFIG", root / "config.yaml"))
    raw = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    return Settings.parse_obj(_expand_env(raw))
