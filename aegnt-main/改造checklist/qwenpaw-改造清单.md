# QwenPaw 改造清单（产品侧 · 练落地）

> 目标：通过修改/扩展 QwenPaw 产品，吃透"框架→产品"的工程加层。这是毕业项目（W11-W12）的直接脚手架。配合 Vibe Coding 工具执行。每条给「目标 / 改哪个文件 / 验收 / 难度」。
> 源码根：`/Users/zhongyou/Desktop/github/QwenPaw-main/src/qwenpaw/`
> 原则：先读懂再改；优先用扩展点（hook/gate/插件/mode）而非改内核；改前看 `tests/` 有无对应契约测试。

---

## A. Loop Engineering 扩展（W10/W12 相关）

### A1 · 加一个自定义 Stop Gate
- 目标：实现一个新 gate，如"同一文件路径被读写超过 N 次就停"或"输出长度超过阈值就停"，注册进 gate runner。
- 改：仿 `loop/gates/doom_loop.py:43`（`DoomLoopGate`）或 `file_loop_gate.py:41`（`FileLoopGate`），继承 `LoopGate`（`loop_gate.py:40`）；在 `loop/gates/runner.py`/`handler.py` 注册。
- 验收：构造触发场景，该 gate 命中并停止循环，日志有记录。
- 难度：⭐⭐⭐

### A2 · 调整 BudgetGate 阈值并验证熔断
- 目标：改 `loop/gates/budget.py:27`（`BudgetGate`）的预算配置，跑一个长任务验证超预算即停。
- 改：budget.py + 配置项。
- 验收：超预算时 Agent 被熔断，token 不再增长。
- 难度：⭐⭐

### A3 · 加一个"评分门控"用 Rubric Gate
- 目标：用 `StandaloneRubricGate`（`rubric.py:154`），定义一个评分判据（如"回答必须含引用来源"），不达标的轮次继续直到达标或超限。
- 改：rubric.py + prompt 配置。
- 验收：低质回答触发继续迭代。
- 难度：⭐⭐⭐⭐

---

## B. Runtime / SSE 扩展（W09 相关）

### B1 · 给 Runtime 加一个新阶段（如 PRE_BUDGET_CHECK）
- 目标：在 `runtime/runtime.py:32` 的 `Runtime.run`（:49）8 阶段间插一个新阶段，挂预算预检 hook。
- 改：`runtime/runtime.py` + `runtime/phases.py`（Phase 枚举）+ 注册 hook。
- 验收：日志看到新阶段执行，hook 生效。
- 难度：⭐⭐⭐⭐

### B2 · 给 Envelope 加一种新事件类型
- 目标：在 `runtime/envelope.py:27` 的 `Envelope.translate_event`（:138）里，把一个框架事件翻译成新的 SSE 消息类型（如"自定义进度事件"）。
- 改：envelope.py。
- 验收：前端 SSE 流收到新类型消息。
- 难度：⭐⭐⭐

### B3 · AgentBuilder 加一个自定义工具组
- 目标：在 `runtime/builder.py:22` 的 `build_toolkit`（:36）里，按某条件注入一组自定义工具。
- 改：builder.py。
- 验收：特定 Agent 拿到该工具组。
- 难度：⭐⭐⭐

---

## C. 治理与安全扩展（W10 相关）

### C1 · 加一条 tool_guard YAML 规则
- 目标：在 `security/tool_guard/` 机制里，加一条规则拦截一类危险命令（如 `git push --force` 到 main、`DROP TABLE`）。
- 改：YAML 规则文件 + 可能补 `engine.py` 匹配逻辑。
- 验收：危险命令被 deny/ask，审计有记录。
- 难度：⭐⭐

### C2 · 写一个 PolicyGuardedTool 包装自定义工具
- 目标：仿 `governance/tool_adapter.py:108`（`PolicyGuardedTool`），把一个自定义工具包一层策略，限制只有特定 Agent 能调。
- 改：governance/ + 策略配置。
- 验收：越权调用被拒。
- 难度：⭐⭐⭐

### C3 · 接一个新沙箱后端（如 Docker sandbox）
- 目标：仿 `sandbox/bubblewrap_sandbox.py`，用 Docker 实现一个沙箱后端注册进 `sandbox/config.py`。
- 改：新建 sandbox 文件 + config。
- 验收：工具在 Docker 容器内执行，宿主隔离。
- 难度：⭐⭐⭐⭐

