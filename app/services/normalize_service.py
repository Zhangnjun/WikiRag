from __future__ import annotations

import json
import logging
import uuid
from typing import Any

from app.agents.llm_normalize_agent import LLMNormalizeAgent
from app.core.exceptions import AppError
from app.models.domain import DOC_TYPES, KnowledgeDocument, PENDING, SourceRecord
from app.services.classifier import DocumentClassifier
from app.utils.markdown import render_markdown
from app.utils.text import clean_text, extract_keywords, split_lines
from app.utils.time import now_iso
from app.utils.trace import log_event, new_trace_id

LOG = logging.getLogger(__name__)


class KnowledgeNormalizeService:
    def __init__(self, classifier: DocumentClassifier, llm_agent: LLMNormalizeAgent | None = None) -> None:
        self.classifier = classifier
        self.llm_agent = llm_agent

    def normalize(self, source: SourceRecord, use_ai: bool = False, doc_type: str | None = None, trace_id: str = "") -> KnowledgeDocument:
        trace_id = trace_id or new_trace_id()
        if doc_type and doc_type not in DOC_TYPES:
            raise AppError(f"Unsupported doc_type: {doc_type}")

        log_event(LOG, trace_id=trace_id, step="normalize_start", status="started", source_id=source.source_id, external_id=source.external_id)
        classification = self.classifier.classify(
            "\n".join([source.source_title, source.raw_content, source.extra_notes]),
            explicit_doc_type=doc_type,
        )
        log_event(
            LOG,
            trace_id=trace_id,
            step="classify_document",
            status="success",
            source_id=source.source_id,
            external_id=source.external_id,
            doc_type=classification.doc_type,
        )
        structured = self._build_rule_payload(source, classification.doc_type, classification.knowledge_domain, classification.applicable_mode)
        ai_enhanced = False
        normalize_mode = "rule"

        if use_ai and self.llm_agent:
            try:
                log_event(LOG, trace_id=trace_id, step="ai_normalize_call", status="started", source_id=source.source_id, external_id=source.external_id)
                ai_payload = self.llm_agent.normalize(
                    {
                        "source_title": source.source_title,
                        "source_type": source.source_type,
                        "source_url": source.source_url,
                        "raw_content": source.raw_content,
                        "owner": source.owner,
                        "tags": source.tags,
                        "updated_at": source.updated_at,
                        "extra_notes": source.extra_notes,
                    },
                    classification.doc_type,
                )
                structured = self._merge_ai_payload(structured, ai_payload)
                ai_enhanced = True
                normalize_mode = "ai_enhanced"
                log_event(LOG, trace_id=trace_id, step="ai_normalize_call", status="success", source_id=source.source_id, external_id=source.external_id)
            except Exception as exc:  # noqa: BLE001
                LOG.warning("AI normalize failed, fallback to rule mode: %s", exc)
                log_event(LOG, trace_id=trace_id, step="ai_normalize_call", status="failed", source_id=source.source_id, external_id=source.external_id, error=str(exc))

        markdown_content = render_markdown(
            {
                "title": structured["title"],
                "doc_type": structured["doc_type"],
                "knowledge_domain": structured["knowledge_domain"],
                "applicable_mode": structured["applicable_mode"],
                "product_line": "、".join(structured["product_line"]),
                "roles": "、".join(structured["roles"]),
                "updated_at": structured["updated_at"],
                "owner": structured["owner"],
                "keywords": "、".join(structured["keywords"]),
                "summary": structured["summary"],
                "scenarios": structured["scenarios"],
                "prerequisites": structured["prerequisites"],
                "core_content": structured["core_content"],
                "steps": structured["steps"],
                "branch_logic": structured["branch_logic"],
                "risks": structured["risks"],
                "best_practices": structured["best_practices"],
                "related_docs": structured["related_docs"],
                "faq": structured["faq"],
                "appendix": structured["appendix"],
                "architecture": structured["image_notes"]["架构图"],
                "flowchart": structured["image_notes"]["流程图"],
                "screenshots": structured["image_notes"]["页面截图"],
                "other_images": structured["image_notes"]["其它示意"],
            }
        )

        timestamp = now_iso()
        document = KnowledgeDocument(
            doc_id=str(uuid.uuid4()),
            title=structured["title"],
            doc_type=structured["doc_type"],
            knowledge_domain=structured["knowledge_domain"],
            applicable_mode=structured["applicable_mode"],
            product_line=structured["product_line"],
            roles=structured["roles"],
            owner=structured["owner"],
            keywords=structured["keywords"],
            summary=structured["summary"],
            scenarios=structured["scenarios"],
            prerequisites=structured["prerequisites"],
            core_content=structured["core_content"],
            steps=structured["steps"],
            branch_logic=structured["branch_logic"],
            risks=structured["risks"],
            best_practices=structured["best_practices"],
            related_docs=structured["related_docs"],
            faq=structured["faq"],
            appendix=structured["appendix"],
            image_notes=structured["image_notes"],
            markdown_content=markdown_content,
            source_id=source.source_id,
            source_url=source.source_url,
            created_at=timestamp,
            updated_at=source.updated_at or timestamp,
            is_archived=False,
            normalize_mode=normalize_mode,
            ai_enhanced=ai_enhanced,
            source_title=source.source_title,
            metadata={
                "source_type": source.source_type,
                "source_tags": source.tags,
                "source_metadata": source.metadata,
                "classification_reasons": classification.reasons,
            },
        )
        log_event(LOG, trace_id=trace_id, step="normalize_finish", status="success", source_id=source.source_id, external_id=source.external_id, normalize_mode=normalize_mode)
        return document

    def _build_rule_payload(
        self,
        source: SourceRecord,
        doc_type: str,
        knowledge_domain: str,
        applicable_mode: str,
    ) -> dict[str, Any]:
        text = clean_text(source.raw_content)
        lines = split_lines(source.raw_content)
        keywords = extract_keywords("\n".join([source.source_title, source.raw_content, " ".join(source.tags)]))

        summary = self._first_matching_paragraph(lines, 3)
        scenarios = self._pick_section(doc_type, text, "scenarios")
        prerequisites = self._pick_section(doc_type, text, "prerequisites")
        core_content = self._pick_section(doc_type, text, "core_content")
        steps = self._pick_section(doc_type, text, "steps")
        branch_logic = self._pick_section(doc_type, text, "branch_logic")
        risks = self._pick_section(doc_type, text, "risks")
        best_practices = self._pick_section(doc_type, text, "best_practices")
        related_docs = source.source_url or PENDING
        faq = self._extract_faq(lines)
        appendix = source.extra_notes or PENDING

        role_candidates = [tag for tag in source.tags if any(token in tag for token in ["开发", "运维", "测试", "算法", "产品", "支持"])]
        product_line = [tag for tag in source.tags if tag not in role_candidates][:3]
        image_notes = {
            "架构图": PENDING,
            "流程图": PENDING,
            "页面截图": PENDING,
            "其它示意": PENDING,
        }
        if "image_urls" in source.metadata and source.metadata["image_urls"]:
            image_notes["其它示意"] = "已提取图片 URL，详见 metadata"

        return {
            "title": source.source_title or PENDING,
            "doc_type": doc_type,
            "knowledge_domain": knowledge_domain,
            "applicable_mode": applicable_mode,
            "product_line": product_line or [PENDING],
            "roles": role_candidates or [PENDING],
            "owner": source.owner or PENDING,
            "keywords": keywords or [PENDING],
            "summary": summary,
            "scenarios": scenarios,
            "prerequisites": prerequisites,
            "core_content": core_content,
            "steps": steps,
            "branch_logic": branch_logic,
            "risks": risks,
            "best_practices": best_practices,
            "related_docs": related_docs,
            "faq": faq,
            "appendix": appendix,
            "updated_at": source.updated_at or PENDING,
            "image_notes": image_notes,
        }

    def _merge_ai_payload(self, base: dict[str, Any], ai_payload: dict[str, Any]) -> dict[str, Any]:
        if not isinstance(ai_payload, dict):
            return base
        merged = json.loads(json.dumps(base, ensure_ascii=False))
        for key, value in ai_payload.items():
            if key not in merged:
                continue
            if isinstance(merged[key], list):
                merged[key] = value if isinstance(value, list) and value else merged[key]
            elif isinstance(merged[key], dict):
                if isinstance(value, dict):
                    for sub_key, sub_value in value.items():
                        merged[key][sub_key] = sub_value or merged[key].get(sub_key, PENDING)
            else:
                merged[key] = value or merged[key]

        if merged.get("doc_type") not in DOC_TYPES:
            merged["doc_type"] = base["doc_type"]
        merged["product_line"] = self._safe_list(merged.get("product_line"))
        merged["roles"] = self._safe_list(merged.get("roles"))
        merged["keywords"] = self._safe_list(merged.get("keywords"))
        for field in [
            "title",
            "knowledge_domain",
            "applicable_mode",
            "owner",
            "summary",
            "scenarios",
            "prerequisites",
            "core_content",
            "steps",
            "branch_logic",
            "risks",
            "best_practices",
            "related_docs",
            "faq",
            "appendix",
            "updated_at",
        ]:
            merged[field] = merged.get(field) or base.get(field) or PENDING
        for image_field in ["架构图", "流程图", "页面截图", "其它示意"]:
            merged["image_notes"][image_field] = merged["image_notes"].get(image_field) or PENDING
        return merged

    @staticmethod
    def _safe_list(value: Any) -> list[str]:
        if isinstance(value, list) and value:
            return [item for item in value if item] or [PENDING]
        if isinstance(value, str) and value:
            return [value]
        return [PENDING]

    @staticmethod
    def _first_matching_paragraph(lines: list[str], limit: int) -> str:
        return "\n".join(lines[:limit]) if lines else PENDING

    @staticmethod
    def _extract_faq(lines: list[str]) -> str:
        faq_lines = [line for line in lines if "FAQ" in line or "常见问题" in line or "Q:" in line]
        return "\n".join(faq_lines[:6]) if faq_lines else PENDING

    @staticmethod
    def _pick_section(doc_type: str, text: str, field: str) -> str:
        snippets = {
            "运维知识库": {
                "scenarios": "适用于故障、异常、告警、恢复相关排查场景。",
                "prerequisites": "需要具备日志、监控、配置和权限信息；缺失部分待补充。",
                "core_content": text[:1200] or PENDING,
                "steps": "1. 复现或确认现象\n2. 收集日志与报错\n3. 核查配置和依赖服务\n4. 根据判断条件执行恢复或升级处理",
                "branch_logic": "若存在明确报错日志，优先按错误线索分支排查；否则从配置、依赖、权限三类高概率原因入手。",
                "risks": "误操作、误回滚、误删数据、配置覆盖不完整等风险需重点关注。",
                "best_practices": "先收集证据再操作；重要变更前做好备份或回滚预案。",
            },
            "新手知识库": {
                "scenarios": "适用于首次接触平台、功能开通、操作入门等场景。",
                "prerequisites": "账号、权限、环境与依赖工具未明确时统一标记待补充。",
                "core_content": text[:1200] or PENDING,
                "steps": "1. 准备账号和权限\n2. 确认环境前置条件\n3. 按步骤完成配置或接入\n4. 验证是否达到完成标准",
                "branch_logic": "如权限不足先处理权限；如环境未就绪先补齐前置条件。",
                "risks": "跳步执行、环境缺失、配置遗漏可能导致结果不一致。",
                "best_practices": "按顺序操作，完成后记录验证结果和常见问题。",
            },
            "内部研发协作知识库": {
                "scenarios": "适用于内部研发、平台、算法、支持等团队的协作与联调。",
                "prerequisites": "需确认仓库、工具链、skill、联调环境及相关权限。",
                "core_content": text[:1200] or PENDING,
                "steps": "1. 确认协作目标和参与角色\n2. 准备仓库、环境和工具链\n3. 执行接入、扫描或联调步骤\n4. 记录结果与后续规范",
                "branch_logic": "若是 skill/工具接入问题，先核查配置和依赖；若是联调问题，优先校验接口、权限和环境一致性。",
                "risks": "跨团队信息不一致、环境漂移、权限遗漏、规范缺失。",
                "best_practices": "统一使用规范模板记录上下文、步骤、风险和关联资料。",
            },
            "配置与治理知识库": {
                "scenarios": "适用于配置管理、发布治理、权限调整、回滚处理等场景。",
                "prerequisites": "需要明确生效范围、发布规则、回滚策略和审批权限。",
                "core_content": text[:1200] or PENDING,
                "steps": "1. 明确配置项和适用范围\n2. 审核权限和发布条件\n3. 执行变更\n4. 验证生效结果\n5. 必要时按规则回滚",
                "branch_logic": "若变更未生效，先确认范围和缓存；若出现异常，按回滚规则处理。",
                "risks": "权限越权、范围误伤、回滚不完整、配置漂移。",
                "best_practices": "所有治理与发布动作应有审批、记录、验证和回滚预案。",
            },
        }
        return snippets[doc_type][field]
