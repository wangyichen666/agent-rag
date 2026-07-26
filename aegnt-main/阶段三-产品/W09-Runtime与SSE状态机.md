# W09 · Runtime 与 SSE 状态机

> 本周目标 | 理解 QwenPaw 怎么把 agentscope 的 `reply` 包成 8 阶段 Runtime + Envelope SSE 状态机，产出工业级 API。
> JD 考点：服务化架构、SSE 流式协议、请求生命周期管理、可扩展插件。

## 1. 本周你将搞懂什么

W04-W08 你学会了"用框架造 Agent"。但框架的 `reply_stream` 只是一个异步生成器——真实产品里，一个 HTTP 请求进来，要做：鉴权、限流、组装 Agent（工具/记忆/治理）、跑、流式推给前端、出错兜底、审计。这些框架不管，是产品的"工程加层"。

QwenPaw 给了一套教科书级实现：**8 阶段 Runtime 生命周期 + Envelope SSE 状态机 + AgentBuilder 依赖注入**。本周拆它，然后仿写一个迷你版。这是从"会用框架"到"会做产品"的跨越。

## 2. 原理铺垫

### 2.1 为什么要有 Runtime 阶段

如果"请求 → 直接 `agent.reply_stream` → 推事件"，看着简单，但很快会遇到：要在调模型前插鉴权、要组装不同工具组合、要在响应后审计、要让插件能挂在各阶段。硬塞进一个函数会变成几百行的 god function。

解法：**把一次请求拆成有序阶段**（pre_dispatch → dispatch → build → execute → response → ...），每个阶段是个钩子点，插件/Hook 可挂任意阶段。这样新功能（如加限流）= 注册一个 pre_execute hook，不改主流程。**阶段化 = 可扩展性。**

### 2.2 为什么要有 Envelope 状态机

框架的 `AgentEvent` 流很"碎"（一堆 delta）。但前端要的是标准化的消息协议（消息块、序号、完成态）。且 SSE 连接可能中断重连，需要能恢复。Envelope 是个**状态机翻译层**：吃进碎 events，吐出有序、带 seq、可最终化的标准 SSE 消息。它内部维护"哪些 text block 正在写、写到哪了"，保证前端拿到的永远是自洽的消息流。

### 2.3 AgentBuilder = 依赖注入装配

每次请求，Agent 不是写死一个，而是按"这次请求的配置"动态装配：哪些工具、哪个模型、哪些中间件、什么治理策略。AgentBuilder 干这事，把"配置 → 可运行 Agent"的过程集中，可测可替。

## 3. 源码精读（QwenPaw，绝对路径）

### 3.1 Runtime 8 阶段生命周期（`src/qwenpaw/runtime/runtime.py:32`）

`Runtime.run()`（`:49`："8-phase lifecycle orchestration"）按顺序走：

| 阶段 | 行号 | 干什么 |
|---|---|---|
| `[phase 1] PRE_DISPATCH` | `:63` | 请求分发前（鉴权/路由准备） |
| `[phase 2] POST_DISPATCH` | `:81` | 分发后 |
| `[phase 3] PRE_AGENT_BUILD` | `:91` | 建 Agent 前 |
| `[phase 4] POST_AGENT_BUILD` | `:107` | Agent 建好后（工具已装） |
| `[phase 5] PRE_EXECUTE` | `:110` | 跑 Agent 前（限流/审批可挂这） |
| `[phase 6] POST_RESPONSE` | `:135` | 响应后（审计/统计挂这） |
| （phase 7/8） | 后续 | 完结/清理 |

注释（`:239`）强调 per-hook shield 执行——插件 hook 失败不影响主流程。

### 3.2 Envelope SSE 状态机（`runtime/envelope.py:27`）

`Envelope`（`:27`："SSE envelope generation + state machine"）：
- `__init__(session_id)`（`:36`）维护 per-request state（text blocks、seq）。
- `_next_seq()`（`:80`）/`_tag_seq()`（`:84`）：给每条消息打序号，支持断线重连续传。
- `emit_response_created()`（`:92`）：响应开始事件。
- `_should_finalize_text_message()`（`:104`）/`_finalize_text_message()`（`:109`）：判断并终结文本消息。
- **核心 `translate_event()`（`:138`）**：把框架 `AgentEvent` 翻译成标准 SSE 消息，内部用 `self._text_blocks`（`:180`）状态字典维护"每个 block 写到哪了"，delta 累加（`:184`）、结束时 finalize（`:196`）。

