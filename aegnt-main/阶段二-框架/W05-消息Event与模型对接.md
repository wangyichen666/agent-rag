# W05 · 消息/Event 与模型对接

> 本周目标 | 吃透 `Msg`/ContentBlock 体系与事件流，接通多 provider，会做结构化输出。
> JD 考点：消息流转、流式事件、模型适配、结构化输出。

## 1. 本周你将搞懂什么

W04 你看到 Agent 边跑边吐"事件"。但这些事件里的数据结构长什么样？模型返回的原始响应怎么变成这些事件？换 Claude / OpenAI / Gemini 要改哪里？如何让模型返回**结构化 JSON** 而不是自由文本？

这些都在两个子系统里：`message/`（数据模型）和 `event/`（事件）+ `formatter/`（模型适配）+ `model/`（模型调用）。本周把它们串起来。

## 2. 原理铺垫

### 2.1 为什么消息不是"一段字符串"

1.0 时代，消息基本就是 `{role, content: str}`。但现代 Agent 要处理：纯文本、模型思考过程（thinking）、工具调用请求、工具执行结果、图片/音频等多模态数据、给模型的隐式提示（hint）。这些东西塞不进一个字符串。

2.0 的解法：`Msg.content` 是一个 **ContentBlock 列表**，每个 block 是一种"内容单元"。一条消息可以是 `[TextBlock, ToolCallBlock, ToolResultBlock]` 的组合。这和 Claude/OpenAI 的 content-parts 思路一致，是当下的主流设计。

### 2.2 事件流 = Agent 生命节的广播

Agent 的 `reply_stream` 是一个"广播站"：它在每个阶段发对应事件，下游（UI / 日志 / 监控）按需订阅。好处是**解耦**——Agent 不关心谁在听，下游不关心 Agent 内部怎么跑。

```
reply 开始 → REPLY_START
  调模型 → MODEL_CALL_START / MODEL_CALL_END
  文字 → TEXT_BLOCK_START / TEXT_BLOCK_DELTA×N / TEXT_BLOCK_END
  思考 → THINKING_BLOCK_* (类似)
  工具调用 → TOOL_CALL_* / TOOL_RESULT_*
回复结束 → REPLY_END
超迭代 → EXCEED_MAX_ITERS
需人确认 → REQUIRE_USER_CONFIRM (HITL)
```

### 2.3 Formatter 做什么

不同 provider 的 API 格式天差地别（OpenAI 用 `content: [{type:"text",...}]`，Claude 用 `content: [{type:"text",...}]` 但 tool 格式不同，Gemini 又是 `parts: [...]`）。Formatter 是**翻译层**：把 agentscope 统一的 `Msg` 列表 → 各 provider 的原生格式。换 provider 只换 formatter + model，业务代码不动。

## 3. 源码精读

### 3.1 `Msg`（`message/_base.py:66`）

`Msg`（`:66`）字段：`name`（发送者名）、`content`（`list[ContentBlock]`，核心）、`role`（user/assistant/system）、`id`、`metadata`、`created_at`、`usage`（token 用量，`:84`）。

`Usage`（`:57`）：`input_tokens` + `output_tokens`。

三个工厂函数（不是子类！）：`UserMsg`（`:476`）、`AssistantMsg`（`:524`）、`SystemMsg`（`:573`）——都是返回设好 `role` 的 `Msg`。

### 3.2 ContentBlock 全家桶（`message/_block.py`）

| Block | 行号 | 干什么 |
|---|---|---|
| `TextBlock` | `:11` | 纯文本 |
| `ThinkingBlock` | `:22` | 模型思考过程（reasoning，如 Claude/o1 的 thinking） |
| `DataBlock` | `:67` | 多模态数据（配 `Base64Source:40`/`URLSource:51`） |
| `HintBlock` | `:81` | 给模型的隐式提示（不回显给用户，RAG 注入用这个，W07/W08） |
| `ToolCallBlock` | `:114` | 模型要调工具的请求（含工具名+参数） |
| `ToolResultBlock` | `:167` | 工具执行结果 |

体会：一条 assistant 消息可能同时含 `TextBlock`（说话）+ `ToolCallBlock`（顺手调个工具）。1.0 串字符串做不到。

### 3.3 EventType 全枚举（`event/_event.py:24-62`）

精确清单（`:24` 起）：`REPLY_START/END`、`MODEL_CALL_START/END`、`TEXT_BLOCK_START/DELTA/END`、`DATA_BLOCK_*`、`THINKING_BLOCK_*`、`HINT_BLOCK`、`TOOL_CALL_START/DELTA/END`、`TOOL_RESULT_START/TEXT_DELTA/DATA_DELTA/END`、`EXCEED_MAX_ITERS`、`REQUIRE_USER_CONFIRM/EXTERNAL_EXECUTION`、`USER_CONFIRM_RESULT`、`USER_INTERRUPT`、`EXTERNAL_EXECUTION_RESULT`、`CUSTOM`。

