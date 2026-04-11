# WikiRag webShell 验证手册

这份文档用于在 webShell 环境下验证两件事：

1. Wiki 导入能力
2. 完整 RAG 能力

适用场景：

- 明天在公司 webShell 环境下自己测试
- 不依赖本地页面也能完成验证
- 排查是“Wiki 导入问题”还是“RAG 检索问题”

默认假设：

- 服务地址：`http://127.0.0.1:8000`
- API Key：`change-me`
- 项目目录：`/Users/sheldonzhao/Desktop/github/findInteresting/WikiRag`

---

## 一、验证目标

### 1. Wiki 导入能力

要验证这条链：

`/api/wiki/search -> 选中指定 wiki -> /api/source/import -> /api/source/{source_id} -> /api/knowledge/normalize`

成功标准：

- 能搜到真实 wiki
- 能按指定 `wiki_sn` 导入
- 导入后 `source` 里能看到正文和 metadata
- 能继续生成 knowledge 文档

### 2. 完整 RAG 能力

要验证这条链：

`source -> knowledge -> chunk -> embedding -> /api/rag/query`

成功标准：

- query 有 answer
- 有 citations
- 有 retrieved_chunks
- debug 信息可解释

---

## 二、启动前准备

### 1. 进入项目目录

```bash
cd /Users/sheldonzhao/Desktop/github/findInteresting/WikiRag
```

### 2. 创建并激活虚拟环境

```bash
python3 -m venv .venv
source .venv/bin/activate
```

### 3. 安装依赖

```bash
pip install -r requirements.txt
```

### 4. 如果要验证真实 Wiki，先配置 Cookie

```bash
export HUAWEI_WIKI_COOKIE='你的真实 cookie'
```

说明：

- 如果不配 Cookie，真实 Huawei Wiki 搜索和导入大概率会失败

### 5. 启动服务

```bash
uvicorn app.main:app --reload
```

启动后优先用命令行验证：

- 健康检查：`http://127.0.0.1:8000/api/health`
- Wiki 搜索：`http://127.0.0.1:8000/api/wiki/search`
- RAG 查询：`http://127.0.0.1:8000/api/rag/query`

如果 webShell 环境支持端口映射或 web preview，再额外访问：

- 调试页：`http://127.0.0.1:8000/rag-debug`
- Swagger：`http://127.0.0.1:8000/docs`

---

## 三、先做最小保底验证

这一步的目的不是依赖演示数据，而是先确认服务和接口本身正常。

### 1. 健康检查

```bash
curl "http://127.0.0.1:8000/api/health" \
  -H "X-API-Key: change-me" \
  | tee health_result.json
```

预期返回：

```json
{"status":"ok"}
```

### 2. 建议先手工导入一条最小 source

```bash
curl -X POST "http://127.0.0.1:8000/api/source/import" \
  -H "Content-Type: application/json" \
  -H "X-API-Key: change-me" \
  -d '{
    "source_title":"最小验证文档",
    "source_type":"manual",
    "source_url":"https://wiki.huawei.com/domains/156/wiki/4198/WIKI2026040410674038",
    "raw_content":"配置项变更前需要确认审批、灰度范围、生效范围和权限要求。发布后如果出现异常，应按回滚规则恢复。",
    "owner":"待补充",
    "tags":["最小验证","配置","回滚"]
  }' | tee validation_outputs/min_source_import.json
```

再执行 normalize：

```bash
curl -X POST "http://127.0.0.1:8000/api/knowledge/normalize" \
  -H "Content-Type: application/json" \
  -H "X-API-Key: change-me" \
  -d '{
    "source_id":"替换成上一步返回的 source_id",
    "use_ai":false
  }' | tee validation_outputs/min_knowledge_normalize.json
```

如果这条最小链路都失败，不要急着测真实 Wiki，先修基础环境。

### 3. 建议在 webShell 里保存关键验证结果

建议新建一个目录保存明天的结果：

```bash
mkdir -p validation_outputs
```

后面的 curl 建议都配合 `tee` 使用，方便保留证据。

---

## 四、Wiki 导入能力详细验证步骤

这部分验证的是“真实 wiki 是否能搜、能导、能转成 knowledge”。

### Step 1：搜索 Wiki

先不要直接导，先确认搜索可用。

```bash
curl -X POST "http://127.0.0.1:8000/api/wiki/search" \
  -H "Content-Type: application/json" \
  -H "X-API-Key: change-me" \
  -d '{
    "search_query": "配置回滚",
    "page": 1,
    "page_size": 5
  }' | tee validation_outputs/wiki_search_result.json
```

