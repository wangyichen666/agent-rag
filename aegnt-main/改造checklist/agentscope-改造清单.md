# agentscope 改造清单（框架侧 · 练扩展）

> 目标：通过修改/扩展 agentscope 框架本身，吃透它的扩展点。配合 Vibe Coding 工具（Claude Code / Cursor）执行。每条给「目标 / 改哪个文件 / 验收 / 难度」。
> 源码根：`/Users/zhongyou/Desktop/github/agentscope/src/agentscope/`
> 原则：在 fork 或分支上改，别污染主仓库；优先用**扩展**（继承/注册）而非改源码，遇到必须改内核的才改。

---

## A. 中间件扩展（W07 相关）

### A1 · 写一个"打点审计中间件"
- 目标：实现 `MiddlewareBase` 的 `on_reasoning` + `on_model_call`，记录每轮推理的迭代号、模型名、token、耗时，输出结构化日志。
- 改：新建 `my_ext/middlewares.py`，继承 `MiddlewareBase`（`middleware/_base.py:12`）。不改框架。
- 验收：给一个 Agent 挂上，跑一次回复，日志里每轮推理一行 JSON 含 token/耗时。
- 难度：⭐⭐

### A2 · 写一个"敏感词拦截中间件"
- 目标：`on_reply` 里检测输出含敏感词时，把回复替换成兜底语。
- 改：新建文件，实现 `on_reply`（`middleware/_base.py:65`），在 `next_handler` 后检查。
- 验收：问含敏感词的问题，输出被替换。
- 难度：⭐⭐

### A3 · 写一个"RAG 检索重排中间件"
- 目标：仿 `RAGMiddleware`（`middleware/_rag.py:456`），但检索后加一道 rerank（按相关度二次排序再注入 HintBlock）。
- 改：新建文件，参考 `_rag.py` 结构。
- 验收：对比有/无 rerank 的检索片段顺序变化，回答质量提升。
- 难度：⭐⭐⭐

---

## B. 工具扩展（W06 相关）

### B1 · 写一个自定义 ToolBase 子类（带状态）
- 目标：实现 `ToolBase` 子类，带 `check_permissions` + `input_schema`，且 `is_state_injected=True` 拿到 `AgentState`。例如"读 Agent 上下文统计"工具。
- 改：新建文件，继承 `tool/_base.py:ToolBase`。
- 验收：Agent 调它，能读到自己的 `state.context` 长度。
- 难度：⭐⭐⭐

### B2 · 加一个 ToolGroup 并验证 ResetTools"最终状态"语义
- 目标：建两个自定义组，验证 `ResetTools`（`tool/_builtin/_meta.py`）传 bool 是最终状态非增量——激活 A 会停用 B。
- 改：用现有 API 组装，不改框架。
- 验收：日志证明激活一个组时另一个被停用。
- 难度：⭐⭐

### B3 · 给 FunctionTool 加全局超时+重试装饰（工具级中间件）
- 目标：用 `ToolMiddlewareBase` 给工具加超时+重试，不改函数本身。
- 改：新建工具中间件，挂到 FunctionTool 的 `middlewares`。
- 验收：模拟慢工具，超时触发重试，最终返回或报错。
- 难度：⭐⭐⭐

---

## C. 模型扩展（W05 相关）

### C1 · 写一个"Mock 模型"用于本地无 key 测试
- 目标：仿 `tests/utils.py:MockModel`，写一个返回预设响应的 `ChatModelBase` 子类，能模拟工具调用。
- 改：新建文件，继承 `model/_base.py:35:ChatModelBase`，实现 `__call__`/`_call_api`。
- 验收：用它跑通一个 Agent 全流程，不花 token。
- 难度：⭐⭐⭐

### C2 · 给 DashScope 模型加"成本记录"
- 目标：子类化 `DashScopeChatModel`，每次调用后按 model 算成本（价格表），记入 metadata。
- 改：新建子类，重写 `_call_api` 后处理（参考 `model/_dashscope/_model.py:176`）。
- 验收：跑一次，`msg.metadata` 里有本次成本估算。
- 难度：⭐⭐⭐

### C3 · 接一个新 provider（如本地 vLLM）
- 目标：仿 `DashScopeChatModel` + `DashScopeChatFormatter`，接一个 OpenAI 兼容的本地 vLLM。
- 改：新建 model + credential + formatter（或在 DashScope 基础上改 base_url）。
- 验收：本地 vLLM 跑通 Agent。
- 难度：⭐⭐⭐⭐

---

## D. 记忆与上下文扩展（W07 相关）

### D1 · 自定义 SummarySchema 字段
- 目标：改 `ContextConfig.summary_schema`（`agent/_config.py:106`），加一个 `open_questions` 字段，看压缩摘要是否有这一段。
- 改：传自定义 Pydantic schema 给 `context_config`。
- 验收：压缩后的 summary 含新字段。
- 难度：⭐⭐

### D2 · 写一个"对话向量化长期记忆"中间件
- 目标：每次对话结束把要点写向量库，下次开新会话先检索相关历史注入。介于 AgenticMemory 和 ReMe 之间。
- 改：新建中间件，用 `rag/_vdb/` 存储检索。
- 验收：新会话能"记得"上一会话的关键信息。
- 难度：⭐⭐⭐⭐

---

## E. 多 Agent / 服务化扩展（W08 相关）

### E1 · 自定义一个 SubAgentTemplate 并 spawn
- 目标：在 `examples/agent_service/main.py` 里加一个自定义 worker 模板（如"代码审查员"），用 TeamCreate/AgentCreate 跑起来。
- 改：参考 `app/_types.py:SubAgentTemplate`。
- 验收：leader 能 spawn 并调度这个自定义 worker。
- 难度：⭐⭐⭐

### E2 · 把 MessageBus 从 InMemory 换 Redis 并验证多进程
- 目标：起两个 app 进程，leader 在 A、worker 在 B，验证跨进程通信。
- 改：用 `app/message_bus/_redis_message_bus.py`。
- 验收：跨进程 TeamSay 通。
- 难度：⭐⭐⭐⭐

### E3 · 给 SSE 端点加一个断线重连测试
- 目标：连 `GET /sessions/{sid}/stream`（`app/_router/_session.py`），中途断开，重连后能续上序号。
- 改：可能需小补 resume 逻辑（看 Envelope seq 是否已支持）。
- 验收：重连后不丢消息、seq 连续。
- 难度：⭐⭐⭐⭐

---

## 完成度自测

- [ ] A 区至少 2 条
- [ ] B 区至少 1 条
- [ ] C1（Mock 模型）必做——后面调试省 token
- [ ] D1 + D2 至少 1 条
- [ ] E1 + E2 至少 1 条

> 全部做完，你已经能"改造框架"而不只是"用框架"——这是高级工程师的分水岭。