# AI Agent 工程师求职学习计划（基于 QwenPaw 项目实战）

> 本文档根据 10 家企业（武汉 / 长沙）的 AI Agent / MCP / AI 应用开发岗位要求，提炼共性能力，制定四阶段递进式学习计划，并以 **QwenPaw**（AgentScope 团队的开源个人 Agent 平台）真实源码作为实战参照系。每个学习模块都给出：学习目标 → 知识点 → QwenPaw 源码对照 → 动手实战任务 → 参考资料。
>
> **适用对象**：有 Python / Java 后端基础，希望转型 AI Agent 方向的工程师。
> **建议周期**：12–15 周（每阶段 3–4 周），可根据基础调整。

---

## 目录

- [一、岗位要求分析](#一岗位要求分析)
- [二、学习计划总览](#二学习计划总览)
- [三、详细学习内容](#三详细学习内容)
  - [阶段一 · 地基筑基（第 1–3 周）](#阶段一--地基筑基第-13-周)
  - [阶段二 · Agent 核心（第 4–7 周）](#阶段二--agent-核心第-47-周)
  - [阶段三 · MCP 与工程化（第 8–11 周）](#阶段三--mcp-与工程化第-811-周)
  - [阶段四 · 平台架构与落地（第 12–15 周）](#阶段四--平台架构与落地第-1215-周)
- [四、QwenPaw 源码实战地图](#四qwenpaw-源码实战地图)
- [五、阶段性产出与简历沉淀](#五阶段性产出与简历沉淀)
- [六、学习资源清单](#六学习资源清单)
- [附录：岗位—能力—阶段对照矩阵](#附录岗位能力阶段对照矩阵)

---

## 一、岗位要求分析

### 1.1 目标岗位速览

| # | 公司 | 岗位 | 城市 | 薪资 | 核心方向 |
|---|------|------|------|------|----------|
| 1 | 高伟达 | AI Agent 研发工程师 | 武汉 | 20–30k | Agent 平台架构 / MCP / 可观测性 / 流量治理 |
| 2 | 软帝联合 | MCP 研发工程师 | 武汉 | 15–20k | MCP Server / 全栈 / 工具链 |
| 3 | 锦碟云 | Python AI 应用工程师 | — | 12–22k | Agent / RAG / 邮件生成 / 数据源 |
| 4 | 云启智慧 | AI 开发平台后端 | — | 11–17k | LLM 集成 / 工作流引擎 / RAG |
| 5 | 武汉卡比特 | AI 提效工程师 | 武汉 | 15–25k | AI Agent / MCP / 工具链 |
| 6 | 星财富 | Agent 工程师 | 长沙 | 15–25k | 金融 / Agent 编排 / RAG |
| 7 | 可孚医疗 | AI Agent 开发工程师 | 长沙 | 12–18k | Python 异步 / Tool Calling / 记忆 / SSE |
| 8 | 云炎科技 | AI 应用型开发工程师 | 长沙 | 12–20k | AI Coding / 自动化 / 全栈 |
| 9 | 浩鲸科技 | AI 开发工程师 | 长沙 | 12–18k | Java / AI Coding / 全栈 |
| 10 | 安克 | AI 开发工程师 | — | 15–20k+ | AI 开发 / 大模型应用 |

### 1.2 共性能力提炼（8 项核心维度）

从 10 个岗位的 JD 中交叉比对，提炼出 8 项共性能力，按"要求该能力的岗位占比"排序：

| 能力维度 | 关键技能 | 岗位覆盖率 | 优先级 |
|----------|----------|-----------|--------|
| Agent 架构与范式 | ReAct、Plan-and-Execute、Multi-Agent、Agent Loop | 10/10 | ★★★★★ |
| 全栈开发 | Python、Java、TypeScript、FastAPI、Spring Boot | 10/10 | ★★★★★ |
| LLM 应用与 Prompt | API 调用、流式输出、Few-shot、CoT、ToT、结构化输出 | 9/10 | ★★★★★ |
| 工程化与运维 | Docker、K8s、CI/CD、可观测性、日志追踪 | 9/10 | ★★★★☆ |
| MCP 协议与工具链 | Server/Client、工具注册、沙箱、审计 | 8/10 | ★★★★☆ |
| AI Coding 工具链 | Cursor、Claude Code、Codex、通义灵码、全流程融入 | 8/10 | ★★★★☆ |
| 后端架构 | Redis、Kafka/RocketMQ、数据库、分布式、高可用 | 8/10 | ★★★★☆ |
| RAG 与向量检索 | 向量库、召回、rerank、知识库接入 | 7/10 | ★★★☆☆ |

> **结论**：Agent 架构、全栈、LLM 应用、工程化是"硬门槛"（几乎必考）；MCP、AI Coding、后端架构是"加分项变标配"；RAG 是高频但不全员要求。学习计划按此优先级排布。

---

## 二、学习计划总览

### 2.1 四阶段路线

```
阶段一 地基筑基 ──▶ 阶段二 Agent 核心 ──▶ 阶段三 MCP 与工程化 ──▶ 阶段四 平台架构与落地
  (第1-3周)            (第4-7周)              (第8-11周)              (第12-15周)
  Python异步          Agent范式             MCP协议规范             Agent编排引擎
  FastAPI             Tool Calling          MCP Server开发          低代码平台
  数据库基础           Agent Loop            安全沙箱               后端架构
  LLM API            记忆与上下文           Multi-Agent协作         流量治理
  Prompt工程          LangChain框架          可观测性               DevOps+AI Coding
```

### 2.2 阶段目标与对标岗位

| 阶段 | 周期 | 目标 | 对标岗位 |
|------|------|------|----------|
| 一 · 地基筑基 | 第 1–3 周 | 打通 Python 异步后端 + LLM API 调用基础 | 可孚医疗、云启智慧、锦碟云 |
| 二 · Agent 核心 | 第 4–7 周 | 掌握 Agent 范式、Tool Calling、Loop、记忆 | 高伟达、可孚医疗、星财富、锦碟云 |
| 三 · MCP 与工程化 | 第 8–11 周 | 能独立开发 MCP Server、做安全沙箱与可观测性 | 软帝联合、高伟达、武汉卡比特 |
| 四 · 平台架构与落地 | 第 12–15 周 | 具备平台级架构设计、流量治理、AI Coding 全流程 | 高伟达、云启智慧、浩鲸科技、云炎科技 |

### 2.3 学习方法

1. **理论 + 源码 + 实战 三位一体**：每个模块先学概念，再读 QwenPaw 对应源码，最后动手实现一个最小版本。
2. **每阶段一个可演示 Demo**：阶段结束时把所学整合成一个能跑、能演示的项目，沉淀到简历。
3. **AI Coding 全程融入**：从阶段一开始就用 Cursor / Claude Code 辅助学习与编码，培养"Vibe Coding"全流程能力（这本身就是岗位要求）。
4. **源码精读优先**：QwenPaw 是生产级 Agent 平台，读它的源码比看教程更接近真实岗位要求。

---

## 三、详细学习内容

### 阶段一 · 地基筑基（第 1–3 周）

> **阶段目标**：打通 Python 异步后端 + LLM API 调用基本功，能独立写一个"调 LLM + 存数据库 + 流式返回"的接口。
> **QwenPaw 对照**：模型接入层（`providers/`）、asyncio 服务运行时（`app/`）。

#### 模块 1.1 · Python 异步编程

**学习目标**：深刻理解 asyncio，能写出高并发、无死锁的异步服务。

**知识点**：
- 事件循环（event loop）原理、`asyncio.run` / `asyncio.gather` / `asyncio.create_task`
- 协程（coroutine）、`async/await` 语义、协程调度
- 多进程 / 多线程 / 协程的适用场景：I/O 密集型用协程，CPU 密集型用进程
- 常见陷阱：协程死锁、内存泄漏、阻塞事件循环、未捕获异常
- `asyncio.Lock` / `Semaphore` / `Queue` 等同步原语

**QwenPaw 源码对照**：
- `src/qwenpaw/app/` —— 整个 Web 服务基于 asyncio，观察它如何组织异步路由与服务
- `src/qwenpaw/agents/tools/run_tool_batch.py` —— 批量工具调用的并发执行模式

**实战任务**：
- 用 asyncio 实现一个并发抓取 10 个 URL 的爬虫，对比同步/异步耗时
- 模拟一个协程死锁场景并修复

**参考资料**：Python 官方 asyncio 文档；《流畅的 Python》异步章节。

---

#### 模块 1.2 · FastAPI 后端框架

**学习目标**：熟练用 FastAPI 构建异步 Web 服务，理解依赖注入与数据校验。

**知识点**：
- 路由定义、路径参数 / 查询参数 / 请求体
- Pydantic 数据校验与序列化（`BaseModel`、`Field`、嵌套模型）
- 依赖注入（`Depends`）、中间件、生命周期事件
- SSE 流式响应（`StreamingResponse`）—— LLM 流式输出的关键
- 异步数据库集成（SQLAlchemy 2.0 async / asyncpg）

**QwenPaw 源码对照**：
- `src/qwenpaw/app/routers/` —— 观察真实 Agent 服务的路由组织
- `src/qwenpaw/app/app_services/` —— 应用服务层如何编排异步逻辑

**实战任务**：
- 用 FastAPI 写一个 `/chat` 接口，接收消息、调用 LLM、以 SSE 流式返回
- 实现 Pydantic 请求/响应模型，做参数校验与错误处理

**参考资料**：FastAPI 官方教程；Pydantic 文档。

---

#### 模块 1.3 · 数据库基础

**学习目标**：掌握 PostgreSQL 与 Redis 在 LLM 应用中的用法。

**知识点**：
- **PostgreSQL**：索引原理（B-tree / GIN）、事务隔离级别（RC / RR / Serializable）、连接池
- **Redis**：底层数据结构、分布式锁（SET NX + 过期）、Stream 消息、缓存策略
- SQL 设计与调优：执行计划（EXPLAIN）、慢查询、分库分表入门

**QwenPaw 源码对照**：
- `src/qwenpaw/agents/memory/adbpg_client.py` —— QwenPaw 用 PostgreSQL 系（ADB-PG）存长期记忆
- `src/qwenpaw/security/secret_store.py` —— 密钥存储设计

**实战任务**：
- 设计一个对话历史表，建立合适索引，测试千万级数据的查询性能
- 用 Redis 实现一个分布式锁，解决并发场景下的资源竞争

**参考资料**：PostgreSQL 官方手册；《Redis 设计与实现》。

---

#### 模块 1.4 · LLM API 调用

**学习目标**：能熟练对接主流大模型 API，理解流式输出与 Token 计费。

**知识点**：
- 主流模型 API：OpenAI、Anthropic Claude、Qwen（DashScope）、DeepSeek、Kimi
- 同步 vs 流式调用、SSE 协议、`usage` 字段与 Token 计费
- 本地模型：Ollama、LM Studio、llama.cpp
- 多模型统一封装：Provider 抽象、能力差异处理

**QwenPaw 源码对照**：
- `src/qwenpaw/providers/` —— 模型供应商抽象层，看它如何统一封装 14+ 云端供应商
- `src/qwenpaw/providers/oauth/` —— 免费模型 OAuth 接入
- `src/qwenpaw/local_models/` —— QwenPaw Local（llama.cpp）本地运行时
- `src/qwenpaw/token_usage/` —— Token 消耗统计与计费

**实战任务**：
- 封装一个 `LLMClient` 类，统一支持 OpenAI / Qwen / DeepSeek 三家 API
- 实现流式输出 + Token 用量统计

**参考资料**：各模型官方 API 文档；OpenAI Cookbook。

---

#### 模块 1.5 · Prompt Engineering 基础

**学习目标**：掌握 Prompt 工程化方法，能稳定引导模型输出。

**知识点**：
- 基础技巧：Zero-shot、Few-shot、Role Prompting
- 推理增强：CoT（Chain-of-Thought）、ToT（Tree-of-Thoughts）、Self-Consistency
- 结构化输出：JSON Schema 约束、Function Calling 引导
- Prompt 模板化管理与效果评估方法

**QwenPaw 源码对照**：
- `src/qwenpaw/modes/*/prompts.py` —— 各 Loop 模式的系统提示词，是工业级 Prompt 的范本
- `src/qwenpaw/agents/memory/prompts.py` —— 记忆管理的提示词

**实战任务**：
- 为一个"代码 review"任务设计 Prompt，对比 Zero-shot / Few-shot / CoT 的效果
- 实现一个 Prompt 模板系统，支持变量注入与版本管理

**参考资料**：OpenAI Prompt Engineering Guide；Anthropic Prompt 工程。

---

### 阶段二 · Agent 核心（第 4–7 周）

> **阶段目标**：掌握 Agent 核心范式与运行机制，能从零实现一个支持工具调用、记忆、循环纠偏的 Agent。
> **QwenPaw 对照**：Loop Engineering（`modes/`）、Scroll Context（`agents/context/`）、ReMe 记忆（`agents/memory/`）。

#### 模块 2.1 · Agent 核心范式

**学习目标**：深入理解 ReAct、Plan-and-Execute、Sub-Agent 三大范式。

**知识点**：
- **ReAct**：CoT 推理链与工具调用交替机制（Thought → Action → Observation 循环）
- **Plan-and-Execute**：先分解任务生成计划，再逐步执行并修正计划闭环
- **Sub-Agent**：主 Agent 派发子任务给子 Agent，结果聚合
- 三种范式的适用场景与优缺点

**QwenPaw 源码对照**：
- `src/qwenpaw/modes/base.py` —— Agent Loop 的基类，定义循环骨架
- `src/qwenpaw/modes/goal/` —— Goal Mode（目标导向循环）的完整实现：`goal_mode.py`、`gates.py`（审批门控）、`state.py`（状态机）
- `src/qwenpaw/agents/tools/delegate_external_agent.py` —— Sub-Agent 委托机制

**实战任务**：
- 用纯 Python（不依赖框架）实现一个 ReAct Agent，能调用计算器与搜索工具
- 改造为 Plan-and-Execute 模式，对比两者在多步任务上的表现

**参考资料**：ReAct 原论文；Plan-and-Solve 论文。

---

#### 模块 2.2 · Function Calling / Tool Calling

**学习目标**：精通工具调用机制，能设计健壮的工具体系。

**知识点**：
- Function Calling 协议：参数 Schema（JSON Schema）、工具描述、返回格式
- 工具设计：输入输出 Schema、鉴权、超时、重试、幂等
- 批量工具调用（parallel tool calls）与结果聚合
- 工具调用失败时的异常处理与降级

**QwenPaw 源码对照**：
- `src/qwenpaw/agents/tools/` —— 20+ 真实工具实现：
  - `shell.py`、`file_io.py`、`file_search.py` —— 系统工具
  - `web_search.py`、`browser_control.py` —— 信息获取工具
  - `run_tool_batch.py` —— 批量并发调用
  - `ast_tool.py`、`lsp_tool.py` —— 代码理解工具（AST、LSP）
- `src/qwenpaw/tool_calls/` —— 工具调用协议层

**实战任务**：
- 为你的 Agent 实现 5 个工具（搜索、计算、读文件、写文件、查时间），定义标准 Schema
- 实现批量并发调用 + 超时重试

**参考资料**：OpenAI Function Calling 文档；MCP 工具规范。

---

#### 模块 2.3 · Agent Loop 智能循环机制

**学习目标**：理解 Agent Loop 的执行模型，能解决断连、无效循环、执行失控等核心问题。

**知识点**：
- 同步循环 vs 异步事件驱动两种 Loop 执行模型
- 任务自主迭代、中断恢复、异常重试、主动思考纠偏
- 防失控：最大步数限制、循环检测、成本上限
- 可组合审批门控（approval gates）：在关键步骤插入人工审批

**QwenPaw 源码对照**（这是 QwenPaw 2.0 的核心亮点）：
- `src/qwenpaw/modes/base.py` —— Loop Engineering 基类
- `src/qwenpaw/modes/coding/` —— Coding Mode（代码循环）：`hooks.py`、`mixin.py`
- `src/qwenpaw/modes/mission/` —— Mission Mode（任务循环）：`gates.py`（审批门控）、`hooks.py`、`state.py`、`contributor.py`
- `src/qwenpaw/modes/goal/gates.py` —— Goal Mode 的门控设计
- `src/qwenpaw/app/approvals/` —— 审批流程服务

**实战任务**：
- 为你的 Agent Loop 实现"最大步数 + 成本上限 + 重复检测"三重防失控
- 实现一个可配置的审批门控：危险操作前暂停等待人工确认

**参考资料**：QwenPaw 文档「Loop Engineering」章节；AgentScope 文档。

---

#### 模块 2.4 · 上下文与记忆管理

**学习目标**：掌握上下文窗口管理与长短期记忆机制。

**知识点**：
- 上下文窗口管理：Token 预算、上下文逐出（eviction）、压缩 vs 保留
- 短期记忆（工作上下文）vs 长期记忆（蒸馏知识）
- 记忆检索：向量检索、按使用感知排序、相关性召回
- 记忆一致性：多 Agent 共享记忆的并发问题

**QwenPaw 源码对照**（QwenPaw 的招牌能力）：
- `src/qwenpaw/agents/context/` —— Scroll Context（滚动上下文）：`base.py`、`types.py`，每轮持久化、逐出后可回放
- `src/qwenpaw/agents/memory/` —— ReMe v0.4.0 长期记忆：
  - `base_memory_manager.py` —— 记忆管理基类
  - `reme_light_memory_manager.py` —— 轻量记忆实现
  - `reme_config.py` —— 记忆配置
  - `adbpg_memory_manager.py` —— 基于 PG 的记忆后端
  - `agent_md_manager.py` —— Agent 知识文件管理

**实战任务**：
- 实现一个滑动窗口上下文管理器：超过 Token 上限时逐出最旧轮次，但保留摘要
- 接入一个向量库（Chroma / Qdrant），实现长期记忆的存储与召回

**参考资料**：QwenPaw 文档「Context」「Memory」章节；ReMe 项目。

---

#### 模块 2.5 · Agent 框架实践

**学习目标**：掌握主流 Agent 框架，理解其架构与优缺点。

**知识点**：
- **LangChain / LangGraph**：Chain、Agent、Tool、Memory 模块；LangGraph 的图状态机
- **LlamaIndex**：RAG 框架，数据连接 + 索引 + 查询
- **AutoGen**：多 Agent 对话框架
- 框架对比：抽象层级、灵活性、生产可用性

**QwenPaw 源码对照**：
- QwenPaw 基于 AgentScope 2.0 构建，是"不依赖 LangChain 的生产级 Agent 框架"范例
- 对比 QwenPaw 的 `modes/` 与 LangGraph 的图编排，理解两种设计哲学

**实战任务**：
- 用 LangGraph 重写阶段 2.1 的 ReAct Agent，对比自研与框架的差异
- 用 LlamaIndex 搭建一个文档问答 RAG

**参考资料**：LangChain / LangGraph 文档；LlamaIndex 文档；AgentScope 文档。

---

### 阶段三 · MCP 与工程化（第 8–11 周）

> **阶段目标**：能独立开发 MCP Server，掌握安全沙箱、Multi-Agent 协作与可观测性。
> **QwenPaw 对照**：Agent OS 驱动层（`drivers/`）、Sandbox（`sandbox/`）、Tool Guard（`security/`）、可观测性（`observability/`）。

#### 模块 3.1 · MCP 协议规范

**学习目标**：精通 MCP（Model Context Protocol）核心概念与协议。

**知识点**：
- MCP 核心概念：Tools、Resources、Prompts、Server、Client
- 协议交互：工具发现、能力协商、调用流程
- 与 Function Calling 的关系：MCP 是"工具协议层"，Function Calling 是"模型能力层"
- A2A（Agent-to-Agent）协议入门

**QwenPaw 源码对照**：
- `src/qwenpaw/drivers/` —— 协议中立的连接器层：
  - `contracts.py` —— 协议中立接口定义
  - `manager.py` —— 驱动管理器
  - `capabilities.py` —— 能力发现
  - `adapters/` —— 各协议适配器（MCP / A2A / ACP）
- `src/qwenpaw/app/mcp/` —— MCP 应用层

**实战任务**：
- 通读 MCP 官方规范，画出协议交互时序图
- 在 QwenPaw 中配置一个外部 MCP Client，观察工具发现与调用流程

**参考资料**：MCP 官方规范（modelcontextprotocol.io）；QwenPaw 文档「MCP」章节。

---

#### 模块 3.2 · MCP Server 开发

**学习目标**：能独立开发企业级 MCP Server。

**知识点**：
- MCP Server 开发：工具注册中心、动态工具发现
- 标准化接口协议：输入输出 Schema、鉴权、超时、重试
- 权限管理：工具级粒度权限、来源感知匹配
- 调用审计：调用日志、链路追踪、安全审计

**QwenPaw 源码对照**：
- `src/qwenpaw/drivers/policy.py` + `policy_types.py` —— 逐次调用策略门控
- `src/qwenpaw/drivers/approval.py` —— 审批机制
- `src/qwenpaw/governance/tool_registry.py` —— 工具注册中心
- `src/qwenpaw/governance/tool_adapter.py` —— 工具适配
- `src/qwenpaw/governance/audit.py` —— 调用审计

**实战任务**：
- 开发一个 MCP Server，把企业内部系统（如 Jira / GitLab）能力封装为 MCP 工具
- 实现工具注册、动态发现、权限校验、调用审计完整链路

**参考资料**：MCP SDK（Python / TypeScript）；QwenPaw MCP 示例。

---

#### 模块 3.3 · 安全沙箱执行

**学习目标**：掌握 Agent 执行隔离与安全防护。

**知识点**：
- 内核级沙箱：macOS Seatbelt、Linux Bubblewrap/Landlock、Windows AppContainer
- Tool Guard：命令注入检测、路径遍历、反向 Shell、混淆攻击
- File Guard：敏感文件/目录访问控制
- Skill Scanner：激活前扫描，检测提示词注入、硬编码密钥、数据外泄
- Access Policy：声明式策略，allow / deny / ask / sandbox

**QwenPaw 源码对照**（QwenPaw 安全体系是四层防护）：
- `src/qwenpaw/sandbox/` —— 内核级沙箱：
  - `macos_sandbox.py`（Seatbelt）、`bubblewrap_sandbox.py`、`linux_sandbox.py`、`windows_sandbox.py`（AppContainer）
  - `local_sandbox.py`、`config.py`
- `src/qwenpaw/security/tool_guard/` —— 工具调用守护：
  - `engine.py` —— YAML 规则引擎
  - `guardians/shell_evasion_guardian.py` —— Shell 注入检测
  - `guardians/file_guardian.py` —— 文件访问守护
  - `guardians/rule_guardian.py` —— 规则守护
  - `execution_level.py` —— STRICT / SMART / AUTO / OFF 四级
  - `approval.py` —— 审批
- `src/qwenpaw/security/skill_scanner/` —— Skill 扫描：
  - `scanner.py`、`analyzers/pattern_analyzer.py`、`scan_policy.py`
- `src/qwenpaw/governance/policy.py` —— Access Policy 声明式策略
- `src/qwenpaw/governance/detectors.py` —— 风险检测器

**实战任务**：
- 配置 QwenPaw 的 Access Policy，实现 allow / deny / ask 三类策略
- 分析 `shell_evasion_guardian.py` 的规则，理解命令注入检测逻辑
- 自己写一条 Tool Guard 规则，拦截某种攻击模式

**参考资料**：macOS Seatbelt 文档；Linux Bubblewrap 文档；QwenPaw 文档「Security」章节。

---

#### 模块 3.4 · Multi-Agent 协作

**学习目标**：掌握多智能体协作与跨系统编排。

**知识点**：
- Multi-Agent 通信协议：消息传递、共享内存、黑板模式
- 上下文隔离与结果聚合
- 子 Agent 生命周期管理（创建 / 调度 / 暂停 / 恢复 / 销毁）
- ACP（Agent Communication Protocol）跨系统编排

**QwenPaw 源码对照**：
- `src/qwenpaw/agents/acp/` —— ACP 协议实现
- `src/qwenpaw/agents/tools/agent_management.py` —— 多 Agent 管理工具
- `src/qwenpaw/agents/tools/delegate_external_agent.py` —— 外部 Agent 委托
- `src/qwenpaw/app/channels/` —— 多频道（钉钉/飞书/微信等）作为多 Agent 协作入口

**实战任务**：
- 搭建一个 2-Agent 协作场景：Agent A 负责信息收集，Agent B 负责分析，跑通结果聚合
- 用 QwenPaw 创建多个 Agent，观察它们的独立记忆与技能

**参考资料**：QwenPaw 文档「Multi-Agent」「ACP Integration」章节；A2A 协议规范。

---

#### 模块 3.5 · 可观测性体系

**学习目标**：构建 Agent 执行的可观测性体系。

**知识点**：
- Trace 链路追踪：OpenTelemetry、单次 Agent 运行的全链路追踪
- Token 消耗监控：按会话/按工具/按模型统计
- 执行耗时分析：每步耗时、瓶颈定位
- 异常告警：失败率、超时、成本异常

**QwenPaw 源码对照**：
- `src/qwenpaw/observability/langfuse.py` —— Langfuse 集成
- `src/qwenpaw/token_usage/` —— Token 消耗统计
- `src/qwenpaw/agent_stats/` —— Agent 运行统计
- `src/qwenpaw/hooks/observability/` —— 可观测性 Hook
- `src/qwenpaw/hooks/error/` —— 错误处理 Hook

**实战任务**：
- 为你的 Agent 接入 OpenTelemetry，实现一次完整调用的链路追踪
- 实现 Token 消耗的按工具统计与成本告警

**参考资料**：OpenTelemetry 文档；Langfuse 文档；Prometheus / Grafana。

---

### 阶段四 · 平台架构与落地（第 12–15 周）

> **阶段目标**：具备平台级架构设计能力，能把 AI Coding 融入全流程，产出可上线的生产级服务。
> **QwenPaw 对照**：Skills 体系（`agents/skill_system/`）、Plugin Market（`market/`）、编排（`modes/`）。

#### 模块 4.1 · Agent 编排引擎

**学习目标**：设计并实现 Agent 编排引擎。

**知识点**：
- 可视化 DAG 编排：节点 / 边 / 数据流
- 动态代码编排：运行时生成与执行编排逻辑
- Skills 技能体系：注册发现、版本管理、热插拔、能力市场
- 标准化接口协议：输入输出 Schema、依赖管理

**QwenPaw 源码对照**：
- `src/qwenpaw/agents/skill_system/` —— Skills 技能体系
- `src/qwenpaw/agents/skills/` —— 内置技能实现
- `src/qwenpaw/market/` —— Plugin Market（插件市场）
- `src/qwenpaw/agents/hooks/` —— 技能生命周期 Hook
- `src/qwenpaw/modes/` —— Loop 模板即一种编排范式

**实战任务**：
- 设计一个 DAG 编排引擎，支持节点拖拽与数据传递
- 实现一个 Skills 注册中心，支持版本管理与热插拔

**参考资料**：Dify / Coze 编排设计；QwenPaw 文档「Skills」「Plugins」章节。

---

#### 模块 4.2 · 低代码平台实践

**学习目标**：理解主流低代码 Agent 平台的能力与场景。

**知识点**：
- Dify：开源 LLM 应用开发平台，工作流编排
- Coze：字节扣子，Bot + 插件 + 工作流
- 百炼：阿里云企业级 Agent 平台
- 三者能力对比与适用场景

**实战任务**：
- 在 Dify 上搭建一个带 RAG 的工作流 Agent
- 对比 Dify 与 QwenPaw 的编排能力，写出差异分析

**参考资料**：Dify / Coze / 百炼官方文档。

---

#### 模块 4.3 · 后端架构与高可用

**学习目标**：掌握 Agent 平台的后端架构设计。

**知识点**：
- 消息队列：Kafka / RocketMQ，消息可靠性投递、延迟消息、事务消息
- Redis 进阶：Stream 消息、Pub/Sub、分布式锁
- 数据库：MySQL / PostgreSQL 索引原理、事务隔离、分库分表
- 高可用设计：多活 / 容灾 / 降级 / 限流熔断
- 插件化架构与 SPI 扩展机制

**QwenPaw 源码对照**：
- `src/qwenpaw/app/crons/` —— 定时任务（消息调度）
- `src/qwenpaw/runtime/commands/` —— 运行时命令
- `src/qwenpaw/governance/resource_governor.py` —— 资源治理

**实战任务**：
- 设计一个支持 10 万 QPS 的 Agent 调用架构（画架构图 + 关键技术选型）
- 用 Kafka 实现异步任务队列，处理 Agent 长任务

**参考资料**：Kafka 权威指南；《数据密集型应用系统设计》。

---

#### 模块 4.4 · 流量治理

**学习目标**：掌握 Agent 级别的流量治理设计。

**知识点**：
- Token 级 / QPS 级限流
- 熔断降级：Hystrix / Sentinel 思想
- 队列缓冲：突发流量削峰
- 灰度发布与 A/B 测试

**实战任务**：
- 为你的 Agent 服务实现 Token 级限流（每用户每小时 Token 上限）
- 设计一个灰度发布方案，按用户 ID 哈希分流

**参考资料**：Sentinel 文档；限流算法（令牌桶 / 漏桶）。

---

#### 模块 4.5 · DevOps + AI Coding 全流程

**学习目标**：掌握容器化部署与 AI Coding 全流程融入。

**知识点**：
- Docker / K8s 容器化编排
- CI/CD 流水线（GitHub Actions / GitLab CI）
- AI Coding 全流程：需求 Spec → 头脑风暴 → 架构设计 → AI 辅助编码 → AI 生成测试
- Vibe Coding 工具：Cursor、Claude Code、Codex、通义灵码、Trae
- Spec-Driven Development 与 Context Engineering

**QwenPaw 源码对照**：
- `docker-compose.yml`、`Dockerfile` —— QwenPaw 的容器化部署范例
- `scripts/` —— 部署与构建脚本
- `e2e/` —— 端到端测试
- `Makefile` —— 构建编排

**实战任务**：
- 为你的 Agent 服务写 Dockerfile + docker-compose，一键部署
- 用 Cursor / Claude Code 完整交付一个功能模块，记录"AI 全流程"的效率提升
- 搭建 GitHub Actions CI/CD，实现自动测试与部署

**参考资料**：Docker / K8s 官方文档；Cursor / Claude Code 文档。

---

## 四、QwenPaw 源码实战地图

> 按 QwenPaw 源码目录组织，作为"边学边读源码"的精读指南。建议按学习阶段顺序精读。

### 4.1 Loop Engineering（Agent 循环）— 阶段二精读

| 源码路径 | 对应学习模块 | 精读重点 |
|----------|------------|----------|
| `src/qwenpaw/modes/base.py` | Agent Loop 基类 | 循环骨架、状态流转 |
| `src/qwenpaw/modes/mission/gates.py` | 审批门控 | 可组合门控设计 |
| `src/qwenpaw/modes/mission/state.py` | 状态机 | 任务状态管理 |
| `src/qwenpaw/modes/coding/hooks.py` | Coding Mode | 代码循环的 Hook 机制 |
| `src/qwenpaw/modes/goal/goal_mode.py` | Goal Mode | 目标导向循环 |

**实战**：阅读 `mission/gates.py`，实现一个自定义审批门控（如"金额超 100 元需人工确认"）。

### 4.2 驱动层（MCP/A2A/ACP）— 阶段三精读

| 源码路径 | 对应学习模块 | 精读重点 |
|----------|------------|----------|
| `src/qwenpaw/drivers/contracts.py` | 协议中立接口 | 抽象设计 |
| `src/qwenpaw/drivers/manager.py` | 驱动管理 | 生命周期管理 |
| `src/qwenpaw/drivers/policy.py` | 策略门控 | 逐次调用策略 |
| `src/qwenpaw/drivers/adapters/` | 协议适配器 | MCP/A2A/ACP 适配 |
| `src/qwenpaw/app/mcp/` | MCP 应用层 | Server/Client 实现 |

**实战**：开发一个 MCP Server 接入 QwenPaw，验证工具动态发现与权限门控。

### 4.3 记忆与上下文 — 阶段二精读

| 源码路径 | 对应学习模块 | 精读重点 |
|----------|------------|----------|
| `src/qwenpaw/agents/context/base.py` | Scroll Context | 滚动上下文、逐出与回放 |
| `src/qwenpaw/agents/memory/base_memory_manager.py` | 记忆基类 | 记忆接口抽象 |
| `src/qwenpaw/agents/memory/reme_light_memory_manager.py` | 轻量记忆 | 记忆实现 |
| `src/qwenpaw/agents/memory/reme_config.py` | 记忆配置 | 后端特定嵌入 |

**实战**：理解三层记忆结构，实现按使用感知的自定义召回。

### 4.4 安全与治理 — 阶段三精读

| 源码路径 | 对应学习模块 | 精读重点 |
|----------|------------|----------|
| `src/qwenpaw/sandbox/macos_sandbox.py` | Seatbelt 沙箱 | 内核级隔离 |
| `src/qwenpaw/security/tool_guard/engine.py` | Tool Guard 引擎 | YAML 规则引擎 |
| `src/qwenpaw/security/tool_guard/guardians/shell_evasion_guardian.py` | Shell 注入检测 | 攻击检测逻辑 |
| `src/qwenpaw/security/skill_scanner/scanner.py` | Skill 扫描 | 激活前扫描 |
| `src/qwenpaw/governance/policy.py` | Access Policy | 声明式策略 |

**实战**：配置 allow/deny/ask 策略，分析命令注入拦截规则。

### 4.5 工具与多智能体 — 阶段二/三精读

| 源码路径 | 对应学习模块 | 精读重点 |
|----------|------------|----------|
| `src/qwenpaw/agents/tools/` | 工具实现 | 20+ 真实工具范例 |
| `src/qwenpaw/agents/tools/run_tool_batch.py` | 批量调用 | 并发执行 |
| `src/qwenpaw/agents/tools/agent_management.py` | 多 Agent 管理 | 生命周期 |
| `src/qwenpaw/agents/tools/delegate_external_agent.py` | 子 Agent 委托 | Sub-Agent |
| `src/qwenpaw/agents/acp/` | ACP 协议 | 跨系统编排 |

### 4.6 可观测性与计费 — 阶段三精读

| 源码路径 | 对应学习模块 | 精读重点 |
|----------|------------|----------|
| `src/qwenpaw/observability/langfuse.py` | 链路追踪 | Langfuse 集成 |
| `src/qwenpaw/token_usage/` | Token 统计 | 消耗监控 |
| `src/qwenpaw/agent_stats/` | 运行统计 | 指标采集 |
| `src/qwenpaw/hooks/observability/` | 可观测 Hook | Hook 机制 |

### 4.7 平台扩展 — 阶段四精读

| 源码路径 | 对应学习模块 | 精读重点 |
|----------|------------|----------|
| `src/qwenpaw/agents/skill_system/` | Skills 体系 | 注册/版本/热插拔 |
| `src/qwenpaw/market/` | Plugin Market | 插件市场 |
| `src/qwenpaw/app/channels/` | 多频道 | 钉钉/飞书/微信接入 |
| `src/qwenpaw/providers/` | 模型供应商 | 14+ 供应商统一封装 |
| `src/qwenpaw/app/crons/` | 定时任务 | 调度与自动化 |

---

## 五、阶段性产出与简历沉淀

> 每阶段产出一个可演示 Demo，是证明"工程落地能力"（而非"只会调 API"）的关键。

### 阶段一产出：LLM 服务脚手架
- 一个 FastAPI 服务，支持多模型切换、SSE 流式输出、Token 统计
- 简历亮点：**"基于 asyncio 实现高并发 LLM 网关，统一封装 3+ 模型 API"**

### 阶段二产出：自研 Agent
- 一个支持 ReAct、Tool Calling、记忆、防失控的 Agent
- 简历亮点：**"自研 Agent Loop，支持同步/异步执行、中断恢复、审批门控"**

### 阶段三产出：MCP Server + 安全体系
- 一个企业级 MCP Server（封装内部系统）+ 安全沙箱配置
- 简历亮点：**"开发 MCP Server，实现工具注册/权限/审计；配置四层安全防护"**

### 阶段四产出：可上线 Agent 平台
- 一个带编排、限流、CI/CD 的 Agent 平台 Demo
- 简历亮点：**"设计 Agent 编排引擎，支持 DAG 编排与流量治理；AI Coding 全流程交付"**

---

## 六、学习资源清单

### 6.1 官方文档与规范
- QwenPaw 文档：https://qwenpaw.agentscope.io/docs
- MCP 协议规范：https://modelcontextprotocol.io
- LangChain / LangGraph 文档
- OpenTelemetry 可观测性文档

### 6.2 开源项目精读
- **QwenPaw**：https://github.com/agentscope-ai/QwenPaw （本计划主线）
- **AgentScope**：https://github.com/agentscope-ai/agentscope （QwenPaw 底座）
- **ReMe**：https://github.com/agentscope-ai/ReMe （长期记忆）
- **Dify**：开源 LLM 应用平台
- **LangGraph**：图状态机 Agent 框架
- **AutoGen**：多 Agent 对话框架

### 6.3 模型 API 实践
- Qwen（DashScope）/ DeepSeek / Claude / OpenAI
- 本地模型：Ollama / LM Studio / llama.cpp

### 6.4 AI Coding 工具
- Cursor、Claude Code、Codex、通义灵码、Trae、GitHub Copilot

---

## 附录：岗位—能力—阶段对照矩阵

| 能力维度 | 阶段一 | 阶段二 | 阶段三 | 阶段四 | 重点对标岗位 |
|----------|:------:|:------:|:------:|:------:|------------|
| Python 异步 / FastAPI | ■ | | | | 可孚医疗、锦碟云 |
| LLM API / Prompt | ■ | | | | 全部 |
| Agent 架构与范式 | | ■ | | | 高伟达、可孚医疗、星财富 |
| Tool Calling | | ■ | | | 高伟达、可孚医疗 |
| Agent Loop / 记忆 | | ■ | | | 高伟达、可孚医疗 |
| MCP 协议 / Server | | | ■ | | 软帝联合、高伟达、卡比特 |
| 安全沙箱 | | | ■ | | 高伟达、卡比特 |
| Multi-Agent / ACP | | | ■ | | 高伟达 |
| 可观测性 | | | ■ | | 高伟达、卡比特 |
| Agent 编排引擎 | | | | ■ | 高伟达、云启智慧 |
| 低代码平台 | | | | ■ | 云启智慧 |
| 后端架构 / 高可用 | | | | ■ | 高伟达、浩鲸科技 |
| 流量治理 | | | | ■ | 高伟达 |
| DevOps / AI Coding | | | | ■ | 浩鲸科技、云炎科技 |
| RAG / 向量检索 | ■ 基础 | ■ 应用 | | | 锦碟云、星财富、云启智慧 |

> ■ 表示该能力在该阶段重点学习。

---

**最后提醒**：这份计划的灵魂是"以 QwenPaw 为参照系，边学边读源码边动手"。岗位要的不是"会调 API 的人"，而是"能把 Agent 能力工程化落地的人"。每读完一个 QwenPaw 模块，就动手实现它的最小版本——这才是真正能拿到 offer 的路径。
