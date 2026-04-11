# WikiRag 傻瓜上手说明

这份文档面向第一次接触项目的人。按步骤执行，不需要先懂实现细节。

## 第 1 步：进入项目目录

```bash
cd /Users/sheldonzhao/Desktop/github/findInteresting/WikiRag
```

## 第 2 步：创建虚拟环境

```bash
python3 -m venv .venv
source .venv/bin/activate
```

## 第 3 步：安装依赖

```bash
pip install -r requirements.txt
```

## 第 4 步：启动服务

```bash
uvicorn app.main:app --reload
```

启动后可以直接打开：

- 调试页面：http://127.0.0.1:8000/rag-debug
- Swagger 页面：http://127.0.0.1:8000/docs
- 健康检查：http://127.0.0.1:8000/api/health

## 第 5 步：准备第一条数据

你至少需要先准备一条知识数据，系统才能检索。

最简单的方式是先手工导入一条 source，然后执行 normalize。

## 第 6 步：打开调试页

打开：

http://127.0.0.1:8000/rag-debug

页面默认已经填好测试参数。最简单的做法是直接点“提交”。

## 第 7 步：看哪里

### 回答展示区

看：

- `answer`
- `status`
- `latency`
- `session_id`

### 引用展示区

看：

- 命中了哪篇文档
- 来自哪个 section
- chunk 摘要是不是对题

### 检索片段展示区

看：

- chunk_id
- score
- section_title
- content 摘要

### Debug 信息区

这是最重要的调试区域。

如果结果不对，就看：

- `keyword_hits`
- `vector_hits`
- `final_hits`
- `query_rewrite`

## 第 8 步：导入一条数据

先导入 source：

```bash
curl -X POST "http://127.0.0.1:8000/api/source/import" \
  -H "Content-Type: application/json" \
  -H "X-API-Key: change-me" \
  -d '{
    "source_title":"配置变更发布与回滚规则",
    "source_type":"manual",
    "source_url":"https://wiki.huawei.com/domains/156/wiki/4198/WIKI2026040410674038",
    "raw_content":"配置项变更前需要确认审批、灰度范围、生效范围和权限要求。发布后如果出现异常，应按回滚规则恢复。",
    "owner":"治理组",
    "tags":["配置","回滚","治理"]
  }'
```

再执行 normalize：

```bash
curl -X POST "http://127.0.0.1:8000/api/knowledge/normalize" \
  -H "Content-Type: application/json" \
  -H "X-API-Key: change-me" \
  -d '{
    "source_id":"替换成刚才返回的 source_id",
    "use_ai":false
  }'
```

normalize 后系统会自动：

- 切分 chunk
- 生成 embedding
- 准备好 hybrid retrieval

## 第 9 步：如果你已经有 wiki

先搜 wiki：

```bash
curl -X POST "http://127.0.0.1:8000/api/wiki/search" \
  -H "Content-Type: application/json" \
  -H "X-API-Key: change-me" \
  -d '{"search_query":"配置回滚","page":1,"page_size":10}'
```

从结果里拿到：

- `wiki_sn`
- `domain_id`
- `kanban_id`

再导入 source。

## 第 10 步：常见问题

### API Key 不对怎么办

默认就是：

`change-me`

如果你改了 `config.yaml`，页面里也要用同样值。

### 为什么没有结果

一般是因为数据库里还没有知识数据，或者只导入了 source 但还没 normalize。

先确认：

- 已成功导入一条 source
- 已执行 `/api/knowledge/normalize`
- 已生成 knowledge 和 chunk

### 为什么没有 citations

说明没有命中有效 chunk。

先看 Debug 区：

- `keyword_hits`
- `vector_hits`
- `final_hits`

### session_id 是做什么的

它用来承接前几轮问题。

如果你连续问：

1. 任务失败后先看什么
2. 那如果还是失败呢

只要带同一个 `session_id`，系统就会把上文一起考虑。

## 补充说明

- `scripts/run_rag_eval.py` 是可选验证脚本，不是启动项，也不是必经步骤
- 如果你只是想使用系统本身，优先走“导入 source -> normalize -> 查询”这条主链
