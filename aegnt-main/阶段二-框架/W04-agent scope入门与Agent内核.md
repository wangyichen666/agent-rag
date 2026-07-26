# W04 · AgentScope 入门与 Agent 内核

> 本周目标 | 跑通 quickstart，读透 `Agent` 内核，理解 2.0 为什么只剩一个统一的 Agent 类。
> JD 考点：Agent 运行时、推理循环（ReAct）、框架架构设计。

## 1. 本周你将搞懂什么

W03 你手写了 50 行 ReAct。现在把那个轮子和 agentscope 2.0 对照着看：框架替你做了什么、在哪做的、留了什么扩展点。

本周只啃一个文件——`src/agentscope/agent/_agent.py`（2837 行，核心中的核心）。读完你会理解：为什么 2.0 砍掉了 1.0 的所有子类，只剩一个 `Agent`。

## 2. 原理铺垫：2.0 的设计哲学

1.0 时代：`ReActAgent`、`DialogAgent`、`UserAgent` 各是各的子类，行为写死在类里。想改一点只能继承重写。

2.0 哲学：**现代 LLM 自己就会推理和用工具**（你在 W02 见过它"演"ReAct）。框架不该用类层次去规定行为，而该：

- 提供一个**统一的 `Agent`**，内置 reasoning-acting 循环；
- 行为差异通过**组合**（plug 进不同的 model / toolkit / middlewares / config）来表达，而不是继承。

所以 2.0 的 `Agent` 构造器是个"装配车间"，———— plug 进去什么，它就是什么 Agent：

```python
Agent(
    name, system_prompt, model,
    toolkit=...,        # ← plug 不同工具 = 不同能力
    middlewares=...,    # ← plug 不同中间件 = 不同行为(记忆/审计/限流...)
    react_config=...,   # ← 调循环参数
    context_config=..., # ← 调上下文压缩
)
```

这和 1.0 的"写死子类"是本质区别。组合 > 继承，是 2.0 的核心心法。

## 3. 源码精读

### 3.1 构造与装配（`_agent.py:100`）

`Agent.__init__`（`:100`）签名已确认：

```
name, system_prompt, model, toolkit?, middlewares?, state?, offloader?,
model_config?, context_config?, react_config?
```

注意 `:170-188`：middlewares 不是一股脑全挂，而是按 `is_implemented("on_xxx")` **筛选**到六个列表里——只实现了 `on_reasoning` 的中间件只在推理时跑，实现了 `on_model_call` 的只在调模型时跑。这就是后面 W07 的"洋葱模型"基础。

### 3.2 三个入口方法（`:194 / :225 / :266`）

| 方法 | 行号 | 作用 |
|---|---|---|
| `reply_stream(inputs)` | `:194` | **核心**：异步生成器，边跑边吐 `AgentEvent`。2.0 的主力入口 |
| `reply(inputs)` | `:225` | 消费整个流，返回最终 `Msg`（阻塞到完成） |
| `observe(msgs)` | `:266` | 只把消息塞进 context，不触发回复（"观察"） |

`reply_stream` 内部就是 `async for chunk in self._reply(...): if not isinstance(chunk, Msg): yield chunk`（`:221`）——把 `_reply` 里的事件吐出来，把最终的 `Msg` 留给 `reply()` 用。

### 3.3 内核循环 `_reply_impl`（`:664`）

这是 W03 那 50 行轮子的"豪华版"，精确对应关系：

```
_reply_impl (:664):
  while 未结束 and iter < max_iters:
      action = _check_next_action()        # :2542  ← 你W03的"还要不要调工具"
      if action == "reasoning":
          await compress_context()         # :759   ← W07上下文压缩
          yield from _reasoning()          # :763   ← 你W03的"调模型"
          batches = _batch_tool_calls()
          yield from _execute_sequential_tool_calls()   # :1375  ← 你W03的"执行工具"
          # 或 _execute_concurrent_tool_calls()        # :1425
      else: break
  yield ReplyEndEvent(...)
```

