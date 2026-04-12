from __future__ import annotations

import math
from typing import Any, Dict, List

import requests

from app.config import AISettings
from app.utils.text import tokenize


class InternalEmbeddingClient:
    def __init__(self, settings: AISettings) -> None:
        self.settings = settings

    def is_enabled(self) -> bool:
        return bool(
            self.settings.enabled
            and self.settings.embedding_api_key
            and self.settings.embedding_model_name
            and self.settings.embedding_base_url
        )

    def health_check(self) -> Dict[str, Any]:
        if not self.settings.embedding_api_key:
            return {"status": "missing_api_key"}
        if not self.is_enabled():
            return {"status": "disabled"}
        try:
            response = requests.get(
                self.settings.embedding_base_url.rstrip("/") + "/models",
                headers={"Authorization": "Bearer %s" % self.settings.embedding_api_key},
                timeout=self.settings.embedding_timeout,
            )
            return {"status": "ok" if response.ok else "error", "http_status": response.status_code}
        except Exception as exc:  # noqa: BLE001
            return {"status": "error", "error": str(exc)}

    def embed_texts(self, texts: List[str], dimension: int = 64) -> List[List[float]]:
        if self.is_enabled():
            return self._remote_embed_texts(texts)
        return [self._local_embed(text, dimension) for text in texts]

    def _remote_embed_texts(self, texts: List[str]) -> List[List[float]]:
        response = requests.post(
            self.settings.embedding_base_url.rstrip("/") + "/embeddings",
            headers={
                "Authorization": "Bearer %s" % self.settings.embedding_api_key,
                "Content-Type": "application/json",
            },
            json={
                "model": self.settings.embedding_model_name,
                "input": texts,
            },
            timeout=self.settings.embedding_timeout,
        )
        response.raise_for_status()
        data = response.json().get("data", [])
        return [item.get("embedding", []) for item in data]

    def _local_embed(self, text: str, dimension: int) -> List[float]:
        vector = [0.0] * dimension
        for token in tokenize(text):
            slot = hash(token) % dimension
            vector[slot] += 1.0
        norm = math.sqrt(sum(value * value for value in vector)) or 1.0
        return [round(value / norm, 6) for value in vector]
