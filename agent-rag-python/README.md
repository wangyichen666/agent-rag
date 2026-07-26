# agent-rag-python

RAG 系统的 AI 能力层（FastAPI）。负责文档解析、切分、Embedding、混合检索、Rerank、Prompt 组装与 LLM 流式生成。业务数据不归这里管（那是 agent-rag-java 的事）。

## 快速开始

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
# 需要真实模型时再装（体积大）：
# pip install torch FlagEmbedding

cp .env.example .env   # 按需修改
python -m app.main
```

无模型联通性调试（不下载任何模型）：

```bash
RAG_VECTOR_STORE=memory RAG_EMBEDDING_ENABLED=false RAG_RERANKER_ENABLED=false python -m app.main
```

## 接口（均需 Header `X-Internal-Token`）

| 接口 | 说明 |
|---|---|
| `POST /v1/chat/completions` | 流式问答（SSE：meta / token / done / error） |
| `POST /v1/retrieve` | 纯检索（召回调试） |
| `POST /v1/ingest` | 文档解析入库（异步，202） |
| `GET /v1/ingest/status/{task_id}` | 入库任务状态 |
| `POST /v1/documents/delete` | 删除文档向量 |
| `POST /v1/kb/create` / `delete` | 知识库向量空间管理 |
| `GET /healthz` | 组件健康检查（无需 token） |

契约细节见 `../doc/03-服务接口设计.md`。

## 目录结构

```
app/
├── api/          # FastAPI 路由 + 依赖容器
├── core/         # 配置 / 日志 / 内部鉴权
├── schemas/      # API 契约（与 Java 对齐）
├── rag/          # parsers / chunkers / embedder / vector_store / retriever / reranker / generator
└── services/     # chat / ingest 编排
```

## 关键设计

- 向量库抽象：`RAG_VECTOR_STORE=milvus|memory`，memory 模式本地零依赖联调
- 模型懒加载：不调用不加载，健康检查会触发加载并报告状态
- 降级链：稀疏检索失败 → 纯稠密；rerank 失败 → RRF 顺序；改写失败 → 原 query
- 拒答：rerank 归一化分数全部低于阈值（默认 0.35）时不调 LLM，直接固定话术
