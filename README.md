# agent-rag

企业知识库 RAG 问答系统：上传文档后自动建立向量索引与知识图谱，支持带引用溯源的多轮对话。

三层架构：**React 前端 → Java 业务层 → Python AI 层**；基础设施：**MySQL + MinIO + Milvus + Neo4j**。

当前为**免登录模式**：后端不校验任何 Token，打开页面即用；文档、会话等数据统一归属内置管理员账号（id=1）。

## 功能一览

| 功能 | 说明 |
|---|---|
| 对话 | 勾选知识库 → 新建会话 → 流式问答（SSE 逐 token），回答带 `[1][2]` 引用来源，可一键跳转查看检索链路 |
| 知识库管理 | 创建/删除知识库，上传 PDF / Word / Markdown / TXT，实时查看解析状态与 chunk 数 |
| 全链路追溯 | 输入任意 query，或**点选历史 Query**，查看 Embedding → 向量召回 → 图谱检索 → RRF 融合 → Rerank → LLM Prompt 每个阶段的中间数据 |
| 知识图谱 | 入库时自动用 LLM 抽取实体/关系写入 Neo4j；页面按实体类型分列可视化，支持缩放/拖拽/详情下钻；问答时图谱通道与向量通道融合 |
| 向量库 | 查看文档在 Milvus 中的存储格式（chunk 结构、metadata、向量维度） |
| 改写记录 | 查看多轮对话的 Query 指代消解改写前后对比 |
| 对话记录 | 查看历史会话与消息 |

## 架构总览

```text
┌─────────────────────────────────────────────────┐
│                agent-rag-front                  │
│          React 18 + TypeScript + Vite           │
│       Ant Design 5 · Zustand · SSE 流式        │
│  对话 / 知识库 / 追溯 / 图谱 / 向量库 / 记录      │
└────────────────────┬────────────────────────────┘
                     │ REST + SSE（免登录）
┌────────────────────▼────────────────────────────┐
│               agent-rag-java                    │
│      Spring Boot 3.3 · JDK 17 · MyBatis-Plus   │
│  知识库 CRUD · 文档/文件管理 · 会话与消息落库     │
│         MinIO 文件存储 · SSE 透传                │
└────────────────────┬────────────────────────────┘
                     │ HTTP REST (Internal Token)
┌────────────────────▼────────────────────────────┐
│              agent-rag-python                   │
│            FastAPI · httpx · numpy              │
│   文档解析 → 切分 → Embedding → 检索 → Rerank    │
│          Prompt 编排 → LLM 流式生成              │
│     图谱：实体抽取 → Neo4j → 图检索融合           │
└───────┬───────────────────────────┬────────────┘
        │                           │
┌───────▼──────┐  ┌──────────┐  ┌──▼───────────┐
│    Milvus    │  │ DeepSeek │  │ SiliconFlow  │
│  向量索引    │  │  LLM     │  │Embed/Rerank  │
└──────────────┘  └──────────┘  └──────────────┘
        ┌───────────────┐
        │     Neo4j     │  知识图谱（实体-关系-出处块）
        └───────────────┘
```

### 三层职责边界

| 层 | 框架 | 职责 | 不做什么 |
|---|---|---|---|
| **前端** | React + Vite + AntD | 交互渲染、SSE 流式接收、Markdown/引用展示、图谱可视化、全链路追溯 | 不感知模型、不直连 Python |
| **Java** | Spring Boot 3.3 | 知识库/文档/会话管理、MinIO 存取、SSE 透传与落库 | 不做向量/图谱/模型计算 |
| **Python** | FastAPI | 解析、切分、Embedding、向量检索、图谱构建与检索、Rerank、Prompt、调 LLM | 不碰业务 CRUD |

> AI 层可随时重写替换，Java 层无感；业务侧改需求也不会牵动 AI 代码。

## 两条核心链路

### 1. 离线文档加工（入库）

```text
前端上传
  → Java：存 MinIO + 数据库记录（pending）
  → Python 拉取文件（预签名 URL）
  → 解析：PyMuPDF（PDF）/ python-docx（Word）/ Markdown 直读
  → 切分：结构感知（保留 title_path/页码）+ 递归字符兜底
  → Embedding：SiliconFlow Qwen3-Embedding（1024 维）
  → Milvus 向量入库（先删旧版本，保证幂等）
  → 图谱构建：LLM 批量抽取三元组（每批 6 块）→ Neo4j 写实体/关系/出处块
  → 回调 Java：标记 parse_status=success + chunk 数
```