### 3.3 AgentExecutor（`runtime/executor.py`）

`AgentExecutor` 用心跳包装 `reply_stream`：周期性发心跳维持 SSE 长连接（防代理超时断开），把框架事件转给 Envelope。它是"框架流 → SSE 流"的搬运工 + 保活器。

### 3.4 AgentBuilder 依赖注入（`runtime/builder.py:22`）

`AgentBuilder`（`:22`）：
- `build_toolkit()`（`:36`）：按配置组装工具（含治理包装 `PolicyGuardedTool`，W10 讲）。
- `build()`（`:125`）：装配完整 Agent（工具 + 提示 + 模型 + 中间件 + 滚动上下文 + 治理）。
- `build_prompt()`（`:332`）/`build_model()`（`:376`）：分别建提示词和模型。
- 是"依赖注入式组装"——所有部件按 config 提供，可测试可替换。

### 3.5 QwenPawAgent 扩展框架 Agent（`agents/react_agent.py:47`）

`QwenPawAgent(CodingModeMixin, Agent)`（`:47`）——**继承框架 `Agent`，二次扩展**（这正是"框架提供 block、产品扩展"的范本）：

- `__init__`（`:59`）
- 重写 `compress_context`（`:145`）：用产品的 Scroll Context 策略（W10 详讲）替代框架默认压缩。
- 重写 `_save_to_context`（`:166`）：自定义存回逻辑。
- `state_dict()`（`:174`）/`load_state_dict()`（`:187`）：会话持久化 + 1.x 遗留格式迁移。
- 重写 `_reasoning`（`:366`）：加媒体剥离、被动重试、停止门控（W10 的 gate 接入点）。
- 重写 `_reply`（`:602`）：注入后台工具调用提示。

对比框架原生（W04 的 `Agent._reply_impl:664`），QwenPaw 在每个关键环节都"加料"——这就是产品级 Agent 与框架 demo Agent 的差距来源。

## 4. 动手作业

放 `code/w09/`。

### 作业 1：仿写迷你 Runtime（3-4 阶段）+ Envelope

`code/w09/mini_runtime.py`：把自己之前写的 agentscope Agent 包成一个迷你 Runtime（pre_build / execute / post_response 三阶段）+ 一个把 `AgentEvent` 翻译成标准 SSE 文本的 Envelope。

```python
# code/w09/mini_runtime.py
# 目标：用 3 阶段 Runtime + Envelope 把 agentscope Agent 包成 SSE 接口
import asyncio, os, json
from agentscope.agent import Agent
from agentscope.event import EventType
from agentscope.credential import DashScopeCredential
from agentscope.message import UserMsg
from agentscope.model import DashScopeChatModel
from agentscope.tool import Bash, Toolkit

class Envelope:
    """迷你 SSE 状态机：把 AgentEvent 翻成 {seq, type, data} 的 SSE 行。"""
    def __init__(self):
        self._seq = 0
    def _next(self):
        self._seq += 1
        return self._seq
    def emit(self, etype: str, data: str) -> str:
        payload = json.dumps({"seq": self._next(), "type": etype, "data": data},
                             ensure_ascii=False)
        return f"data: {payload}\n\n"
    def done(self) -> str:
        return "data: [DONE]\n\n"

class MiniRuntime:
    """3 阶段：pre_build → execute → post_response。"""
    def __init__(self, api_key):
        self.api_key = api_key
    async def run(self, query: str):
        env = Envelope()
        # [phase 1] PRE_BUILD
        yield env.emit("phase", "pre_build")
        model = DashScopeChatModel(
            credential=DashScopeCredential(api_key=self.api_key),
            model="qwen-plus", stream=True)
        agent = Agent(name="mini", system_prompt="你是助手", model=model,
                      toolkit=Toolkit(tools=[Bash()]))
        # [phase 2] EXECUTE：跑 Agent，事件经 Envelope 翻译
        yield env.emit("phase", "execute")
        async for e in agent.reply_stream(UserMsg("u", query)):
            if e.type == EventType.TEXT_BLOCK_DELTA:
                yield env.emit("text", e.text_delta)
            elif e.type == EventType.TOOL_CALL_END:
                yield env.emit("tool", "call_end")
        # [phase 3] POST_RESPONSE
        yield env.emit("phase", "post_response")
        yield env.done()

async def main():
    rt = MiniRuntime(os.environ["DASHSCOPE_API_KEY"])
    async for sse_line in rt.run("当前目录有几个 .md 文件？"):
        print(sse_line, end="")

asyncio.run(main())
```