重点看返回结果中是否存在：

- `sn`
- `title`
- `domain_id`
- `kanban_id`
- `url`

如果没有结果：

- 先换关键词
- 再检查 Cookie
- 再检查公司网络和权限

### Step 2：从搜索结果里挑一条 Wiki

从返回结果里选 1 到 2 条最适合验证的 wiki。

建议优先选：

- 配置变更 / 回滚类
- 运维排障类
- 内部研发协作类

你需要记录 3 个值：

- `wiki_sn`
- `domain_id`
- `kanban_id`

例如：

- `wiki_sn = WIKI2026040410674038`
- `domain_id = 156`
- `kanban_id = 4198`

### Step 3：导入指定 Wiki

把上一步拿到的值替换进去：

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
    "tags": ["wiki", "验证", "配置回滚"],
    "skip_if_exists": true,
    "overwrite_if_exists": false
  }' | tee validation_outputs/source_import_result.json
```

重点看返回里的：

- `source_id`
- `source_title`
- `source_url`
- `external_id`
- `import_status`

说明：

- `external_id` 一般就是 `wiki_sn`
- 如果重复导入且 `skip_if_exists=true`，会直接返回已有记录

### Step 4：查看 Source 详情

把 `SOURCE_ID` 替换为上一步返回值：

```bash
curl "http://127.0.0.1:8000/api/source/SOURCE_ID" \
  -H "X-API-Key: change-me" \
  | tee validation_outputs/source_detail_result.json
```

重点检查：

- `source_title`
- `source_url`
- `raw_content`
- `external_id`
- `metadata.wiki_sn`
- `metadata.domain_id`
- `metadata.kanban_id`
- `metadata.raw_html`
- `metadata.image_urls`

通过标准：

- 标题是 wiki 标题
- `raw_content` 不是空
- metadata 里保留了 wiki 相关信息

### Step 5：把 Source 转成 Knowledge

```bash
curl -X POST "http://127.0.0.1:8000/api/knowledge/normalize" \
  -H "Content-Type: application/json" \
  -H "X-API-Key: change-me" \
  -d '{
    "source_id": "SOURCE_ID",
    "use_ai": false
  }' | tee validation_outputs/knowledge_normalize_result.json
```

重点看返回：

- `doc_id`
- `title`
- `doc_type`
- `markdown_content`

这一步成功后，系统还会自动做：

- chunk 切分
- embedding

### Step 6：查看 Knowledge 详情

```bash
curl "http://127.0.0.1:8000/api/knowledge/DOC_ID" \
  -H "X-API-Key: change-me" \
  | tee validation_outputs/knowledge_detail_result.json
```

重点看：

- `doc_type`
- `summary`
- `markdown_content`

如果这里正常，说明 Wiki 导入到 Knowledge 的链已经通了。

---

## 五、完整 RAG 能力详细验证步骤

这部分验证的是“导入后的知识是否真的能被检索和回答”。

### Step 1：优先用接口直接验证

在 webShell 里，优先用 curl，而不是依赖页面。

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
  }' | tee validation_outputs/rag_query_result.json
```

重点看：

- `status`
- `latency_ms`
- `answer`
- `citations`
- `retrieved_chunks`
- `debug_info`

### Step 2：判断是否命中正确

重点检查：

- answer 是否围绕问题本身
- citations 是否来自正确文档
- retrieved_chunks 是否真的包含相关内容
- final_hits 是否使用了合理 chunk

### Step 3：测试多轮上下文

第一问：

```bash
curl -X POST "http://127.0.0.1:8000/api/rag/query" \
  -H "Content-Type: application/json" \
  -H "X-API-Key: change-me" \
  -d '{
    "query": "任务失败后先看什么",
    "top_k": 3,
    "use_rerank": true,
    "use_ai": false,
    "debug": true
  }' | tee validation_outputs/rag_session_round1.json
```

拿到返回的 `session_id`。

第二问，带同一个 `session_id`：

```bash
curl -X POST "http://127.0.0.1:8000/api/rag/query" \
  -H "Content-Type: application/json" \
  -H "X-API-Key: change-me" \
  -d '{
    "query": "那如果是变更后失败呢",
    "session_id": "替换成上一轮返回的 session_id",
    "top_k": 3,
    "use_rerank": true,
    "use_ai": false,
    "debug": true
  }' | tee validation_outputs/rag_session_round2.json
```

