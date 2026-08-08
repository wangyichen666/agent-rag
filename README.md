# agent-rag

企业知识库 RAG 问答系统。三层架构：前端（React）→ Java 业务层（Spring Boot）→ Python AI 层（FastAPI），基础设施使用 MySQL + MinIO + Milvus + Neo4j（知识图谱）。

## 架构总览

```
┌─────────────────────────────────────────────────┐
│                agent-rag-front                  │
│          React 18 + TypeScript + Vite           │
│       Ant Design 5 · Zustand · SSE 流式        │
│   对话 / 知识库管理 / 会话历史 / 全链路追溯       │
└────────────────────┬────────────────────────────┘
                     │ HTTPS / SSE (JWT)
┌────────────────────▼────────────────────────────┐
│               agent-rag-java                    │
│      Spring Boot 3.3 · JDK 17 · MyBatis-Plus   │
│   用户认证 · 知识库 CRUD · 会话管理 · SSE 透传   │
│         MinIO 文件存储 · MySQL 业务数据          │
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
| **前端** | React + Vite + AntD | 交互渲染、SSE 流式接收、Markdown/引用展示、全链路追溯 | 不感知模型、不直连 Python |
| **Java** | Spring Boot 3.3 | 用户/权限、知识库 CRUD、会话落库、文件存取、SSE 透传 | 不做向量/模型计算 |
| **Python** | FastAPI | 解析、切分、Embedding、检索、Rerank、Prompt、调 LLM | 不碰用户体系 |

> AI 层可随时重写替换，Java 层无感；业务侧改需求也不会牵动 AI 代码。

## 技术栈

### 前端（agent-rag-front）

| 类别 | 选型 |
|---|---|
| 框架 | React 18 + TypeScript + Vite |
| UI 组件库 | Ant Design 5 |
| 状态管理 | Zustand |
| 流式接收 | fetch + ReadableStream（手写 SSE 解析，支持 POST + 自定义 Header） |
| Markdown | react-markdown + remark-gfm + rehype-highlight |

### Java 业务层（agent-rag-java）

| 类别 | 选型 |
|---|---|
| 框架 | Spring Boot 3.3 + JDK 17 |
| ORM | MyBatis-Plus |
| 鉴权 | jjwt（JWT HMAC-SHA512） |
| 对象存储 | MinIO Client |
| 数据库 | MySQL 8.0 |

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

### 基础设施

| 组件 | 用途 | 端口 |
|---|---|---|
| MySQL 8.0 | 业务数据：用户、知识库、会话、消息 | 3306 |
| MinIO | 文档对象存储 | 9000 / 9001 |
| Milvus | 稠密向量索引（1024 维 HNSW） | 19530 |
| etcd | Milvus 元数据 | 2379 |
| Neo4j 5.26 | 知识图谱：实体/关系/出处块 | 7474 / 7687 |

## RAG 检索流程

```
用户提问
  ↓
Query 改写（多轮指代消解）
  ↓
Embedding 向量化（SiliconFlow Qwen3-Embedding）
  ↓
Milvus 稠密检索（dense Top-20）
  ↓
RRF 融合（dense + sparse + graph）
  ↓
Rerank 精排（SiliconFlow Qwen3-Reranker）
  ↓
阈值过滤（score ≥ 0.35）
  ↓
组装 Prompt（参考资料 + System Prompt + User Message）
  ↓
