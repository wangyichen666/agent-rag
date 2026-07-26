# agent-rag-java

RAG 系统的业务层（Spring Boot 3）。负责用户/认证、知识库与文档管理、MinIO 文件存储、会话消息持久化、SSE 流式转发。不做任何向量/模型计算（那是 agent-rag-python 的事）。

## 快速开始

前置：MySQL 8（执行 `src/main/resources/sql/schema.sql`）、MinIO、运行中的 agent-rag-python。

```bash
# 环境变量（均有默认值，本地可全用默认）
export DB_URL=jdbc:mysql://127.0.0.1:3306/agent_rag
export DB_USER=root DB_PASSWORD=root
export MINIO_ENDPOINT=http://127.0.0.1:9000
export AI_BASE_URL=http://127.0.0.1:8000
export AI_INTERNAL_TOKEN=dev-internal-token

mvn spring-boot:run
```

默认管理员：`admin / admin123`（`ADMIN_USERNAME` / `ADMIN_PASSWORD` 可改）。

## 接口一览（`/api` 前缀，除登录外均需 `Authorization: Bearer <JWT>`）

| 接口 | 说明 |
|---|---|
| `POST /api/auth/login` | 登录 |
| `GET/POST /api/kb`、`GET/DELETE /api/kb/{id}` | 知识库 |
| `GET/POST /api/kb/{id}/documents` | 文档列表 / 上传（multipart，字段名 `file`） |
| `DELETE /api/documents/{id}`、`POST /api/documents/{id}/reingest` | 删除 / 重新解析 |
| `GET/POST /api/conversations`、`GET /api/conversations/{id}/messages` | 会话与历史 |
| `POST /api/chat/completions` | 问答（SSE：meta/token/done/error，与 Python 协议一致） |
| `POST /api/messages/{id}/feedback` | 答案反馈（赞/踩） |
| `GET /api/system/ai-health` | 聚合 Python 健康检查 |

## 设计要点

- **SSE 透传**：`ChatService` 用 `java.net.http.HttpClient` 流式读 Python，`SseEmitter` 原样转发；`done` 时把完整回答 + 引用 + 检索 debug 落库 `message` 表
- **文档状态机**：`pending → parsing → success/failed`，Python 解析完成后回调 `/internal/callback/ingest`
- **删除顺序**：先删向量再删记录（宁残留文件，不残留可检索向量）
- **权限**：M1 全量开放给登录用户，`kb_permission` 表已建，二期在 `KbService.listVisible` 加过滤即可

## 目录结构

```
src/main/java/com/example/rag/
├── common/          # Result / BizException / 全局异常处理
├── config/          # Security / CORS / 初始管理员
├── infra/
│   ├── ai/          # AiClient（REST + SSE + Internal Token）
│   └── storage/     # MinioService
└── module/
    ├── auth/        # 登录 / JWT
    ├── kb/          # 知识库 / 文档 / 解析回调
    └── chat/        # 会话 / 消息 / 问答 SSE
```