重点看：

- `query_rewrite`
- 最终命中的 chunks 是否与上下文相关

### Step 4：测试一个无关 query

例如：

```bash
curl -X POST "http://127.0.0.1:8000/api/rag/query" \
  -H "Content-Type: application/json" \
  -H "X-API-Key: change-me" \
  -d '{
    "query": "balaba",
    "top_k": 3,
    "use_rerank": true,
    "use_ai": false,
    "debug": true
  }' | tee validation_outputs/rag_bad_query_result.json
```

当前预期现象：

- 系统可能仍然会返回 answer
- 这是当前已知问题，不是你操作错了

这一步的价值是：

- 证明你已经发现系统缺少“拒答阈值”
- 后续优化方向明确

---

## 六、建议明天优先验证的 query

### 配置治理类

- `配置变更异常后怎么回滚`
- `发布后没生效先查什么`

### 运维排障类

- `推理服务告警怎么排查`
- `日志采集失败先看哪里`

### 研发协作类

- `skill 接入失败要检查什么`
- `联调环境改配置前要确认什么`

### FAQ / 新手类

- `权限申请后还不能访问怎么办`
- `第一次创建推理任务怎么做`

---

## 七、如果 webShell 支持页面，再怎么辅助看

如果你的 webShell 环境支持端口映射、preview 或浏览器访问本地端口，可以额外打开：

`http://127.0.0.1:8000/rag-debug`

但这不是必须项。

如果打不开页面，不影响验证结论。

### 1. 回答展示区

看：

- `status`
- `latency`
- `session_id`
- `answer`

注意：

- 当前 answer 仍偏调试风格
- 如果命中了多个相似 chunk，可能出现内容重复

### 2. 引用展示区

看：

- `doc_id`
- `source_id`
- `section_title`
- `chunk_summary`

它帮助判断：

- 回答是不是基于正确文档

### 3. 检索片段展示区

看：

- `chunk_id`
- `score`
- `section_title`
- `content`

它帮助判断：

- 最终回答吃了哪些 chunk

### 4. Debug 信息区

重点看：

- `query_rewrite`
- `keyword_hits`
- `vector_hits`
- `final_hits`

它帮助判断：

- 是关键词召回错了
- 还是向量召回错了
- 还是融合排序有问题

---

## 八、最常见问题

### 1. `/api/wiki/search` 没结果

优先检查：

- `HUAWEI_WIKI_COOKIE` 是否配置
- Cookie 是否过期
- 搜索词是否太窄
- 网络和权限是否正常

### 2. `/api/source/import` 失败

优先检查：

- `wiki_sn`
- `domain_id`
- `kanban_id`

是否和搜索结果一致

### 3. 导入成功但 `raw_content` 为空

可能原因：

- 详情接口没有返回有效正文
- 该 wiki 结构过于特殊

### 4. RAG 没命中

可能原因：

- query 太偏
- doc_type 过滤错了
- 文档质量差
- chunk 和 retrieval 还需要调优

### 5. 无关 query 也有答案

这是当前已知问题。

原因：

- 还没有做“低分拒答”
- 只要有 top_k 命中，就会拼接 answer

---

## 九、明天建议保留的验证证据

建议至少保留这些文件：

1. `validation_outputs/wiki_search_result.json`
2. `validation_outputs/source_import_result.json`
3. `validation_outputs/source_detail_result.json`
4. `validation_outputs/knowledge_normalize_result.json`
5. `validation_outputs/rag_query_result.json`
6. `validation_outputs/rag_session_round1.json`
7. `validation_outputs/rag_session_round2.json`
8. `validation_outputs/rag_bad_query_result.json`

如果能开页面，再额外截图：

- 正常命中页面截图
- 无关 query 页面截图

---

## 十、最小结论模板

如果明天验证通过，你可以这样总结：

> 已完成 Huawei Wiki 搜索、指定 wiki 导入、source 入库、knowledge 规范化、chunk 与 embedding 自动生成，以及基于该知识的 RAG 查询闭环验证。当前系统已具备可演示、可调试、可继续优化的最小闭环能力。

如果明天发现问题，也可以这样总结：

> 已完成 Wiki 接口联通与基础导入验证，RAG 链路可跑通，但当前仍存在弱命中误答、重复 chunk 进入 answer、拒答阈值缺失等问题，下一步应优先优化 retrieval gating 和 answer 去重逻辑。