你 W03 写的 `for i in range(max_iters)` ≈ 这里的循环；你的"tool_calls 为空就结束"≈ `_check_next_action`；你的"执行 + 回填"≈ `_execute_*_tool_calls`。

框架多出来的（你 W03 没做、框架替你做了）：
- **并发分批**：多个工具调用按 `is_concurrency_safe` 分 sequential/concurrent 两批（`:1375/:1425`）。
- **压缩**：每轮推理前 `compress_context()`（`:759`），防上下文爆炸。
- **事件流**：每个阶段 yield 事件（`ReplyStartEvent` / `TextBlockDeltaEvent` / `ToolCallEndEvent` …），UI 能实时渲染。
- **人在回路/中断**：`RequireUserConfirmEvent`、`UserInterruptEvent` 等。

### 3.4 三个 Config（`agent/_config.py`）

| Config | 行号 | 关键字段 |
|---|---|---|
| `ContextConfig` | `:51` | `trigger_ratio=0.8`（超 80% 上下文就压缩）、`reserve_ratio=0.1`（留 10%）、`tool_result_limit=50000`（工具结果超 5 万 token 截断）、`summary_schema`/`summary_template`（结构化压缩模板） |
| `ReActConfig` | `:123` | `max_iters`（默认 20，循环上限）、`stop_on_reject`、`interruption_message` |
| `ModelConfig` | `:164` | `max_retries`、`fallback_model`（主模型挂了切备模型） |

### 3.5 SummarySchema（`_config.py:9`）

上下文压缩时用模型生成结构化摘要，五个字段：`task_overview` / `current_state` / `important_discoveries` / `next_steps` / `context_to_preserve`。W07 会精读，本周知道"压缩不是简单截断，而是结构化总结"即可。

### 3.6 不花钱学用法：`tests/agent_basic_test.py`

源码里这个测试文件用 `MockModel`/`MockTool` 假数据测 Agent，**不调真 API**。e YAGNI：想读内核又舍不得 token，就照着它改写示例。

## 4. 动手作业

放 `code/w04/`。

### 作业 1：跑通 quickstart + 看懂事件流

`code/w04/quickstart.py`：

```python
# code/w04/quickstart.py
# 目标：用 agentscope 2.0 跑最小 Agent，观察事件流事件的种类
import asyncio
import os

from agentscope.agent import Agent, ReActConfig
from agentscope.credential import DashScopeCredential
from agentscope.event import EventType
from agentscope.message import UserMsg
from agentscope.model import DashScopeChatModel
from agentscope.tool import Bash, Read, Toolkit


async def main():
    model = DashScopeChatModel(
        credential=DashScopeCredential(api_key=os.environ["DASHSCOPE_API_KEY"]),
        model="qwen-plus",
        stream=True,
    )
    agent = Agent(
        name="demo",
        system_prompt="你是助手，可执行命令。",
        model=model,
        toolkit=Toolkit(tools=[Bash(), Read()]),
        react_config=ReActConfig(max_iters=10),  # 显式限步
    )

    counts: dict[str, int] = {}
    async for evt in agent.reply_stream(UserMsg("user", "列出当前目录下的 .md 文件数量。")):
        t = evt.type.value
        counts[t] = counts.get(t, 0) + 1
        # 文字增量实时打印
        if evt.type == EventType.TEXT_BLOCK_DELTA:
            print(evt.text_delta, end="", flush=True)
        # 工具调用结束时通报
        elif evt.type == EventType.TOOL_CALL_END:
            print(f"\n  ⚙️ 调用工具: {getattr(evt, 'name', '?')}")
    print("\n\n事件统计:", counts)


if __name__ == "__main__":
    asyncio.run(main())
```

跑：`python code/w04/quickstart.py`

**预期**：Agent 调 `Bash` 跑 `ls`/`find`，吐出 `.md` 数量。结尾事件统计里你会看到 `text_block_delta`、`tool_call_end`、`reply_start`、`reply_end` 等若干种。**这就是 2.0 的"事件流"心智**——Agent 的整个生命周期是一串事件。

