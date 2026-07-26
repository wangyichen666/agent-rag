# Agent-RAG 系统设计文档

基于「React 前端 + Java 业务层 + Python AI 层」三层架构的检索增强生成（RAG）系统设计方案。

## 文档索引

| 文档 | 内容 | 读者 |
|---|---|---|
| [01-总体架构与技术选型](./01-总体架构与技术选型.md) | 系统分层、技术栈选型与理由、服务间通信方案、仓库结构 | 全员 |
| [02-RAG核心功能详解](./02-RAG核心功能详解.md) | **重点文档**：文档解析、切分、Embedding、向量索引、混合检索、Rerank、Prompt 组装、流式生成、多轮对话、质量评估、性能工程 | AI 层开发、算法 |
| [03-服务接口设计](./03-服务接口设计.md) | Java ↔ Python API 契约（含 JSON 示例）、SSE 事件协议、前端 ↔ Java API、错误码 | 前后端开发 |
| [04-数据库与存储设计](./04-数据库与存储设计.md) | MySQL 表结构、MinIO 桶规划、Milvus Collection Schema | 后端开发 |
| [05-部署与开发路线图](./05-部署与开发路线图.md) | Docker Compose 编排、硬件需求、里程碑计划、风险清单 | 全员、运维 |

## 系统一句话简介

用户在前端上传文档构建知识库，Python AI 层完成「解析 → 切分 → 向量化 → 入库」；提问时，Java 业务层鉴权后调用 Python 完成「检索 → 精排 → 组装 Prompt → LLM 流式生成」，回答连同引用来源逐 token 流回前端。

## 仓库布局

```
agent-rag/
├── agent-rag-front    # React 18 + TypeScript + Vite + Ant Design
├── agent-rag-java     # Spring Boot 3 业务层（认证、会话、知识库管理、SSE 转发）
├── agent-rag-python   # FastAPI AI 层（解析、Embedding、检索、Rerank、生成）
└── doc/               # 本文档集
```

## 待拍板的关键决策

1. **LLM 来源**：云端 API（DeepSeek / 通义千问）还是本地私有化（vLLM + Qwen2.5）？
2. **数据规模**：文档量级与并发量级 → 决定向量库从 PGVector 起步还是直接 Milvus
3. **权限模型**：是否需要知识库级隔离（不同用户访问不同知识库）

> 文档版本：v1.0 · 2026-07-26
