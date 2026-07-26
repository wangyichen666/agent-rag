# agent-rag-front

RAG 系统前端（React 18 + TypeScript + Vite + Ant Design 5）。

## 快速开始

```bash
npm install
npm run dev        # http://localhost:5173，/api 代理到 127.0.0.1:8080
npm run build      # 产物 dist/
```

默认账号 `admin / admin123`（由 Java 端初始化）。

## 页面

| 页面 | 路径 | 功能 |
|---|---|---|
| 登录 | /login | JWT 登录 |
| 对话 | / | 知识库勾选 → 新会话 → SSE 流式问答 + 引用标签 + 拒答态 + 停止生成 |
| 知识库管理 | /kb | 知识库 CRUD、文档上传、解析状态轮询（3s）、失败重试、删除 |

## 实现要点

- **SSE 客户端**（`src/api/sse.ts`）：EventSource 不支持 POST/Header，用 `fetch + ReadableStream` 手写事件解析（meta/token/done/error）
- **流式渲染**：token 增量 append 到消息体，react-markdown 边收边渲染，尾部光标动画
- **引用溯源**：meta 事件先达，答案下方渲染引用 Tag，悬停显示标题路径/页码/相关度
- **解析状态轮询**：知识库页每 3s 检查 pending/parsing 文档并刷新

## 部署

Dockerfile 两阶段：node 构建 → nginx 托管 + `/api` 反代（已关闭缓冲支持 SSE）。
