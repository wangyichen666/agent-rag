# AI Agent 系统学习教程（基于 AgentScope 2.0 + QwenPaw）

> 从零到能独立造 Agent 产品的 12 周系统学习路径。
> 目标受众：0-1 年初级开发者，目标是「系统学习、从零到能独立造」。
> 节奏：12 周按周计划，每周一个明确交付物。
> 毕业项目：研究 + 写作 + 审校 三 Agent 协作平台（含自建 MCP Server）。
> 参考地基：本机 `/Users/zhongyou/Desktop/github/agentscope`（框架）与 `/Users/zhongyou/Desktop/github/QwenPaw-main`（产品）。

---

## 0. 这份教程为何这样设计（必读）

### 0.1 谁是它

- **agentscope 2.0.4**：阿里通义 SysML 团队的生产级 AI Agent 框架。核心理念是「为日益强大的 agentic LLM 而设计」——不靠死 prompt 和固定编排约束模型，而是利用模型自身推理与工具使用能力。
- **QwenPaw (copaw)**：agentscope 官方团队基于 2.0 构建的真实产品（Agent OS / 个人 AI 助手）。它把框架扩展成跨渠道（钉钉/飞书/企微/Discord 等）+ 定时任务 + Coding Mode（三栏 IDE）的完整产品，示范了框架本身没有的工业级工程化。
- 二者是同源团队：**agentscope 提供 building blocks，QwenPaw 展示如何把它们组装 + 加厚成产品**。这正好构成「理论 → 框架 → 产品」三段式。

### 0.2 最重要的避坑提示：2.0 ≠ 1.0

网上绝大多数博客、旧教程讲的是 agentscope **1.0**，与当前 2.0.4 已**完全不同**：

| 维度 | 1.0（旧资料） | 2.0.4（本教程基于此） |
|---|---|---|
| Agent 类 | `ReActAgent`/`DialogAgent`/`UserAgent`/`ReplAgent` 多个子类 | **只有统一的 `Agent` 一个类**，ReAct 循环内建于 `_reply_impl` |
| 编排原语 | `Pipeline`/`Pipe`/`MsgHub`/`SequentialPipeline` | **已移除**；靠「单 Agent reasoning-acting 循环 + 事件流 + 服务层 Team 工具 + MessageBus」 |
| 多 Agent | 代码级 pipeline 编排 | 服务层 `TeamCreate`/`AgentCreate`/`TeamSay` + MessageBus |
| 调用方式 | 同步 `agent(msg)` | 全异步 `await agent.reply_stream(msg)` |

本教程全程基于 2.0 真实 API，并把「1.0 思维 → 2.0 思维迁移」作为每篇末尾的固定避坑小节。这条暗线对面试讲项目极有价值。

### 0.3 三段式结构

| 阶段 | 周次 | 主线 | JD 考点 |
|---|---|---|---|
| **I. 地基** | W1-W3 | 补 Python/asyncio + LLM API + 手写 ReAct/Plan-Execute（不依赖框架） | Agent 核心范式、Prompt Engineering |
| **II. 框架** | W4-W8 | 吃透 agentscope 2.0：Agent/Message/Event → Toolkit/MCP → Middleware/记忆 → RAG → 多 Agent Team + 服务化 | MCP、编排引擎、上下文/记忆、可观测性 |
| **III. 产品** | W9-W12 | 拆解 + 仿造 QwenPaw：Runtime/SSE → Loop Engineering/治理/沙箱 → 毕业项目 | 生命周期管理、流量治理、安全沙箱、企业级落地 |

---

## 1. 目录结构

```
2027年/
├── README.md                      ← 你在这里（总入口）
├── 00-导读与环境准备.md            ← 环境搭好、跑通第一个 Agent
├── 阶段一-地基/
│   ├── W01-Python异步与LLM-API调用.md
│   ├── W02-Agent范式与Prompt工程.md
│   └── W03-手写ReAct与Plan-Execute循环.md
├── 阶段二-框架/
│   ├── W04-agent scope入门与Agent内核.md
│   ├── W05-消息Event与模型对接.md
│   ├── W06-工具体系与MCP.md
│   ├── W07-中间件记忆与上下文治理.md
│   └── W08-RAG与多Agent-Team与服务化.md
├── 阶段三-产品/
│   ├── W09-Runtime与SSE状态机.md
│   ├── W10-Loop-Engineering与治理沙箱安全.md
│   ├── W11-多Agent协作平台实战(上).md
│   └── W12-多Agent协作平台实战(下)-毕业交付.md
├── code/                          ← 每周可运行示例（w01/ … w12/，各带 README）
├── 面试问答卡/                    ← 按主题聚合（10 张）
└── 改造checklist/
    ├── agentscope-改造清单.md
    └── qwenpaw-改造清单.md
```

