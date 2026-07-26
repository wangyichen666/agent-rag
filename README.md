# agent-rag

企业知识库 RAG 问答系统。三层架构：

| 仓库 | 职责 | 技术栈 |
|---|---|---|
| `agent-rag-front` | 前端（对话 / 知识库管理） | React 18 + TS + Vite + AntD |
| `agent-rag-java` | 业务层（认证 / 知识库 / 会话 / SSE 转发） | Spring Boot 3 + MyBatis-Plus + MySQL + MinIO |
| `agent-rag-python` | AI 层（解析 / 切分 / 检索 / 生成） | FastAPI + BGE-M3 + Milvus |

## 文档

`doc/` 目录下有完整设计文档：总体架构、RAG 核心功能详解、接口契约、存储设计、部署路线图、开发任务清单。

## 快速启动

### 方式一：Docker Compose（完整环境）

```bash
export LLM_API_KEY=sk-xxxx     # DeepSeek 或其他 OpenAI 兼容服务
docker compose up -d --build
# 前端 http://localhost    默认账号 admin / admin123
```

### 方式二：本地开发（逐个起）

```bash
# 1. 基础设施：MySQL / MinIO / Milvus（可用 compose 只起中间件）
docker compose up -d mysql minio etcd milvus

# 2. Python AI 层（无模型联通性调试：RAG_VECTOR_STORE=memory RAG_EMBEDDING_ENABLED=false）
cd agent-rag-python && python -m app.main

# 3. Java 业务层
cd agent-rag-java && mvn spring-boot:run

# 4. 前端
cd agent-rag-front && npm install && npm run dev   # http://localhost:5173
```

## 端到端验证流程

1. 登录 → 「知识库管理」新建知识库 → 上传一份 PDF/Word/Markdown
2. 等状态变为「已完成」（自动轮询刷新）
3. 回「对话」页勾选知识库 → 新会话 → 提问
4. 观察流式输出与答案下方的引用来源标签