`ReplyEndReason`（`:96`）：`COMPLETED` / `INTERRUPTED` / `EXCEED_MAX_ITERS`——回复为什么结束，三种原因。

Delta 事件（`*_DELTA`）就是流式增量，UI 拿它实时拼接显示。End 事件是"这块完毕"的信号。

### 3.4 Formatter（`formatter/`，9 个 provider）

每个 provider 两个格式化器：`XxxChatFormatter`（单 Agent）+ `XxxMultiAgentFormatter`（多 Agent，把 `name` 编进消息）。文件：`_anthropic_formatter.py` / `_dashscope_formatter.py` / `_deepseek_formatter.py` / `_gemini_formatter.py` / `_moonshot_formatter.py` / `_ollama_formatter.py` / `_openai_formatter.py` / `_openai_response_formatter.py` / `_xai_formatter.py`，基类 `_formatter_base.py:FormatterBase`。

换 provider：`DashScopeChatModel` 内部默认用 `DashScopeChatFormatter`（见 W01 导读里 subagent 报告：`model=_dashscope/_model.py:151` 设 `self.formatter = formatter or DashScopeChatFormatter()`）。你一般不用手设。

### 3.5 结构化输出（`model/_base.py:438`）

`ChatModelBase.generate_structured_output`（`:438`）：传一个 Pydantic model 或 JSON schema，让模型返回**结构化数据**（不是自由文本）。默认实现在 `_call_api_with_structured_output`（`:503`），用"工具调用"模拟结构化输出（把 schema 伪装成一个工具让模型"调用"）。

DashScope 的 `_call_api_with_structured_output`（`model/_dashscope/_model.py:534`）有个细节：开 thinking 模式时会把 `tool_choice` 降级成 `"auto"`（DashScope 不允许 thinking + required tool_choice）——这就是框架替你处理的 provider 坑。

### 3.6 多 provider 入口（`model/__init__.py` 可用类）

`DashScopeChatModel`、`OpenAIChatModel`、`OpenAIResponseModel`（o1/o3 reasoning）、`AnthropicChatModel`、`GeminiChatModel`、`OllamaChatModel`、`DeepSeekChatModel`、`MoonshotChatModel`、`XAIChatModel`。credential 对应在 `credential/__init__.py`（`DashScopeCredential`、`AnthropicCredential` … `CredentialFactory`）。

## 4. 动手作业

放 `code/w05/`。

### 作业 1：事件流染色打印器

`code/w05/event_colorize.py`：把不同事件类型染不同颜色，体会事件种类。

```python
# code/w05/event_colorize.py
import asyncio, os
from agentscope.agent import Agent
from agentscope.credential import DashScopeCredential
from agentscope.event import EventType
from agentscope.message import UserMsg
from agentscope.model import DashScopeChatModel
from agentscope.tool import Bash, Toolkit

# ANSI 颜色
C = {"text": "\033[37m", "think": "\033[35m", "tool": "\033[36m",
     "sys": "\033[33m", "end": "\033[0m"}

async def main():
    model = DashScopeChatModel(
        credential=DashScopeCredential(api_key=os.environ["DASHSCOPE_API_KEY"]),
        model="qwen-plus", stream=True)
    agent = Agent(name="c", system_prompt="你是助手", model=model,
                  toolkit=Toolkit(tools=[Bash()]))
    async for e in agent.reply_stream(UserMsg("u", "查看当前目录有哪些文件并总结。")):
        t = e.type
        if t == EventType.TEXT_BLOCK_DELTA:
            print(f"{C['text']}{e.text_delta}{C['end']}", end="", flush=True)
        elif t == EventType.THINKING_BLOCK_DELTA:
            print(f"{C['think']}·{e.text_delta}{C['end']}", end="", flush=True)
        elif t == EventType.TOOL_CALL_END:
            print(f"{C['tool']}\n⚙️ tool_call end{C['end']}")
        elif t == EventType.REPLY_START:
            print(f"{C['sys']}== REPLY_START =={C['end']}")
        elif t == EventType.REPLY_END:
            print(f"{C['sys']}\n== REPLY_END reason={e.reason.value} =={C['end']}")
    print()

asyncio.run(main())
```

**预期**：思考过程紫色、文字白色、工具调用青色、起止黄色。如果模型不开 thinking，紫色部分可能没有——可把 model 参数换成支持 thinking 的（DashScope 的 `Parameters(thinking_enable=True)`，但要注意 qwen-plus 是否支持）对照。

