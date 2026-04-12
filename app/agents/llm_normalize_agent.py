from __future__ import annotations

import json
from typing import Any

from app.clients.internal_ai import InternalAIClient


class LLMNormalizeAgent:
    def __init__(self, client: InternalAIClient) -> None:
        self.client = client

    def normalize(self, source_payload: dict[str, Any], doc_type: str | None) -> dict[str, Any]:
        prompt = (
            "请将下面的内部知识原始材料整理为结构化 JSON，不允许编造未知信息，未知内容统一填写'待补充'。"
            "字段包括：title, doc_type, knowledge_domain, applicable_mode, product_line, roles, owner, "
            "keywords, summary, scenarios, prerequisites, core_content, steps, branch_logic, risks, "
            "best_practices, related_docs, faq, appendix, image_notes。"
            f"如果已经给定 doc_type，请优先遵循：{doc_type or '无'}。\n"
            f"原始材料：{json.dumps(source_payload, ensure_ascii=False)}"
        )
        return self.client.normalize_document(prompt)