**预期**：输出标准 SSE 行（`data: {"seq":1,"type":"phase","data":"pre_build"}` … `data: [DONE]`），文本逐块带 seq。这就是 Runtime+Envelope 的最小闭环。

### 作业 2：套个 FastAPI，curl 验证 SSE

把作业 1 包成 `GET /chat/stream?q=...` 的 FastAPI 端点（`StreamingResponse`），用 `curl -N "http://127.0.0.1:8000/chat/stream?q=你好"` 验证能收到逐条 SSE。体感"Agent 事件流如何变成工业级 HTTP SSE"。

### 作业 3：加一个 hook

仿 QwenPaw，给 MiniRuntime 加一个 `PRE_EXECUTE` 钩子点（如打印开始时间/简单限流：超过 10 QPS 拒绝）。体感"阶段化让新功能 = 注册一个 hook，不改主流程"。

## 5. 面试问答卡

**Q1：为什么要把一次请求拆成多个 Runtime 阶段？**
- 参考答案：硬塞一个函数会成 god function，难扩展。阶段化（QwenPaw `Runtime.run:49` 的 8 阶段）让鉴权/组装/限流/审计各挂一个阶段 hook，新功能=注册 hook 不改主流程，且每阶段 per-hook shield 执行，插件失败不影响主链。这是可扩展性的关键。
- 源码佐证：`runtime/runtime.py:63/81/91/107/110/135` 各阶段，`:239` shield 说明。
- 话术：「阶段化把请求切成有序钩子点，新功能挂 hook 不改主流程，插件隔离失败不影响主链。」

**Q2：Envelope 状态机解决什么问题？**
- 参考答案：框架 `AgentEvent` 碎（一堆 delta），前端要标准有序可恢复的消息。Envelope（`envelope.py:27`）用 `translate_event`（`:138`）+ `_text_blocks` 状态字典（`:180`）把碎事件翻成带 seq、可 finalize 的标准 SSE，支持断线重连续传（`_next_seq:80`）。它是"框架流→工业 SSE"的翻译+保序层。
- 话术：「Envelope 把碎 delta 翻成带序号的标准 SSE，还能断线重连续传。」

**Q3：AgentBuilder 为什么用依赖注入式组装？**
- 参考答案：每次请求 Agent 按配置动态装配（工具/模型/中间件/治理），AgentBuilder（`builder.py:22`，`build:125`/`build_toolkit:36`）集中"配置→Agent"过程，部件可测可替，避免 100 个 if-else 散落。这是产品级"按请求定制 Agent"的基础。
- 话术：「每请求按配置装配 Agent，集中可测可替，不是写死一个。」

**Q4：QwenPawAgent 怎么扩展框架 Agent？**
- 参考答案：继承 `Agent`（`react_agent.py:47`），重写关键环节加产品料：`compress_context:145`（Scroll 上下文）、`_reasoning:366`（媒体剥离+停止门控）、`_reply:602`、`state_dict/load_state_dict:174/187`（持久化+迁移）。框架给 block，产品在每个 block 加工程逻辑——这是"框架 vs 产品"差距来源。
- 话术：「继承框架 Agent，在 compress/reasoning/reply/state 各环节加产品逻辑。」

## 6. 从 1.0 到 2.0 / 避坑（产品层）

- 框架的 `reply_stream` 是"原料"，产品的 Runtime+Envelope 是"加工线"。直接把 `reply_stream` 暴露给前端 = 没有阶段化、没有序号、没有恢复、没有审计——demo 可以，生产不行。
- QwenPaw 的 8 阶段不是 agentscope 强制的，是产品自己定的——你可以按自己业务定阶段数。
- 每阶段的 hook 用 asyncio.shield 保护（`runtime.py:239`），别让一个插件挂掉把整个请求拖崩。

## 附：本周 checkpoint

- [ ] 作业 1 跑通：MiniRuntime 产出带 seq 的 SSE
- [ ] 作业 2 跑通：curl 收到 SSE 流
- [ ] 作业 3：成功挂一个 phase hook
- [ ] 能讲清"框架 reply → 产品 Runtime/Envelope 中间那层工程"

---
下周：[W10 Loop Engineering 与治理、沙箱、安全](W10-Loop-Engineering与治理沙箱安全.md)——全文最深度一周。