- 图谱构建失败只告警降级，**不影响向量入库**；`RAG_GRAPH_ENABLED=false` 即退回纯向量 RAG。
- 删除文档/知识库会同步清理 Milvus 向量与 Neo4j 子图。

### 2. 在线问答（query → 答案）

```text
用户提问
  → Java：会话校验（免登录）→ 透传 Python
  → Query 改写：多轮指代消解（有历史才调用，失败用原文）
  → 并行检索：
      向量路：Embedding → Milvus 稠密 Top-20
      图谱路：实体抽取 → Neo4j 精确匹配（文本包含兜底）→ 1~2 跳扩展
  → RRF 融合（dense + graph，k=60）
  → Rerank 精排：SiliconFlow Qwen3-Reranker 取 Top-5（失败按 RRF 降级）
  → 阈值过滤：最高分 < 0.35 则拒答
  → 上下文裁剪：按分数装进 2000 token 预算
  → 组装 Prompt：System + 编号参考资料 + 历史（最近 5 轮）+ 用户问题
  → DeepSeek 流式生成 → SSE 逐 token 返回（meta/token/done，带引用）
  → Java 落库（用户消息 + 回答 + trace_id + 引用）
```

模型真正看到的 Prompt 结构：

```text
System: 你是一个严谨的企业知识库助手。基于「参考资料」回答用户问题。
要求：
  1. 只依据参考资料回答，资料中没有的内容，明确说"根据现有资料无法回答"，不要编造。
  2. 回答中引用资料时，在对应语句末尾标注引用编号，格式 [1] [2]。
  3. 回答使用简体中文，结构清晰，必要时使用列表。
  4. 不要复述参考资料全文，用自己的话归纳。

【参考资料】
[1]（来源：08 OpenClaw 模型选择与切换.md · 第2页 · 模型选择）
    <候选块内容>
[2]（来源：xxx.md · 第5页 · 安装）
    <候选块内容>

【历史对话（最近 5 轮）】
【用户问题（原文）】
```

## 技术栈

### 前端（agent-rag-front）

| 类别 | 选型 |
|---|---|
| 框架 | React 18 + TypeScript + Vite |
| UI 组件库 | Ant Design 5 |
| 状态管理 | Zustand |
| 流式接收 | fetch + ReadableStream（手写 SSE 解析，done/error 自动收尾） |
| Markdown | react-markdown + remark-gfm + rehype-highlight |
| 图谱可视化 | 自研 SVG 布局（按实体类型分列 + 标签碰撞检测），零额外依赖 |

### Java 业务层（agent-rag-java）

| 类别 | 选型 |
|---|---|
| 框架 | Spring Boot 3.3 + JDK 17 |
| ORM | MyBatis-Plus |
| 对象存储 | MinIO Client |
| 数据库 | MySQL 8.0 |
| 鉴权 | 免登录（默认管理员账号；历史 JWT 代码已移除，可参照 git 历史恢复） |

### Python AI 层（agent-rag-python）

| 类别 | 选型 |
|---|---|
| 框架 | FastAPI + Uvicorn |
| HTTP 客户端 | httpx（异步 + 流式） |
| 文档解析 | PyMuPDF（PDF）+ python-docx（Word） |
| Embedding | Qwen3-Embedding-0.6B（SiliconFlow API，1024 维） |
| Reranker | Qwen3-Reranker-0.6B（SiliconFlow API） |
| LLM | DeepSeek（OpenAI 兼容协议，可替换） |
| 向量库 | Milvus 2.4（HNSW 索引，IP 度量） |
| 图数据库 | Neo4j 5.26（neo4j 官方 Python 驱动） |

### 基础设施

| 组件 | 用途 | 端口 |
|---|---|---|
| MySQL 8.0 | 业务数据：知识库、文档、会话、消息 | 3306 |
| MinIO | 文档对象存储 | 9000 / 9001 |
| Milvus | 稠密向量索引（1024 维 HNSW） | 19530 |
| etcd | Milvus 元数据 | 2379 |
| Neo4j 5.26 | 知识图谱：实体/关系/出处块 | 7474 / 7687 |

