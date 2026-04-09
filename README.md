# WikiRag

WikiRag 是一个可运行的 FastAPI 项目，用于将内网 Wiki 或人工输入的原始材料整理为统一 Markdown 知识文档，并提供基础管理与检索能力，为后续 RAG 预留扩展接口。

## 能力范围

- 原始材料录入
- 基于规则或 AI 增强的知识规范化整理
- 标准 Markdown 输出
- 知识文档列表、详情、更新、归档
- 基础文本检索
- Markdown 自动切 chunk
- chunk 自动 embedding
- hybrid retrieval 与最小 RAG 查询
- Huawei Wiki 搜索 / 详情地址保留在配置中
- 后续 OCR、Embedding、向量检索、反馈、定时同步的扩展预留

## 目录结构

```text
WikiRag/
├── app/
│   ├── api/
│   ├── agents/
│   ├── clients/
│   ├── core/
│   ├── data/
│   ├── models/
│   ├── repositories/
│   ├── schemas/
│   ├── services/
│   ├── utils/
│   ├── config.py
│   └── main.py
├── config.yaml
├── requirements.txt
└── scripts/start.sh
```

## 快速启动

```bash
cd /Users/sheldonzhao/Desktop/github/findInteresting/WikiRag
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```

## Quick Start

1. 启动服务：

```bash
cd /Users/sheldonzhao/Desktop/github/findInteresting/WikiRag
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```

2. 打开页面：

