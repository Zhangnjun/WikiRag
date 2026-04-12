from __future__ import annotations

from .text import PENDING


MARKDOWN_TEMPLATE = """# {title}

## 1. 文档元信息
- 文档类型：{doc_type}
- 所属知识域：{knowledge_domain}
- 适用模式：{applicable_mode}
- 适用产品线：{product_line}
- 适用角色：{roles}
- 更新时间：{updated_at}
- 负责人：{owner}
- 关键词：{keywords}

## 2. 文档摘要
{summary}

## 3. 适用场景
{scenarios}

## 4. 前置条件
{prerequisites}

## 5. 核心内容
{core_content}

## 6. 操作步骤 / 排查步骤
{steps}

## 7. 判断条件 / 分支逻辑
{branch_logic}

## 8. 常见错误 / 风险点
{risks}

## 9. 处理建议 / 最佳实践
{best_practices}

## 10. 关联资料
{related_docs}

## 11. FAQ
{faq}

## 12. 附录
{appendix}

## 13. 图片与示意
- 架构图：{architecture}
- 流程图：{flowchart}
- 页面截图：{screenshots}
- 其它示意：{other_images}
"""


def render_markdown(payload: dict[str, str]) -> str:
    return MARKDOWN_TEMPLATE.format(
        title=payload["title"],
        doc_type=payload["doc_type"],
        knowledge_domain=payload["knowledge_domain"],
        applicable_mode=payload["applicable_mode"],
        product_line=payload["product_line"] or PENDING,
        roles=payload["roles"] or PENDING,
        updated_at=payload["updated_at"] or PENDING,
        owner=payload["owner"] or PENDING,
        keywords=payload["keywords"] or PENDING,
        summary=payload["summary"] or PENDING,
        scenarios=payload["scenarios"] or PENDING,
        prerequisites=payload["prerequisites"] or PENDING,
        core_content=payload["core_content"] or PENDING,
        steps=payload["steps"] or PENDING,
        branch_logic=payload["branch_logic"] or PENDING,
        risks=payload["risks"] or PENDING,
        best_practices=payload["best_practices"] or PENDING,
        related_docs=payload["related_docs"] or PENDING,
        faq=payload["faq"] or PENDING,
        appendix=payload["appendix"] or PENDING,
        architecture=payload["architecture"] or PENDING,
        flowchart=payload["flowchart"] or PENDING,
        screenshots=payload["screenshots"] or PENDING,
        other_images=payload["other_images"] or PENDING,
    )