---

## 2. 每周篇统一模板

每篇 `W##-*.md` 固定 6 个小节，保证可读与导航一致：

```
# W## · 标题
> 本周目标 | 一句话 | JD 考点：xxx
## 1. 本周你将搞懂什么          ← 学习目标 + 为什么重要
## 2. 原理铺垫                  ← 概念/原理 + 文字版思维导图
## 3. 源码精读                  ← 带绝对路径与行号，精确到方法
## 4. 动手作业                  ← 指向 code/w##/，最小可运行步骤 + 预期输出
## 5. 面试问答卡（本周相关）     ← 2-4 个高频问题 + 参考答案话术 + 源码佐证
## 6. 从 1.0 到 2.0 / 避坑      ← 旧资料对照，防止学歪
## 附：本周 checkpoint           ← 打勾清单：跑通？改懂？能讲？
```

---

## 3. 12 周逐周大纲

### 阶段一 · 地基（W1-W3，给初级补底，不依赖框架）

#### W01 · Python 异步与 LLM API 调用
- **目标**：能看懂 agentscope 全异步代码；能用原生 SDK 调通 DashScope / Claude / OpenAI；会用 `httpx` 手写 SSE 流式解析。
- **原理**：`asyncio` 事件循环、协程/Task/`async for`、`httpx.AsyncClient`、SSE 字节流解析、并发（`asyncio.gather`）。
- **源码精读**：`src/agentscope/_utils/`（异步工具）、`model/_base.py` 的 `__call__` async 形态。
- **动手**：① `httpx` 手写 SSE 流式解析器逐 token 打印；② `asyncio.gather` 并发调 3 个 provider 对比输出。
- **面试卡**：01-Agent 范式（异步）、API 流式原理。
- **避坑**：1.0 同步 `agent()` → 2.0 全 `await agent.reply_stream()`。

#### W02 · Agent 范式与 Prompt 工程
- **目标**：讲清 ReAct / Plan-Execute / Multi-Agent / CoT / ToT / Few-shot / Self-Consistency 各是什么、何时用；了解 Transformer/Attention 极简原理。
- **原理**：CoT 推理链、ReAct「Thought→Action→Observation」交替、Plan-Execute「先分解后执行 + 修正闭环」、Multi-Agent 通信（消息传递/共享内存/黑板模式）。
- **动手**：用纯 prompt 让模型按 ReAct 格式做一次工具决策，体会「模型自身会推理」。
- **面试卡**：01-Agent 范式全梳理。
- **避坑**：JD 提到的 Hermes/OpenClaw/LangChain 多为别家体系，教程给「对应到 agentscope 2.0 是什么」。

#### W03 · 手写 ReAct 与 Plan-Execute 循环
- **目标**：**不依赖任何框架**，用原生 LLM API + 循环造一个能调工具的 Agent。这是理解框架「为何这么设计」的关键。
- **原理**：工具 JSON Schema、Function Calling 返回解析、循环终止、最大迭代保护、错误重试。
- **动手**：① 手写 50 行 ReAct loop（系统 prompt + 工具定义 + while + 解析 tool_call）；② 升级成 Plan-Execute（先出 JSON 计划，再逐步执行 + 可修正）。
- **面试卡**：03-推理循环与工具调用（用自己的轮子讲，再对比框架）。
- **避坑**：自己的轮子会撞上「上下文爆炸 / 工具结果过长 / 死循环」——这些痛点正是 W07/W10 要解决的，埋下伏笔。

### 阶段二 · 框架（W4-W8，吃透 agentscope 2.0）

