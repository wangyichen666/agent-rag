# W12 · 多 Agent 协作平台实战（下）· 毕业交付

> 本周目标 | 把 W10 治理 + W09 Runtime 加进毕业项目，加 Token 监控 + trace + Docker，达到「能讲成简历项目」的完成度。
> JD 考点：工程化与流量治理、可观测性、容器化部署、企业级落地——12 周总收口。

## 1. 本周你将搞懂什么

W11 你搭了"能跑"的骨架。但"能跑"和"能讲成简历项目"差着三个工程化层：**治理**（别让 Agent 失控）、**可观测**（知道发生了什么）、**部署**（能交付运行）。本周把这三层加进去，再把整个项目讲成一段 5 分钟的话术。

这是 12 周的总收口：W01-W03 的地基、W04-W08 的框架、W09-W12 的产品，全部汇聚到这一个项目里。

## 2. 原理铺垫（收口设计）

### 2.1 把哪些"零件"装进毕业项目

```
研究+写作+审校 多 Agent 平台（W11 骨架）
  + [W10] Stop Gate（BudgetGate + DoomLoopGate）→ 防 Agent 烧钱/死循环
  + [W10] 审批（危险操作人在回路）→ reviewer 改稿前可人工确认
  + [W09] 迷你 Runtime + Envelope → 工业级 SSE 流式接口
  + [W07/W10] Token 监控 + Trace → 知道每次回答烧了多少、链路如何
  + [W12] Docker + README + 架构图 → 可交付运行
  + [W12] 面试话术 → 能讲清
```

### 2.2 治理为什么必须有

没有 BudgetGate，用户问个复杂问题，researcher 反复检索 + writer 反复改稿，一轮烧 50 万 token 你都不知道。没有 DoomLoopGate，writer 陷入"改→审→改"死循环。这两个 gate 直接对应 JD"Agent Loop 治理"。

### 2.3 可观测性的最小闭环

- **Token**：`TokenRecordingModelWrapper`（W10）记每次模型调用 token，按 Agent 聚合。
- **Trace**：TracingMiddleware（W07）or Langfuse（W10），一次 user 请求 → leader → 3 worker 的调用链可可视。
- **审计**：MCP Server 的 AUDIT（W11）+ 工具调用日志。

## 3. 源码精读（参考，绝对路径）

本周主要是组装前几周的成果，参考点：

- **Stop Gate 怎么挂**：QwenPawAgent `_reasoning`（`react_agent.py:366`）是 gate 接入点；你的各 worker Agent 用 W10 作业 1 的中间件 gate 思路挂上。
- **审批接在哪**：`app/approvals/service.py:72` 的 `ApprovalService` + 框架 `REQUIRE_USER_CONFIRM` 事件。简化版：reviewer 给出"高危修改建议"时，Leader 暂停等人确认。
- **Token 监控**：`token_usage/model_wrapper.py:15` 的 `TokenRecordingModelWrapper` 包装你的 model。
- **Trace**：`middleware/_tracing/_trace.py:116` 的 `TracingMiddleware` 挂 Leader。
- **Runtime/Envelope**：W09 作业的 MiniRuntime/Envelope 包整个流程。
- **Docker**：参考 QwenPaw `deploy/Dockerfile` 写法（多阶段构建）。

## 4. 动手作业

放 `code/w12/`。这是收口交付。

### 作业 1：加 Stop Gate + 审批

给 W11 的三个 worker 都挂 W10 的 `RepeatToolGate` + 一个 `BudgetGate`（单 Agent 总 token 超 5 万就停）。给 Leader 加审批：reviewer 评分低于 6 时，"是否让 writer 按建议大改"暂停等人输入（用 `REQUIRE_USER_CONFIRM` 或简化成 input()）。

