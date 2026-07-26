# 面试问答卡 05 · AgentScope 架构设计

> 覆盖：W4 / W9。对应 JD：Agent 智能体平台核心架构、框架架构理解。

---

## Q1：agentscope 2.0 为什么只剩一个 Agent 类？和 1.0 有什么本质区别？

### 【模范回答】

这是 2.0 最核心的设计转变，一句话概括：**从「继承」转向「组合」**。

1.0 时代，框架用类层次来表达不同行为——有 `ReActAgent`（带工具推理）、`DialogAgent`（纯对话）、`UserAgent`（模拟用户）等多个子类，每个子类的行为写死在类里。你想让一个 Agent 的行为变一变，常常得继承重写。多 Agent 编排也是代码级的 `Pipeline`、`MsgHub`。

2.0 把这套推翻了，只剩**一个统一的 `Agent` 类**。为什么？因为框架头一句话就讲透了——**它是「为日益强大的 agentic LLM 而设计」的**。现代大模型自己就会推理、自己就会用工具（你在 W2 见过它纯靠 prompt 就能演绎 ReAct 格式），框架不该再用死板的类层次去规定「你是 ReAct 还是 Dialog」。行为差异应该通过**组合**来表达：一个统一的 Agent，内置 reasoning-acting 循环，你往里 plug 不同的部件，它就是不同 Agent——plug 带工具的 toolkit 它就是 ReAct Agent，plug 记忆中间件它就有长期记忆，plug 治理 gate 它就受管控，plug 不同 model 它就换模型。

具体看构造器，它是个「装配车间」：`Agent(name, system_prompt, model, toolkit, middlewares, state, offloader, model_config, context_config, react_config)`。toolkit 决定能力（什么工具）、middlewares 决定行为（审计/记忆/限流/RAG）、三套 config 决定参数（max_iters/压缩阈值/重试降级）。组合代替继承的好处是：加一个能力 = plug 一个中间件或工具，不用新建子类；能力可任意叠加；可测试可替换。

这个转变和整个开源生态的趋势一致——LangChain 早期也是一堆 Agent 子类，后来也往「组合式」走。本质是：**模型变强了，框架要让位给模型**，自己从「规定行为」退到「提供积木」。

我对这套设计最有体感的点：W3 我手写的 50 行 ReAct 轮子，逻辑上就等于 2.0 的 `Agent._reply_impl` 简化版——一个统一循环，行为靠你喂什么。1.0 把它做成 ReActAgent 子类反而把人框住了，2.0 还原成「一个循环 + 可插拔部件」，更接近本质。

> **要点速记**：① 从继承(1.0 多子类)转向组合(2.0 统一 Agent)；② 设计哲学「为日益强大的 agentic LLM 而设计」——框架让位给模型；③ 构造器是装配车间：toolkit/middlewares/config 决定行为；④ 加能力=plug 部件不用改子类，可叠加可替换；⑤ 与开源生态组合式趋势一致。
>
> **源码佐证**：`Agent`（`agent/_agent.py:100`，`__init__` 装配）；`_reply_impl`（:664，内置循环）；middlewares 按钩子筛选挂载（:170-188）；`agent/__init__.py` 只导出 `Agent`+三 Config，无子类。
>
> **压轴一句话**：2.0 砍掉 ReActAgent/DialogAgent 子类，一个统一 Agent 靠 plug toolkit/middleware/config 表达行为——组合代替继承，因为模型够强了，框架从「规定行为」退到「提供积木」。

---

## Q2：agentscope 的模块怎么划分？框架和产品的边界在哪？

### 【模范回答】

agentscope 2.0 的模块划分是按「Agent 构建所需的每一类积木」来切的，很清晰。我这样记：

核心积木——`agent/`（统一 Agent 类与三套 config）、`message/`（Msg + ContentBlock）、`event/`（事件流）、`model/`（9 个 provider 的模型抽象）、`formatter/`（把统一 Msg 翻译成各 provider 原生格式）、`tool/`（Toolkit/FunctionTool/MCPTool/ToolGroup 工具体系）、`middleware/`（六 hook 洋葱模型中间件）、`permission/`（权限五档）。

能力扩展——`rag/`（知识库：parser/chunker/向量库）、`embedding/`（向量化）、`mcp/`（MCP 客户端）、`skill/`（技能加载）、`workspace/`（沙箱/上下文卸载，支持 Local/Docker/E2B/K8s）、`state/`（Agent 状态）、`credential/`（凭证）、`tts/`（语音）。

服务化——`app/`（FastAPI 服务层：多租户多会话、Team 多 Agent 工具、MessageBus、SSE 路由、RAG 服务化）。

这套划分的逻辑是：**框架只给「积木」**——怎么定义 Agent、消息怎么走、工具怎么调、记忆怎么存、模型怎么接。至于怎么把这些积木组装成「能上线的产品」，框架不管，留给产品层。

**框架和产品的边界**就在这。框架给你 reply_stream、Toolkit、Middleware、SessionService 这些 building blocks；但一个真实产品还要：8 阶段 Runtime（鉴权/限流/审计的阶段化）、SSE 的 Envelope 状态机（碎事件→标准消息→断线重连）、Loop Engineering（死循环/超预算治理）、企业级 governance（策略引擎+审批+沙箱）、多渠道接入（钉钉/飞书/企微）、Token 监控与 Langfuse 可观测性、技能系统——这些框架不自带，要产品自己加。

QwenPaw 就是这套「加层」的完整范本。它继承框架的 `Agent` 做成 `QwenPawAgent`（在每个关键环节加料：重写 compress_context 用 Scroll 策略、重写 _reasoning 接停止门控、重写 state_dict 做持久化和迁移），再加 Runtime/Envelope/Loop/governance/sandbox 一整圈。**框架提供块，产品把块组装+加厚成 OS**——这就是边界，也是 JD 里「平台核心架构设计」要回答的东西。

> **要点速记**：① 模块按「积木类」切——核心(agent/message/event/model/formatter/tool/middleware/permission)+能力(rag/embedding/mcp/skill/workspace)+服务化(app)；② 框架只给积木，不管怎么组装成产品；③ 产品要加 Runtime/Envelope/Loop治理/governance/沙箱/多渠道/监控——框架不自带；④ QwenPaw 继承 Agent 加料 + 加一圈工程层 = 完整范本。
>
> **源码佐证**：各模块 `__init__.py`；产品加层参考 QwenPaw `runtime/`(8阶段)、`loop/`(gates)、`governance/`、`sandbox/`、`agents/react_agent.py:47`(QwenPawAgent 扩展 Agent)。
>
> **压轴一句话**：框架按积木类分模块只给 building blocks，产品在框架之上加 Runtime/SSE状态机/Loop治理/沙箱/多渠道/监控这圈工程层——框架提供块，产品加厚成 OS，QwenPaw 是范本。