DeepSeek 流式生成 → 前端 SSE 逐 token 展示（带引用来源）
```

## 项目结构

```
agent-rag/
├── agent-rag-front/          # 前端
│   └── src/
│       ├── pages/
│       │   ├── ChatPage.tsx      # 对话页
│       │   ├── KbPage.tsx        # 知识库管理
│       │   ├── TracePage.tsx     # RAG 全链路追溯
│       │   └── StoragePage.tsx   # 向量库存储格式
│       ├── api/
│       │   ├── client.ts         # HTTP 封装（JWT 注入）
│       │   └── sse.ts            # SSE 流式客户端
│       └── stores/auth.ts        # 认证状态
│
├── agent-rag-java/           # Java 业务层
│   └── src/main/java/com/example/rag/
│       ├── module/auth/          # 认证（JWT）
│       ├── module/kb/            # 知识库 & 文档管理
│       ├── module/chat/          # 会话 & 消息
│       ├── infra/ai/             # Python 服务客户端
│       └── infra/storage/        # MinIO 封装
│
├── agent-rag-python/         # Python AI 层
│   └── app/
│       ├── api/
│       │   ├── routes_chat.py    # 问答 API（SSE）
│       │   ├── routes_ingest.py  # 文档入库 API
│       │   ├── routes_debug.py   # 追溯 API
│       │   └── routes_graph.py   # 图谱数据 / 统计 API
│       ├── rag/
│       │   ├── parsers.py        # 文档解析
│       │   ├── chunkers.py       # 智能切分
│       │   ├── embedder.py       # Embedding
│       │   ├── reranker.py       # Rerank
│       │   ├── retriever.py      # 混合检索 + RRF
│       │   ├── extractor.py      # LLM 实体/关系抽取
│       │   ├── graph_store.py    # Neo4j 图存储
│       │   ├── graph_retriever.py# 图谱子图检索
│       │   ├── generator.py      # Prompt + LLM
│       │   └── vector_store.py   # Milvus 封装
│       └── services/
│           ├── chat_service.py   # 问答编排
│           └── ingest_service.py # 入库编排
│
├── doc/                      # 设计文档
├── docker-compose.yml        # 一键启动
└── .env                      # API Key 等敏感配置（不入 git）
```

## 快速启动

### 方式一：Docker Compose（完整环境）

```bash
export LLM_API_KEY=sk-your-deepseek-key
export SILICONFLOW_API_KEY=sk-your-siliconflow-key
export NEO4J_PASSWORD=neo4jrag   # 可选，默认 neo4jrag
docker compose up -d --build
# 前端 http://localhost    免登录，直接进入对话页
# Neo4j Browser http://localhost:7474（账号 neo4j）
```

> 当前为**免登录模式**：后端不校验 JWT，所有业务接口使用管理员账号（id=1）；
> 前端无登录页。如需恢复登录，改回 JWT 过滤器与登录页即可。

### 方式二：本地开发

```bash
# 1. 启动中间件
docker compose up -d mysql minio etcd milvus neo4j

# 2. Python AI 层
cd agent-rag-python
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
# 编辑 .env，填写 RAG_SILICONFLOW_API_KEY 和 RAG_LLM_API_KEY
python -m app.main    # http://localhost:8000

# 3. Java 业务层
cd agent-rag-java
mvn spring-boot:run   # http://localhost:8080

# 4. 前端
cd agent-rag-front
npm install && npm run dev   # http://localhost:5173
```

### 配置说明

在 `agent-rag-python/.env` 中：

```bash
# SiliconFlow（Embedding + Rerank）
RAG_SILICONFLOW_API_KEY=sk-your-key

# LLM（DeepSeek，或其他 OpenAI 兼容 API）
RAG_LLM_API_KEY=sk-your-key
RAG_LLM_BASE_URL=https://api.deepseek.com
RAG_LLM_MODEL=deepseek-chat

# 知识图谱（Neo4j；RAG_GRAPH_ENABLED=false 即退回纯向量 RAG）
RAG_GRAPH_ENABLED=true
RAG_NEO4J_URI=bolt://127.0.0.1:7687
RAG_NEO4J_USER=neo4j
RAG_NEO4J_PASSWORD=neo4jrag
RAG_GRAPH_MAX_HOPS=2
RAG_GRAPH_TOP_K=8
```

## 页面功能

| 页面 | 路由 | 功能 |
|---|---|---|
| 对话 | `/` | 选择知识库 → 创建会话 → 流式问答（引用来源 + Markdown 渲染） |
| 知识库管理 | `/kb` | 创建/删除知识库、上传文档、查看解析状态 |
| 全链路追溯 | `/trace` | 选择知识库输入 query → 追溯 Embedding → 向量检索 → 图谱检索（实体/命中块）→ RRF 融合 → Rerank → LLM Prompt 全流程中间数据 |
| 向量库 | `/storage` | 下拉选择文档 → 查看在 Milvus 中的存储格式（chunk 结构、metadata、向量维度） |
| 知识图谱 | `/graph` | 实体-关系图谱可视化：缩放/平移/拖拽、点击查看详情、关键词高亮、规模统计；入库自动建图 |

> 文档入库后 Python 层自动用 LLM 抽取实体/关系写入 Neo4j，问答时图谱通道与向量通道做 RRF 融合
> （检索调试新增 `graph_hits`）。设计详见 [doc/10-知识图谱设计.md](doc/10-知识图谱设计.md)。