```python
# code/w12/governed_agents.py（在 W11 基础上增量）
# 1. BudgetGate: 包装 model，累计 token 超限抛 StopIteration 式停止
class BudgetGate(MiddlewareBase):
    def __init__(self, budget=50000):
        self.budget, self.used = budget, 0
    async def on_model_call(self, *, agent, input_kwargs, next_handler):
        async for item in next_handler(**input_kwargs):
            yield item
        # 累加该次调用 token（从事件或 msg.usage 取）
        last = agent.state.context[-1] if agent.state.context else None
        u = getattr(last, "usage", None)
        if u:
            self.used += u.input_tokens + u.output_tokens
            if self.used > self.budget:
                print(f"🛑 BUDGET 超限 {self.used}>{self.budget}, 停止 {agent.name}")

# 2. 把 gate 挂到每个 worker
async def build_researcher():
    mcp = ...  # 同 W11
    await mcp.connect()
    tools = await mcp.list_tools()
    return Agent(name="researcher", system_prompt="...",
                 model=make_model(), toolkit=Toolkit(tools=tools),
                 middlewares=[RepeatToolGate(3), BudgetGate(50000)])

# 3. Leader 评分低时审批(简化版)
score = parse_score(reviewer_result)  # 从 reviewer 输出抽分数
if score < 6:
    ans = input(f"评分仅 {score}，是否让 writer 大改？(y/n) ")  # 生产用 ApprovalService
    if ans == "y":
        await writer.reply(...)  # 再改一轮
```

**预期**：超预算/死循环时 gate 触发停止；低分时暂停待人确认。这就是"治理 + 人在回路"。

### 作业 2：Token 监控 + Trace

用 `TokenRecordingModelWrapper`（或自写简化版）包 model，跑一次完整请求，打印各 Agent token 汇总。给 Leader 挂 `TracingMiddleware`，导出一次 trace（控制台打印 span 树即可，有 Langfuse 环境更好）。

### 作业 3：Docker 化 + README + 架构图

`code/w12/Dockerfile`（多阶段，仿 QwenPaw `deploy/`）：

```dockerfile
# code/w12/Dockerfile
FROM python:3.12-slim AS base
WORKDIR /app
RUN pip install --no-cache-dir uv
COPY . .
RUN uv pip install --system "agentscope==2.0.4" mcp fastapi uvicorn httpx
EXPOSE 8088
CMD ["python", "app/main.py"]   # FastAPI + SSE 入口
```

`code/w12/README.md`：写清——项目是什么、架构图（文字版：角色/通信/MCP/治理）、怎么跑（docker build/run）、用了 agentscope 2.0 哪些能力、与 QwenPaw 的借鉴关系、已知局限。

### 作业 4：5 分钟讲清这个项目（话术稿）

`code/w12/讲稿.md`，按这个结构写：

```
1. 一句话定位：基于 agentscope 2.0 的研究-写作-审校多 Agent 协作平台
2. 为什么这样设计：Leader-Worker 动态调度(对比 1.0 代码 pipeline 的局限)
3. 技术亮点(挑3个深的讲):
   - 自建 MCP Server(注册/schema/鉴权/审计)接 Researcher
   - Loop Engineering(Budget/DoomLoop gate)治失控
   - Runtime+Envelope 把框架流变工业 SSE
4. 踩过的坑 + 怎么解决(对应 W03/W07/W10 三个钉子)
5. 可观测: Token 监控 + Trace + 审计
6. 局限与下一步(诚实)
```

## 5. 毕业交付物清单

- [ ] `multi-agent-platform/` 可运行仓库
  - [ ] 自建 MCP Server（鉴权+审计+沙箱）
  - [ ] Leader + Researcher + Writer + Reviewer（真 Team or 顺序骨架）
  - [ ] Stop Gate（Budget + DoomLoop）+ 审批
  - [ ] Token 监控 + Trace
  - [ ] 迷你 Runtime + SSE 接口
  - [ ] Dockerfile + docker-compose（含 Redis/Qdrant 可选）
  - [ ] README（架构图 + 运行 + 局限）