### 作业 2：对照 W03，列差异表

开 `code/w04/diff.md`，把你 W03 的 `react_handcraft.py` 和 `Agent._reply_impl` 的步骤逐行对照，写清"我做了什么 / 框架多了什么"。这是面试讲项目的神来之笔。

### 作业 3：用 `reply()` 拿最终消息

把上面改成 `msg = await agent.reply(UserMsg(...))`，打印 `msg.usage`（token 用量）和 `type(msg)`。体会"流式拿过程、reply 拿结果"两条路。

## 5. 面试问答卡

**Q1：agentscope 2.0 为什么只剩一个 `Agent` 类？**
- 参考答案：现代 LLM 自带推理和工具使用能力，框架不该用类层次固定行为。2.0 用**组合**代替**继承**：一个统一 `Agent` 内置 reasoning-acting 循环，行为差异靠 plug 不同 model/toolkit/middlewares/config 表达。这比 1.0 的 ReActAgent/DialogAgent 子类更灵活、更易扩展。
- 源码佐证：`Agent.__init__`（`agent/_agent.py:100`）装配车间；middlewares 按钩子筛选（`:170-188`）。
- 话术：「LLM 自己会推理了，框架不用类来规定行为，改成组合——plug 什么就是什么 Agent。」

**Q2：`reply_stream` 和 `reply` 有什么区别？**
- 参考答案：`reply_stream`（`:194`）返回 `AsyncGenerator[AgentEvent]`，边跑边吐事件，UI 能实时渲染，是 2.0 主力入口；`reply`（`:225`）内部 drain 整个流、返回最终 `Msg`，阻塞到完成。`reply_stream` 内部就是 `async for chunk in self._reply(...)` 只 yield 非 Msg 项（`:221`）。
- 话术：「stream 拿过程给 UI 渲染，reply 拿最终结果。」

**Q3：`_reply_impl` 的循环和手写 ReAct 有什么对应？**
- 参考答案：`_check_next_action`（`:2542`）≈ 手写的"tool_calls 为空就结束"；`_reasoning`（`:916`）≈ 调模型；`_execute_*_tool_calls`（`:1375/:1425`）≈ 执行+回填。框架额外做了并发分批、上下文压缩（`:759`）、事件流、人在回路。
- 话术：「和我手写的轮子一一对应，框架额外加了并发、压缩、事件、HITL。」

**Q4：`max_iters`、`trigger_ratio`、`tool_result_limit` 分别治什么病？**
- 参考答案：`max_iters`（`ReActConfig`）防死循环；`trigger_ratio=0.8`（`ContextConfig`）上下文超 80% 触发压缩；`tool_result_limit=50000` 工具结果超 5 万 token 截断——分别治死循环、上下文爆炸、工具结果过长，正好是 W03 手写撞上的三个坑。
- 话术：「三个参数治三个病：死循环、上下文爆、工具结果过长。」

## 6. 从 1.0 到 2.0 / 避坑

- 1.0：`from agentscope.agents import ReActAgent, DialogAgent` → 2.0：`from agentscope.agent import Agent`（**模块名单数**，糟点：极容易拼错）。
- 1.0：`agent(msg)` 同步 → 2.0：`await agent.reply_stream(msg)` 异步。
- 1.0：行为=子类 → 2.0：行为=组合（plug toolkit/middlewares/config）。
- 旧资料里 `from agentscope.pipelines import ...` 整个模块在 2.0 已删除，别找了。

## 附：本周 checkpoint

- [ ] quickstart 跑通，看到事件统计里多种事件类型
- [ ] `reply()` 跑通，打印出 `msg.usage`
- [ ] W03 轮子 vs `_reply_impl` 差异表写好
- [ ] 能讲清"组合 > 继承"在 2.0 的体现

---
下周：[W05 消息/Event 与模型对接](W05-消息Event与模型对接.md)——把 `Msg`/ContentBlock/事件流/多 provider 接通。