#### W04 · AgentScope 入门与 Agent 内核
- **目标**：跑通 quickstart；理解 2.0 为何只剩一个 `Agent` 类。
- **源码精读**：`agent/_agent.py`（`__init__:100`、`_reply_impl:664`、reasoning-acting 循环、`max_iters=20`）、`agent/_config.py`（ModelConfig/ContextConfig/ReActConfig）、`tests/agent_basic_test.py`（MockModel 不花钱学用法）。
- **动手**：`DashScopeChatModel + Toolkit(Bash,Read)` 跑最小 Agent，`async for` 消费 `reply_stream` 打印事件。
- **面试卡**：05-AgentScope 架构设计。

#### W05 · 消息/Event 与模型对接
- **目标**：吃透 `Msg`/ContentBlock 体系与事件流；接通多 provider；会结构化输出。
- **源码精读**：`message/_base.py`、`message/_block.py`（Text/ToolCall/ToolResult/Data/HintBlock）、`event/_event.py`（EventType 全枚举）、`formatter/`（9 provider × Chat/MultiAgent 双格式化器）、`model/_base.py:generate_structured_output`。
- **动手**：① 事件流消费者，ThinkingBlock/ToolCallBlock 分别染色打印；② Pydantic 让模型返回结构化结果。
- **面试卡**：02-消息与编排、06-模型对接与结构化输出。
- **避坑**：1.0 `Msg` 与 2.0 content block 模型完全不同。

#### W06 · 工具体系与 MCP（客户端）
- **目标**：会用 FunctionTool/ToolBase/ToolGroup；理解 MCP 客户端；把 MCP 接进 Toolkit。
- **源码精读**：`tool/_toolkit.py`、`tool/_adapters.py`（FunctionTool/MCPTool）、`tool/_tool_group.py`（分组激活，替代「工具全可见」）、`tool/_builtin/`（Bash/Read/Write/Edit）、`mcp/_mcp_client.py`（Stdio/Http config）、`permission/`（PermissionMode 五档）。
- **动手**：① 写一个自定义 FunctionTool（schema、超时、重试）；② 接现成 MCP（如 `@playwright/mcp` 或高德）；③ 体验 `ResetTools` 分组切换。
- **面试卡**：04-工具调用与 MCP、09-权限与沙箱。
- **JD 映射**：MCP Server/Client、工具注册中心、动态发现、权限、超时重试——全覆盖（客户端侧）。**MCP Server 端搭建并入毕业项目（W11-W12）**。

#### W07 · 中间件、记忆与上下文治理
- **目标**：掌握洋葱模型 6 大 hook；理解短期记忆/压缩/长期记忆三层；接 Trace + Token 监控。
- **源码精读**：`middleware/_base.py`（reply/reasoning/acting/model_call/compress_context/system_prompt 六 hook）、`agent/_agent.py:_compress_context_impl:327`（SummarySchema 结构化压缩）、`middleware/_rag.py`、`middleware/_tracing/_trace.py`（OTel span）、AgenticMemory/Mem0/ReMe 三种长期记忆中间件。
- **动手**：① 写一个自定义中间件（如审计日志：记录每次 reasoning token）；② 跑 `examples/long_term_memory/agentic_memory/main.py`，看 Agent 自写 `Memory/MEMORY.md`。
- **面试卡**：07-记忆与上下文、08-可观测性。
- **JD 映射**：上下文窗口管理、长短期记忆、Trace、Token 监控——全覆盖。回填 W03 自己轮子的痛点。

#### W08 · RAG 与多 Agent Team + 服务化
- **目标**：建知识库做 RAG；理解 2.0 多 Agent 的 Team + MessageBus 模型；跑服务化 SSE。
- **源码精读**：`rag/_knowledge.py`、`rag/_parser/`、`rag/_chunker/`、`rag/_vdb/`（Qdrant/MilvusLite/MongoDB）、`examples/rag/integrate_with_agent.py`（static/agentic 双模式）；`app/_tool/_team_create.py`/`_agent_create.py`/`_team_say.py`、`app/message_bus/`（InMemory/Redis）、`app/_service/_session.py`（多租户会话状态机）、`app/_router/_session.py:619`（SSE 长连接）。
- **动手**：① 建 PDF 知识库，跑 static + agentic 双 RAG；② 起 `examples/agent_service/main.py`，创建 Team，leader spawn 两个 worker 分工。
- **面试卡**：02-消息与编排（多 Agent）、07-RAG。
- **避坑**：1.0 多 Agent 靠 `Pipeline`/`MsgHub` 代码编排，2.0 靠服务层 Team 工具——迁移最反直觉的点，本周讲透。