### 作业 2：结构化输出

`code/w05/structured.py`：让模型返回一个 Pydantic 对象，而不是自由文本。

```python
# code/w05/structured.py
import asyncio, os
from pydantic import BaseModel
from agentscope.credential import DashScopeCredential
from agentscope.message import UserMsg
from agentscope.model import DashScopeChatModel

class PersonInfo(BaseModel):
    name: str
    age: int
    hobbies: list[str]

async def main():
    model = DashScopeChatModel(
        credential=DashScopeCredential(api_key=os.environ["DASHSCOPE_API_KEY"]),
        model="qwen-plus")
    # generate_structured_output 直接拿结构化结果
    res = await model.generate_structured_output(
        messages=[UserMsg("u", "从这句话抽取信息: 张三28岁，喜欢爬山和摄影")],
        structured_model=PersonInfo,
    )
    p = PersonInfo(**res.content)  # res.content 是 dict
    print(p)  # name='张三' age=28 hobbies=['爬山','摄影']

asyncio.run(main())
```

**预期**：直接拿到强类型 `PersonInfo` 对象。这就是 W02 说"LangChain 里费劲做的事，框架一行 `generate_structured_output` 搞定"。

### 作业 3：换 provider 对照

把作业 1 的 model 换成 `AnthropicChatModel(credential=AnthropicCredential(api_key=os.environ["ANTHROPIC_API_KEY"]), model="claude-sonnet-4-5")`，**业务代码一行不改**（只是 import 换一下），确认结果一样能出。体会 Formatter 的价值。没 Claude key 就跳过。

## 5. 面试问答卡

**Q1：agentscope 2.0 的消息为什么是 ContentBlock 列表而不是字符串？**
- 参考答案：一条消息常含多种内容（文本/思考/工具调用/工具结果/多模态/hint），串字符串表达不了。`Msg.content` 是 `list[ContentBlock]`（`message/_base.py:72`），每种内容一个 block（TextBlock:11 / ToolCallBlock:114 / ToolResultBlock:167 / DataBlock:67 / HintBlock:81 / ThinkingBlock:22），和 Claude/OpenAI 的 content-parts 一致。
- 话术：「一条消息可能同时含文字和工具调用，用 block 列表才能干净表达。」

**Q2：Agent 的事件流解决了什么问题？**
- 参考答案：解耦。Agent 把生命周期各阶段广播成事件（`event/_event.py:24` 起 30+ 种），UI/日志/监控各取所需，Agent 不关心谁听。Delta 事件做流式拼接，End 事件做分块结束信号，REQUIRE_USER_CONFIRM 做 HITL，EXCEED_MAX_ITERS 做兜底。
- 话术：「事件流是广播总线，Agent 发、下游订阅，互不耦合。」

**Q3：换模型 provider 要改什么？**
- 参考答案：换 model 类（`DashScopeChatModel`→`AnthropicChatModel`）+ credential，**业务代码不动**——因为 Formatter 把统一 `Msg` 翻译成各 provider 原生格式。各 model 内部自带默认 formatter（如 DashScope 的 `DashScopeChatFormatter`）。
- 话术：「换 model+credential 就行，业务代码零改，Formatter 顶住格式差异。」

**Q4：结构化输出怎么做？为什么有用？**
- 参考答案：`model.generate_structured_output(messages, structured_model=Pydantic类)`（`model/_base.py:438`），内部默认用"工具调用模拟"（`:503`）让模型按 schema 返回 JSON。用处：要确定性结构（抽取、分类、计划生成）时，避免解析自由文本的脆弱。
- 话术：「传个 Pydantic 进去拿强类型结果，比正则解析自由文本稳得多。」

## 6. 从 1.0 到 2.0 / 避坑

- 1.0：`Msg.content` 是字符串 / 字典，结构散乱 → 2.0：`list[ContentBlock]`，强类型。
- 1.0：没有事件流，靠回调或同步返回 → 2.0：`AsyncGenerator[AgentEvent]`，全流式。
- 1.0：换 provider 要改不少 → 2.0：Formatter 层隔离，换 model 类即可。
- HintBlock（`:81`）是新东西，RAG/上下文注入用它——1.0 没有。

## 附：本周 checkpoint

- [ ] 作业 1 跑通，看到多种染色事件
- [ ] 作业 2 跑通，拿到强类型 Pydantic 对象
- [ ] 能列出 5 种以上 ContentBlock 及用途
- [ ] 能讲清"为什么换 provider 业务代码不用改"

---
下周：[W06 工具体系与 MCP](W06-工具体系与MCP.md)——FunctionTool/MCPTool/ToolGroup/权限。