- RAG Debug UI: [http://127.0.0.1:8000/rag-debug](http://127.0.0.1:8000/rag-debug)
- Swagger UI: [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)
- Health: [http://127.0.0.1:8000/api/health](http://127.0.0.1:8000/api/health)

3. 如果数据库里还没有数据，先执行：

```bash
python scripts/run_rag_eval.py
```

这一步会自动导入演示数据、做 normalize、切 chunk、生成 embedding，并输出评测报告。

默认 API Key 来自 [`config.yaml`](/Users/sheldonzhao/Desktop/github/findInteresting/WikiRag/config.yaml) 中的 `app.api_key`，请求时放到 `X-API-Key` 头里。

如果要启用 Huawei Wiki 抓取，先设置：

```bash
export HUAWEI_WIKI_COOKIE='your_cookie'
```

如果要启用内部 AI：

```bash
export OPENAI_API_KEY='your_key'
export OPENAI_MODEL='gpt-4.1-mini'
```

并把 `config.yaml` 中 `ai.enabled` 改成 `true`。

## 示例请求

### 1. 导入原始材料

```bash
curl -X POST "http://127.0.0.1:8000/api/source/import" \
  -H "Content-Type: application/json" \
  -H "X-API-Key: change-me" \
  -d '{
    "source_title": "内部 skill 接入与仓库扫描说明",
    "source_type": "manual",
    "source_url": "https://wiki.huawei.com/domains/156/wiki/4198/WIKI2026040510674417",
    "raw_content": "适用于内部研发协作。内容包含仓库扫描、skill 接入、联调步骤、常见失败日志、配置变更说明。若扫描失败，请检查权限、配置项和工具链版本。",
    "owner": "平台研发组",
    "tags": ["研发", "skill", "仓库扫描", "平台"],
    "updated_at": "2026-04-10T00:00:00+00:00"
  }'
```

### 2. 基于 source_id 生成规范化文档

```bash
curl -X POST "http://127.0.0.1:8000/api/knowledge/normalize" \
  -H "Content-Type: application/json" \
  -H "X-API-Key: change-me" \
  -d '{
    "source_id": "replace-source-id",
    "use_ai": false
  }'
```

### 3. 直接从 Wiki 详情导入并整理

```bash
curl -X POST "http://127.0.0.1:8000/api/source/import" \
  -H "Content-Type: application/json" \
  -H "X-API-Key: change-me" \
  -d '{
    "source_type": "wiki_api",
    "fetch_from_wiki": true,
    "wiki_sn": "WIKI2026040410674038",
    "domain_id": 156,
    "kanban_id": 4198,
    "owner": "待补充",
    "tags": ["研发", "wiki"]
  }'
```

### 4. 搜索知识文档

```bash
curl -X POST "http://127.0.0.1:8000/api/knowledge/search" \
  -H "Content-Type: application/json" \
  -H "X-API-Key: change-me" \
  -d '{
    "query": "skill 接入",
    "doc_type": "内部研发协作知识库"
  }'
```

### 5. 搜索 Wiki 候选结果

```bash
curl -X POST "http://127.0.0.1:8000/api/wiki/search" \
  -H "Content-Type: application/json" \
  -H "X-API-Key: change-me" \
  -d '{
    "search_query": "skill 接入",
    "page": 1,
    "page_size": 10
  }'
```

### 6. 查看 Source 列表

```bash
curl "http://127.0.0.1:8000/api/source/list?page=1&page_size=20&source_type=manual" \
  -H "X-API-Key: change-me"
```

### 7. 批量导入多个 Source

```bash
curl -X POST "http://127.0.0.1:8000/api/source/import/batch" \
  -H "Content-Type: application/json" \
  -H "X-API-Key: change-me" \
  -d '{
    "skip_if_exists": true,
    "overwrite_if_exists": false,
    "items": [
      {
        "source_title": "运维排障案例",
        "source_type": "manual",
        "source_url": "https://wiki.huawei.com/example/a",
        "raw_content": "出现告警和异常时，先检查日志和配置项。",
        "owner": "运维组",
        "tags": ["运维", "告警"]
      }
    ],
    "wiki_items": [
      {
        "wiki_sn": "WIKI2026040410674038",
        "domain_id": 156,
        "kanban_id": 4198,
        "tags": ["wiki", "研发"]
      }
    ]
  }'
```

### 8. RAG 查询

```bash
curl -X POST "http://127.0.0.1:8000/api/rag/query" \
  -H "Content-Type: application/json" \
  -H "X-API-Key: change-me" \
  -d '{
    "query": "配置变更异常后怎么回滚",
    "top_k": 3,
    "use_rerank": true,
    "use_ai": false,
    "filters": {
      "doc_type": "配置与治理知识库"
    },
    "debug": true
  }'
```

## RAG 调试页面使用说明

调试页地址：

- [http://127.0.0.1:8000/rag-debug](http://127.0.0.1:8000/rag-debug)

页面默认已经填好一组可直接提交的示例参数：

- API Key: `change-me`
- Query: `配置变更异常后怎么回滚`
- Top K: `3`
- Use AI: 关闭
- Use Rerank: 开启
- Debug: 开启
- Doc Type: `配置与治理知识库`

页面区域说明：

- 查询输入区：填写 API Key、query、session_id、top_k、过滤条件和开关
- 回答展示区：看 `answer`、`status`、`latency_ms`、`session_id`
- 引用展示区：看 `doc_id/source_id/section_title/chunk 摘要`
- 检索片段展示区：看最终返回的 chunk、score 和来源
- Debug 信息区：看 `keyword_hits/vector_hits/final_hits/query_rewrite`
- 错误提示区：接口报错会直接显示

最简单的操作方式：

1. 打开 `/rag-debug`
2. 直接点“提交”
3. 看 `answer`
4. 看 `citations`
5. 看 `retrieved_chunks`
6. 看 `debug_info`

## 最小验证流程

1. 启动服务
2. 执行：

```bash
python scripts/run_rag_eval.py
```

3. 打开：

- [http://127.0.0.1:8000/rag-debug](http://127.0.0.1:8000/rag-debug)

4. 使用默认 query：

- `配置变更异常后怎么回滚`

5. 重点看：

- answer 是否围绕回滚、发布、异常展开
- citations 是否来自正确文档
- retrieved chunks 是否落在正确 section
- debug info 能否看出问题出在 keyword/vector/final 哪一层

## 常见问题说明

`API Key 不对怎么办`

- 默认值是 `change-me`
- 如果你改了 [`config.yaml`](/Users/sheldonzhao/Desktop/github/findInteresting/WikiRag/config.yaml) 里的 `app.api_key`，页面里也要改成同样值

`没有返回 chunk 怎么办`

- 先确认是否已经导入 source 并执行 normalize
- 或者直接先跑 `python scripts/run_rag_eval.py`

`没有 citations 怎么办`

- 通常说明没有命中足够相关的 chunk
- 先看 Debug 区的 `keyword_hits` 和 `vector_hits`

`embedding 失败怎么看`

- 看服务日志里 `embedding_chunk` / `embedding_batch`
- 或查 SQLite 里的 `chunk_records.embedding_status` 和 `error_message`

`session_id 有什么作用`

- 用于承接前几轮 query 的上下文
- 留空会自动创建
- 同一个 `session_id` 连续查询时，系统会把最近几轮 query 拼接进 `query_rewrite`

## 示例响应

```json
{
  "doc_id": "6f96f8f7-5b37-444f-9be2-7a806d4f4a6d",
  "title": "内部 skill 接入与仓库扫描说明",
  "doc_type": "内部研发协作知识库",
  "knowledge_domain": "内部研发协作知识库",
  "applicable_mode": "研发协作",
  "product_line": ["平台"],
  "roles": ["研发"],
  "owner": "平台研发组",
  "keywords": ["skill", "仓库扫描", "配置项", "工具链"],
  "summary": "适用于内部研发协作。内容包含仓库扫描、skill 接入、联调步骤、常见失败日志、配置变更说明。",
  "markdown_content": "# 内部 skill 接入与仓库扫描说明\n..."
}
```

## 说明

- Markdown 模板固定，缺失信息统一填 `待补充`
- 图片与示意章节始终保留，缺图时填 `待补充`
- AI 是增强，不可用时自动降级到规则模式
- Huawei Wiki 地址仍使用：
  - 搜索：`https://wiki.huawei.com/devops-knowledge-management/api/search/wiki`
  - 详情：`https://wiki.huawei.com/devops-knowledge-management/api/getWiki`
- Knowledge 文档创建或重新规范化后，会自动：
  - 切分 chunk
  - 生成 embedding
  - 进入 hybrid retrieval 可检索状态