## 项目结构

```text
agent-rag/
├── agent-rag-front/          # 前端
│   └── src/
│       ├── pages/
│       │   ├── ChatPage.tsx      # 对话页（SSE 流式 + 引用）
│       │   ├── KbPage.tsx        # 知识库管理
│       │   ├── TracePage.tsx     # RAG 全链路追溯（含图谱阶段 + 历史 Query）
│       │   ├── GraphPage.tsx     # 知识图谱可视化
│       │   ├── StoragePage.tsx   # 向量库存储格式
│       │   ├── RewritePage.tsx   # 改写记录
│       │   └── HistoryPage.tsx   # 对话记录
│       ├── api/
│       │   ├── client.ts         # HTTP 封装（统一错误处理）
│       │   └── sse.ts            # SSE 流式客户端
│       └── types.ts              # 与 Java 契约对齐的类型
│
├── agent-rag-java/           # Java 业务层
│   └── src/main/java/com/example/rag/
│       ├── common/               # 统一返回体 / 免登录默认账号
│       ├── config/               # Security（放行）、管理员初始化
│       ├── module/kb/            # 知识库、文档、图谱代理接口
│       ├── module/chat/          # 会话、消息、SSE 透传、历史/改写查询
│       ├── infra/ai/             # Python 服务客户端（REST + SSE）
│       └── infra/storage/        # MinIO 封装
│
├── agent-rag-python/         # Python AI 层
│   └── app/
│       ├── api/
│       │   ├── routes_chat.py    # 问答 API（SSE）
│       │   ├── routes_ingest.py  # 文档入库 API
│       │   ├── routes_debug.py   # 全链路追溯 API（含图谱阶段）
│       │   ├── routes_graph.py   # 图谱数据 / 统计 API
│       │   └── routes_misc.py    # 健康检查
│       ├── rag/
│       │   ├── parsers.py        # 文档解析
│       │   ├── chunkers.py       # 智能切分
│       │   ├── embedder.py       # Embedding
│       │   ├── reranker.py       # Rerank
│       │   ├── retriever.py      # 混合检索 + RRF + 图谱融合
│       │   ├── extractor.py      # LLM 实体/关系抽取
│       │   ├── graph_store.py    # Neo4j 图存储
│       │   ├── graph_retriever.py# 图谱子图检索
│       │   ├── generator.py      # Prompt 组装 + LLM 客户端
│       │   └── vector_store.py   # Milvus 封装
│       └── services/
│           ├── chat_service.py   # 问答编排（改写→并行检索→融合→生成）
│           └── ingest_service.py # 入库编排（解析→切分→向量→建图）
│
├── doc/                      # 设计文档（架构/RAG/接口/图谱等）
├── docker-compose.yml        # 一键启动（8 个服务）
├── README.md
└── .env                      # API Key 等敏感配置（不入 git）
```

## 快速启动

### 方式一：Docker Compose（完整环境）

```bash
export LLM_API_KEY=sk-your-deepseek-key
export SILICONFLOW_API_KEY=sk-your-siliconflow-key
export NEO4J_PASSWORD=neo4jrag    # 可选，默认 neo4jrag
docker compose up -d --build

# 前端 http://localhost（免登录，直接进入对话页）
# Neo4j Browser http://localhost:7474（neo4j / neo4jrag）
```

### 方式二：本地开发

```bash
# 1. 启动基础设施（Docker）
docker compose up -d mysql minio etcd milvus neo4j

# 2. Python AI 层（:8000）
cd agent-rag-python
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env && vim .env   # 填写 RAG_SILICONFLOW_API_KEY / RAG_LLM_API_KEY / RAG_NEO4J_PASSWORD
python -m app.main

# 3. Java 业务层（:8080）
cd agent-rag-java
mvn spring-boot:run

# 4. 前端（:5173）
cd agent-rag-front
npm install && npm run dev
```

> 本地开发时 `agent-rag-python/.env` 的 `RAG_NEO4J_PASSWORD` 必须与 Neo4j 实际密码一致
> （Docker Compose 默认 `neo4jrag`）。