### C4 · 加一个人在回路审批 onboarding
- 目标：用 `app/approvals/service.py:72`（`ApprovalService`）+ `driver_gate.py`，给某类操作配审批流，前端走 `REQUIRE_USER_CONFIRM`。
- 改：approvals/ + 前端。
- 验收：触发该操作时暂停等人审批，审批后继续/拒绝。
- 难度：⭐⭐⭐⭐

---

## D. MCP Server 扩展（W11 相关 · 毕业项目核心）

### D1 · 给 QwenPaw 的 MCP 配置管理加白名单校验测试
- 目标：读懂 `app/routers/mcp.py`（`update_mcp_tool_whitelist:102`），补一个测试验证白名单生效。
- 改：`tests/` 加测试。
- 验收：白名单外的工具被禁。
- 难度：⭐⭐

### D2 · 自建一个独立 MCP Server 并接进 QwenPaw
- 目标：用官方 `mcp` SDK 起一个 Server（如"查内部 wiki"），通过 QwenPaw `drivers/handlers/mcp.py:51`（`MCPDriverHandler`）+ `drivers/adapters/agentscope_tool.py:135`（`DriverCapabilityTool`）接进 Agent。
- 改：新建 MCP Server 项目 + QwenPaw 配置一个 client。
- 验收：Agent 能 `list_tools` 发现并调用你的 Server 工具，鉴权+审计生效。
- 难度：⭐⭐⭐⭐

### D3 · 给 MCP Server 调用加超时+重试+熔断
- 目标：在 D2 基础上，`drivers/handlers/mcp.py` 调用层加超时、重试、熔断（参考 `token_usage` + gate 思路）。
- 改：drivers/handlers/mcp.py。
- 验收：Server 慢/挂时客户端熔断而非卡死。
- 难度：⭐⭐⭐⭐

---

## E. 多 Agent / 渠道扩展（W08/W11 相关）

### E1 · 加一个自定义 Agent Mode
- 目标：仿 `modes/`（如 `mission/`），定义一个新 mode（如"数据分析模式"），用 `commands() + tools() + hooks() + prompt_contributors()` 组合。
- 改：新建 mode 包。
- 验收：切到该 mode 时 Agent 行为/工具集变化。
- 难度：⭐⭐⭐⭐

### E2 · 加一个消息渠道（如飞书机器人）
- 目标：仿 `app/channels/` 的 `BaseChannel`（参考钉钉/飞书实现），接一个新渠道。
- 改：新建 channel 文件。
- 验收：该渠道发消息能触发 Agent 回复。
- 难度：⭐⭐⭐⭐

### E3 · MultiAgentManager 加一个监控端点
- 目标：给 `app/multi_agent_manager.py:23`（`MultiAgentManager`）加一个 HTTP 端点，列出当前所有 Agent 状态。
- 改：manager + router。
- 验收：`GET /agents` 返回各 Agent 状态、上次活跃时间。
- 难度：⭐⭐⭐

---

## F. 可观测性扩展（W10/W12 相关）

### F1 · 给 TokenUsageManager 加按租户聚合
- 目标：改 `token_usage/manager.py:65`（`TokenUsageManager`），按 tenant 聚合 token，导出接口。
- 改：manager.py + storage。
- 验收：能查某租户某时段 token 总量。
- 难度：⭐⭐⭐

### F2 · 接 Langfuse 并跑通一次完整 trace
- 目标：配 `observability/langfuse.py`，跑一次多 Agent 请求，在 Langfuse 看到完整链路。
- 改：配置 + 可能补 instrumentation。
- 验收：Langfuse 看板有 trace 树。
- 难度：⭐⭐⭐

---

## 毕业项目映射（W11-W12 要做的子集）

毕业项目最少做完这几条，即可达"简历项目"完成度：

- [ ] **D2** 自建 MCP Server 接入（核心）
- [ ] **C1** 至少一条 tool_guard 规则
- [ ] **A2** BudgetGate 熔断验证
- [ ] **A1** 至少一个自定义 Stop Gate
- [ ] **F2** Trace 跑通
- [ ] **B3** 自定义工具组接进 AgentBuilder（造 leader/worker 时用）

> 做完这 6 条，你的毕业项目就有了：自建 MCP（鉴权/审计）+ 治理（gate/tool_guard）+ 可观测（trace）+ 自定义多 Agent 装配——正好覆盖 JD 核心。