### 阶段三 · 产品（W9-W12，拆解 + 仿造 QwenPaw）

#### W09 · Runtime 与 SSE 状态机
- **目标**：理解 QwenPaw 怎么把 agentscope `reply` 包成 8 阶段 Runtime + Envelope 状态机，产出标准 SSE。
- **源码精读**：`src/qwenpaw/runtime/runtime.py`（8 阶段生命周期）、`runtime/envelope.py`（SSE 状态机）、`runtime/executor.py`（AgentExecutor 心跳包装）、`runtime/builder.py`（AgentBuilder 依赖注入式组装）、`agents/react_agent.py:47`（QwenPawAgent 扩展 `Agent`）。
- **动手**：仿写迷你 Runtime（3-4 阶段）+ Envelope，把自己的 Agent 包成 SSE 接口，curl 测。
- **面试卡**：06-服务化与 SSE、05-架构设计（产品层）。
- **价值**：看懂「框架 reply() 到工业级 API」中间那层工程。

#### W10 · Loop Engineering 与治理、沙箱、安全
- **目标**：理解 QwenPaw 怎么治理 Agent 失控（死循环/超预算/无效迭代）、做权限与沙箱。
- **源码精读**：`loop/gates/base.py` + 各 gate（budget/iteration/doom_loop/file_loop/scoring）、`governance/tool_adapter.py`（`PolicyGuardedTool`）、`governance/policy.py`、`security/tool_guard/`（YAML 规则、shell 逃逸守护、STRICT/SMART/AUTO/OFF）、`sandbox/`（macOS Seatbelt/Linux bubblewrap·landlock/Windows AppContainer）、`security/skill_scanner/`、`token_usage/`、`observability/`（Langfuse）、`app/approvals/`（人在回路）。
- **动手**：① 给 W06 Agent 加自定义 stop gate（「连续 3 次调同一工具就停」）；② 配一条 YAML tool_guard 规则拦截危险命令。
- **面试卡**：08-可观测性、09-权限与沙箱、10-工程化与流量治理。
- **JD 映射**：Agent Loop 治理（断连/无效循环/执行失控）、安全沙箱、调用审计、熔断限流——本周深度最高、面试最亮眼。

#### W11 · 多 Agent 协作平台实战（上）
- **目标**：动手造毕业项目骨架——研究 + 写作 + 审校 三 Agent 协作平台。
- **设计**：leader 拆题 → researcher（RAG + Web 检索）→ writer 产出 → reviewer 审校 → leader 聚合。用 agentscope Team 模型起骨架。
- **动手**：搭 leader + researcher + writer + reviewer、TeamSay 通信、共享知识库、流式输出到简易 Web/CLI。
- **本阶段并入 MCP Server**：自建一个企业级 MCP Server（工具注册/schema/鉴权/超时重试/审计 + 简易沙箱），作为 researcher 的数据源接入。
- **面试卡**：02-多 Agent、04-MCP Server、10-工程化。

#### W12 · 多 Agent 协作平台实战（下）· 毕业交付
- **目标**：把 W10 治理 + W9 Runtime 加进项目，达到「能讲成简历项目」的完成度。
- **动手**：① 加 stop gate + 审批（危险操作人在回路）；② 加 Token 监控 + 简易 trace；③ Docker 化 + `README` 讲清架构；④ 写「5 分钟讲清这个项目」话术稿。
- **交付**：可运行仓库 + 架构图 + 改造 checklist + 面试话术。
- **面试卡**：10-工程化与流量治理（综合）。

---

## 4. 面试问答卡（10 张，按主题聚合）

每张卡固定四段：「问题群」「参考答案（要点）」「源码佐证（绝对路径）」「一句话话术」。

