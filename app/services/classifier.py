from __future__ import annotations

from dataclasses import dataclass


@dataclass
class ClassificationResult:
    doc_type: str
    knowledge_domain: str
    applicable_mode: str
    reasons: list[str]


class DocumentClassifier:
    RULES = {
        "运维知识库": ["报错", "失败", "告警", "异常", "排查", "日志", "恢复", "故障"],
        "内部研发协作知识库": ["接入", "开发", "联调", "仓库", "skill", "工具链", "扫描", "配置变更", "研发"],
        "新手知识库": ["新手", "首次", "入门", "开通", "准备", "开始使用", "快速开始"],
        "配置与治理知识库": ["配置项", "权限", "发布", "回滚", "治理", "生效范围", "灰度", "审批"],
    }

    def classify(self, text: str, explicit_doc_type: str | None = None) -> ClassificationResult:
        if explicit_doc_type:
            return ClassificationResult(
                doc_type=explicit_doc_type,
                knowledge_domain=explicit_doc_type,
                applicable_mode=self._default_mode(explicit_doc_type),
                reasons=["explicit doc_type provided"],
            )

        scores: dict[str, list[str]] = {doc_type: [] for doc_type in self.RULES}
        lowered = text.lower()
        for doc_type, keywords in self.RULES.items():
            for keyword in keywords:
                if keyword.lower() in lowered:
                    scores[doc_type].append(keyword)

        best_type = max(scores.items(), key=lambda item: len(item[1]))[0]
        reasons = scores[best_type] or ["fallback default"]
        return ClassificationResult(
            doc_type=best_type,
            knowledge_domain=best_type,
            applicable_mode=self._default_mode(best_type),
            reasons=reasons,
        )

    @staticmethod
    def _default_mode(doc_type: str) -> str:
        mapping = {
            "运维知识库": "排障 / 运维",
            "内部研发协作知识库": "研发协作",
            "新手知识库": "入门 / 操作",
            "配置与治理知识库": "配置 / 发布 / 治理",
        }
        return mapping.get(doc_type, "待补充")