## 配置说明（agent-rag-python/.env）

```bash
# ---- 服务 ----
RAG_INTERNAL_TOKEN=dev-internal-token

# ---- 向量库 ----
RAG_VECTOR_STORE=milvus
RAG_MILVUS_URI=http://127.0.0.1:19530

# ---- SiliconFlow（Embedding + Rerank）----
RAG_SILICONFLOW_API_KEY=sk-your-key
RAG_SILICONFLOW_BASE_URL=https://api.siliconflow.cn/v1
RAG_EMBEDDING_MODEL_NAME=Qwen/Qwen3-Embedding-0.6B
RAG_RERANKER_MODEL_NAME=Qwen/Qwen3-Reranker-0.6B
RAG_RERANKER_TOP_N=5

# ---- LLM（DeepSeek 或其他 OpenAI 兼容 API）----
RAG_LLM_BASE_URL=https://api.deepseek.com
RAG_LLM_API_KEY=sk-your-key
RAG_LLM_MODEL=deepseek-chat

# ---- 知识图谱（Neo4j；RAG_GRAPH_ENABLED=false 即退回纯向量 RAG）----
RAG_GRAPH_ENABLED=true
RAG_NEO4J_URI=bolt://127.0.0.1:7687
RAG_NEO4J_USER=neo4j
RAG_NEO4J_PASSWORD=neo4jrag
RAG_GRAPH_EXTRACT_BATCH_SIZE=6   # 每次 LLM 抽取的 chunk 数（控制 token 成本）
RAG_GRAPH_MAX_HOPS=2             # 图检索扩展跳数
RAG_GRAPH_TOP_K=8                # 图通道返回候选数
```

## 页面路由

| 页面 | 路由 | 功能 |
|---|---|---|
| 对话 | `/` | 选知识库 → 新建会话 → 流式问答（引用 + Markdown） |
| 知识库管理 | `/kb` | 创建/删除知识库、上传文档、查看解析状态 |
| 全链路追溯 | `/trace` | 手动输入或点选历史 Query → Embedding → 向量召回 → 图谱检索 → RRF → Rerank → Prompt |
| 知识图谱 | `/graph` | 按类型分列的实体关系图谱：缩放/拖拽/详情下钻/关键词高亮/规模统计 |
| 向量库 | `/storage` | 查看文档在 Milvus 中的存储格式 |
| 改写记录 | `/rewrites` | Query 改写前后对比 |
| 对话记录 | `/conversations` | 历史会话与消息 |

## 测试

```bash
# Python 单元测试（不依赖 Neo4j / 外部 LLM）
cd agent-rag-python && .venv/bin/python -m pytest tests/ -q

# 前端类型检查 + 构建
cd agent-rag-front && npm run build

# Java 编译
cd agent-rag-java && mvn -q compile -DskipTests
```

## 常见问题

**知识图谱页没有数据？**

- 确认知识库下拉选中的是上传文档的那个知识库（页面会自动优先选中已有图谱数据的库）；
- 图谱在**文档入库时**构建，上传后需等待解析完成再刷新；
- 图谱功能上线**之前**入库的旧文档没有图谱，重新上传即可（重建接口待实现）；
- 检查 Python 健康检查中 `knowledge_graph` 组件是否为 `ok`（`curl http://localhost:8000/healthz`）。

**对话流结束后输入框一直不可用？**

- 该问题已修复：前端收到 `done`/`error` 事件即主动结束 SSE 读取，不再依赖服务端关闭连接。
- 若仍复现，请确认前端代码为最新并刷新页面（Vite 缓存）。

**Neo4j 连不上？**

- 确认容器健康：`docker compose ps neo4j`；
- 确认 `agent-rag-python/.env` 的 `RAG_NEO4J_PASSWORD` 与容器密码一致（Compose 默认 `neo4jrag`）。

## 设计文档

详见 [doc/](doc/) 目录：

- `01-总体架构与技术选型.md` / `02-RAG核心功能详解.md` / `03-服务接口设计.md`
- `04-数据库与存储设计.md` / `05-部署与开发路线图.md` / `07-RAG框架选型与自研决策.md`
- `10-知识图谱设计.md`（图谱数据模型、建图/检索链路、配置与取舍）
