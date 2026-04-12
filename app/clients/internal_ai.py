from __future__ import annotations

import json
import re
from typing import Any

import requests

from app.config import AISettings


JSON_BLOCK_RE = re.compile(r"```(?:json)?\s*(.*?)```", re.DOTALL)


class InternalAIClient:
    def __init__(self, settings: AISettings) -> None:
        self.settings = settings

    def is_enabled(self) -> bool:
        return bool(
            self.settings.enabled
            and self.settings.chat_api_key
            and self.settings.chat_model_name
            and self.settings.chat_base_url
        )

    def health_check(self) -> dict[str, Any]:
        if not self.settings.chat_api_key:
            return {"status": "missing_api_key"}
        if not self.is_enabled():
            return {"status": "disabled"}
        try:
            response = requests.get(
                self.settings.chat_base_url.rstrip("/") + "/models",
                headers={"Authorization": "Bearer %s" % self.settings.chat_api_key},
                timeout=self.settings.chat_timeout,
            )
            return {"status": "ok" if response.ok else "error", "http_status": response.status_code}
        except Exception as exc:  # noqa: BLE001
            return {"status": "error", "error": str(exc)}

    def normalize_document(self, prompt: str) -> dict[str, Any]:
        response = requests.post(
            self.settings.chat_base_url.rstrip("/") + "/chat/completions",
            headers={
                "Authorization": "Bearer %s" % self.settings.chat_api_key,
                "Content-Type": "application/json",
            },
            json={
                "model": self.settings.chat_model_name,
                "messages": [
                    {"role": "system", "content": "Return JSON only."},
                    {"role": "user", "content": prompt},
                ],
                "temperature": 0.1,
            },
            timeout=self.settings.chat_timeout,
        )
        response.raise_for_status()
        content = response.json()["choices"][0]["message"]["content"]
        fenced = JSON_BLOCK_RE.search(content)
        if fenced:
            content = fenced.group(1).strip()
        return json.loads(content)