- [ ] `讲稿.md` 5 分钟话术
- [ ] `改造checklist/qwenpaw-改造清单.md` 里勾掉你做完的改造项

## 6. 面试问答卡（综合）

**Q1：用 5 分钟讲讲你这个项目。**
- 话术骨架见作业 4。核心：定位→设计理由→3 个亮点→踩坑→可观测→局限。**每次讲都按这结构，别发散。**

**Q2：项目里你最难的一个技术点是什么？怎么解的？**
- 参考答案候选（挑你真做的讲）：① Loop 治理——起初只靠 max_iters 治不住死循环，借鉴 QwenPaw `StopGate` 抽象做了 BudgetGate/DoomLoopGate，每种失控一服药；② 上下文治理——researcher 资料太多撑爆，用框架 `compress_context`（SummarySchema 结构化压缩）+ 只传必要产物给下游；③ MCP Server 鉴权审计——从 QwenPaw `app/routers/mcp.py` 学的"策略+白名单+审计"。
- 话术：「挑一个真踩过的坑，讲清现象→根因→解法→为什么这么做。」

**Q3：如果让你把这个平台做成多租户 SaaS，要改什么？**
- 参考答案：MessageBus 换 Redis（`app/message_bus/_redis_message_bus.py`），SessionService 多租户隔离（`app/_service/_session.py`），模型 key/额度按租户配额（Token 监控 + BudgetGate 租户级），MCP Server 鉴权带租户 scope，沙箱按租户隔离。这正是 QwenPaw `MultiAgentManager`（`app/multi_agent_manager.py:23`）+ Redis 的设计。
- 话术：「总线换 Redis、会话多租户隔离、Token 按租户配额、MCP 鉴权带 scope、沙箱隔离。」

**Q4：你的项目和直接用 LangChain/低代码(dify/coze)比，优缺点？**
- 参考答案：优点——agentscope 2.0 源码透明、可深度定制（自建 MCP/自定 gate/扩展 Agent）、不锁死编排；低代码上手快但不透明、难做企业级治理（审计/沙箱/限流）。缺点——自己写工程量大，低代码快。选型看是否要深度可控与企业级治理。
- 话术：「要深度可控+企业治理选自建框架，求快选低代码，我选前者因为要做治理与扩展。」

## 7. 从 1.0 到 2.0 / 避坑（收口）

- 整个项目里，你"没有"用过 `ReActAgent`/`Pipeline`/`MsgHub`/同步 `agent(msg)`——因为你全程 2.0。面试时主动说"我基于 2.0，没用 1.0 那套"，加分。
- 治理、可观测、部署这三层是"框架不直接给、产品必须加"的——你做了，就把"会用框架"和"会做产品"区分开了。
- 话术稿要练到 5 分钟内讲完，别背稿，按结构口语讲。

## 附：本周 checkpoint（毕业验收）

- [ ] 作业 1：BudgetGate + 审批生效
- [ ] 作业 2：Token 监控 + trace 跑出一次完整链路
- [ ] 作业 3：docker build 成功，README 完整
- [ ] 作业 4：5 分钟话术能流畅讲完
- [ ] 交付物清单全勾

---
# 🎓 恭喜，12 周毕业

你从 0-1 年初级，走完了：Python 异步 → LLM API → 手写 ReAct → 吃透 agentscope 2.0 内核/消息/工具/MCP/中间件/记忆/RAG/多Agent → 拆解 QwenPaw 的 Runtime/SSE/Loop治理/沙箱 → 独立交付一个多 Agent 协作平台。

求职时用：`README.md` 的 JD 映射表 + `面试问答卡/` + `讲稿.md`。每个考点都有源码佐证，不是空谈。

后续可深入：A2A/ACP 协议（QwenPaw `agents/acp/`）、Workspace 沙箱后端（Docker/E2B/K8s/OpenSandbox）、RAG 服务化（`app/rag/` index_worker）。但这些是锦上添花，你现在的水平已经能胜任这些 JD 的核心要求了。