| # | 卡片 | 覆盖周次 |
|---|---|---|
| 01 | Agent 范式（ReAct/Plan-Execute/Multi-Agent/CoT/ToT） | W2/W3/W8 |
| 02 | 消息与编排（Msg/Event/Team/MessageBus） | W5/W8/W11 |
| 03 | 推理循环与工具调用 | W3/W4 |
| 04 | 工具与 MCP（Client + Server） | W6/W11 |
| 05 | AgentScope 架构设计 | W4/W9 |
| 06 | 模型对接与结构化输出、SSE 服务化 | W5/W9 |
| 07 | 记忆、上下文与 RAG | W7/W8 |
| 08 | 可观测性（Trace/Token/审计） | W7/W10 |
| 09 | 权限与沙箱 | W6/W10 |
| 10 | 工程化与流量治理（限流熔断/Look 治理/部署） | W10/W12 |

---

## 5. 改造 Checklist（两份，可直接喂 Vibe Coding）

### `agentscope-改造清单.md`（框架侧，练扩展）
任务示例：加自定义中间件 / 加自定义模型 backend / 加自定义工具 gate。每条给「目标 / 改哪个文件 / 验收方式 / 难度」。

### `qwenpaw-改造清单.md`（产品侧，练落地）
任务示例：改 Runtime 阶段 / 加一条 stop gate / 加一条 tool_guard 规则 / 把自建 MCP Server 接进毕业项目。每条同上。

---

## 6. JD 考点映射表（求职速查）

| JD 关键词 | 对应周次 | 源码佐证 |
|---|---|---|
| ReAct / Plan-Execute / Multi-Agent | W2/W3/W8 | `agent/_agent.py:_reply_impl`、`app/_tool/_team_*` |
| MCP Server / Client | W6/W11-12 | `mcp/_mcp_client.py`、qwenpaw `app/routers/mcp.py` |
| Agent Loop 治理 / 死循环 | W10 | qwenpaw `loop/gates/*` |
| 上下文 / 长短期记忆 | W7 | `agent/_agent.py:_compress_context_impl` |
| Trace / Token 监控 | W7/W10 | `middleware/_tracing`、qwenpaw `token_usage/` |
| 安全沙箱 | W10 | qwenpaw `sandbox/` |
| 限流熔断 / 流量治理 | W10 | qwenpaw `app/` 限流 + `governance/` |
| 部署 / Docker / CI | W12 | qwenpaw `deploy/` + `.github/workflows/` |

### 5 个岗位 → 周次重点匹配概览

| 岗位 | 重点讲深的周次 |
|---|---|
| 高伟达 AI Agent 研发 | W2/W3/W6/W8/W10（多 Agent + Loop 治理 + MCP） |
| 软帝联合 MCP 研发 | W6/W11/W12（MCP Server 全链路 + 全栈） |
| 锦碟云 Python AI 应用 | W6/W7/W8/W11（Agent + RAG + 邮件/工具链） |
| 云启 AI 开发平台 | W4-W8 全段 + W08 服务化 |
| 卡比特 AI 提效 / 云炎 / 浩鲸 | W1-W3 + W6 + W12（Vibe Coding + 提效工程化） |

---

## 7. 模型与环境约定

- **默认模型**：DashScope（通义 Qwen）为主，Claude / OpenAI 作「换 provider」对照示例。
- **Python**：≥ 3.11（agentscope 2.0 要求），用 `uv` 管理虚拟环境。
- **依赖框架**：`agentscope==2.0.4`（PyPI 依赖，非 vendor）。
- 具体 key / 安装步骤见 `00-导读与环境准备.md`。

---

## 8. 如何使用这份教程

1. 先读 `00-导读与环境准备.md`，把环境跑通（能调通第一个 Agent 再说）。
2. 严格按周推进，每篇按模板 6 节走：**原理 → 源码 → 动手 → 面试卡 → 避坑 → checkpoint**。
3. 每周 `code/w##/` 的作业必须真的跑通，不要只读。
4. 阶段三开始用 Vibe Coding 工具（Claude Code / Cursor）执行 `改造checklist/`，边改边学。
5. 求职前用「JD 映射表」+「面试问答卡」回扫，确保每个考点有源码佐证。

---

*本文件是教程的「设计骨架」。你批准这份骨架后，才会逐周编写完整正文。*