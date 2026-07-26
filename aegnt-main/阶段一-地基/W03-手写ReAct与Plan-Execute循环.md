# W03 · 手写 ReAct 与 Plan-Execute 循环

> 本周目标 | 不依赖任何框架，用原生 LLM API + 循环，自己造一个能调用工具的 Agent，并升级成 Plan-Execute。
> JD 考点：ReAct/Plan-Execute 实现细节、Function Calling、循环终止与重试——这是理解一切框架的钥匙。

## 1. 本周你将搞懂什么

W02 让模型"演"了 ReAct 格式，但工具没真执行。本周你**亲手造轮子**：定义工具、把工具喂给模型、解析模型返回的工具调用、执行、把结果塞回去、循环直到模型说"我答完了"。

为什么一定要自己造？因为：

- 框架（agentscope）做的就是这件事——你不亲手写过，就永远觉得框架是"魔法"，遇到问题不会调；
- 自己造的过程中会**撞上三个痛**：上下文爆炸、工具结果过长、死循环。这三个痛正是 W07（压缩/记忆）和 W10（Loop 治理）要解决的——本周埋的钉子，到时一次性拔掉；
- 面试讲项目时，"我先手写了个 50 行 ReAct，再对比 agentscope 的实现"比"我用了 agentscope"有深度十倍。

## 2. 原理铺垫

### 2.1 Function Calling 的本质

模型本身**不会执行任何东西**。它只是：你给它一份"工具说明书"（JSON Schema），它在回答时，可以选择输出一个**结构化的工具调用请求**（函数名 + 参数 JSON），由**你的代码**去真正执行，再把结果作为新消息喂回去。

```
你 → 模型: [问题] + [可用工具: get_weather(城市)]
模型 → 你:   tool_call: get_weather(城市="杭州")   # 模型说"我想查杭州天气"
你 → 执行:   get_weather("杭州") → "28度晴"
你 → 模型: [问题] + [模型刚才的tool_call] + [tool结果:"28度晴"]
模型 → 你:   "杭州今天28度晴天"                    # 模型看到结果,给出答案
```

关键：**模型决策，你来执行**。循环 = "模型决策 → 你执行 → 喂回去 → 模型再决策"。

### 2.2 ReAct 循环的四个要素

1. **系统 prompt**：告诉模型它是 Agent、有哪些工具、怎么用。
2. **工具定义**：JSON Schema（名字、描述、参数）。
3. **循环 + 终止条件**：模型不再要工具调用时 → 输出最终答案 → 结束；或达到最大迭代数 → 强行停。
4. **工具执行 + 结果回填**：执行模型要的工具，把结果作为 `tool` 角色消息塞回对话。

### 2.3 Plan-Execute 相比 ReAct 多了什么

ReAct 是"走一步看一步"。Plan-Execute 在最前面多一步：**先让模型一次性产出一个 JSON 计划列表**（`[step1, step2, step3]`），然后逐步执行；执行某步后可以触发"重新规划"。

```
Plan: [
  {"step": 1, "action": "search", "desc": "查杭州人口"},
  {"step": 2, "action": "calc",   "desc": "人口*3"},
  {"step": 3, "action": "answer", "desc": "给最终答案"}
]
execute step1 → replan? no → execute step2 → ...
```

## 3. 源码精读（对照目标）

虽然本周不用框架，但瞄一眼框架怎么写循环，方向感更准。agentscope 的 `Agent._reply_impl`（`src/agentscope/agent/_agent.py:664`）就是你想写的东西的"豪华版"：

```
while 没结束且未超 max_iters:
    action = _check_next_action()        # :2542 决定退出还是继续推理
    if action == "reasoning":
        await compress_context()         # :759 上下文压缩(W07)
        yield from self._reasoning()     # :763 调模型(产出thought/tool_call)
        batches = await _batch_tool_calls()
        yield from self._execute_sequential_tool_calls()  # :1375
        # 或 _execute_concurrent_tool_calls() :1425
    else: break
yield ReplyEndEvent
```

你本周写的简化版骨架和它**一一对应**：`_check_next_action`↔你的"模型还要不要调工具"、`_reasoning`↔你的"调模型"、`_execute_*_tool_calls`↔你的"执行工具"。框架多了：并发分批、权限、压缩、事件流、人在回路、重试。你写完简化版，再回头看这段会非常亲切。

## 4. 动手作业

放 `code/w03/`。

### 作业 1：50 行手写 ReAct（Function Calling 版）

`code/w03/react_handcraft.py`：用 DashScope 的 OpenAI 兼容接口（`tools` 参数走原生 Function Calling），自己写 while 循环。

```python
# code/w03/react_handcraft.py
# 目标：手写 ReAct 循环。模型用 tools 决策，你执行，循环直到给答案。
import json
import os

from openai import OpenAI  # pip install openai

# DashScope OpenAI 兼容入口
client = OpenAI(
    api_key=os.environ["DASHSCOPE_API_KEY"],
    base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
)

# 1. 工具实现（你的真函数）
def get_weather(city: str) -> str:
    # 这里 mock 一下，真实场景接天气 API
    db = {"杭州": "28度晴", "北京": "30度多云"}
    return db.get(city, "未知")

def calc(expression: str) -> str:
    try:
        return str(eval(expression, {"__builtins__": {}}, {}))
    except Exception as e:
        return f"计算错误: {e}"

# 2. 工具说明书（JSON Schema，喂给模型）
TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "get_weather",
            "description": "查询某城市天气",
            "parameters": {
                "type": "object",
                "properties": {"city": {"type": "string"}},
                "required": ["city"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "calc",
            "description": "计算数学表达式，如 '28*3'",
            "parameters": {
                "type": "object",
                "properties": {"expression": {"type": "string"}},
                "required": ["expression"],
            },
        },
    },
]

NAME2FN = {"get_weather": get_weather, "calc": calc}


def react(user_query: str, max_iters: int = 8) -> str:
    messages = [
        {"role": "system", "content": "你是助手，能用工具。能直接答就直接答。"},
        {"role": "user", "content": user_query},
    ]
    for i in range(max_iters):
        resp = client.chat.completions.create(
            model="qwen-plus", messages=messages, tools=TOOLS
        )
        msg = resp.choices[0].message
        messages.append(msg.model_dump(exclude_none=True))
        # 模型没有要调工具 → 它在给最终答案
        if not msg.tool_calls:
            return msg.content or "(空回复)"
        # 执行每个工具调用，回填结果
        for call in msg.tool_calls:
            name = call.function.name
            args = json.loads(call.function.arguments)
            print(f"  [iter {i}] 执行 {name}({args})")
            result = NAME2FN[name](**args)
            messages.append({
                "role": "tool",
                "tool_call_id": call.id,
                "content": str(result),
            })
    return "(达到最大迭代数，强制停止)"


if __name__ == "__main__":
    print("--- 问题1：杭州天气 ---")
    print(react("杭州天气怎么样？"))
    print("\n--- 问题2：需要调两个工具，杭州温度乘以3 ---")
    print(react("杭州天气温度乘以3是多少？"))
```

跑：`python code/w03/react_handcraft.py`

**预期**：问题1 直接答；问题2 你会看到 `[iter 0] 执行 get_weather(...)`，模型拿到天气后 `[iter 1] 执行 calc(...)`，第三轮给出答案。这就是一个活的 ReAct Agent，**没依赖任何框架**。

### 作业 2：升级成 Plan-Execute

`code/w03/plan_execute.py`：多一个"规划"阶段。先让模型输出 JSON 计划，再逐步执行；卖个破绽——让计划出错，体验"replan"。

核心改动：第一轮不要 `tools`，改让模型**输出 JSON 计划**；提示词加约束（用 `response_format={"type":"json_object"}` 或 agentscope W05 会讲的 `generate_structured_output`）：

```python
# 伪代码框架，自己补全
def plan_execute(user_query: str):
    # 步骤1: 规划
    plan = ask_model(f"把任务拆成JSON步骤数组: {user_query}", expect_json=True)
    # plan 例: [{"step":1,"tool":"get_weather","args":{"city":"杭州"}}, ...]
    # 步骤2: 逐步执行(可触发 replan)
    results = {}
    for item in plan:
        if item["tool"] == "answer":
            return summarize(user_query, results)
        result = NAME2FN[item["tool"]](**item["args"])
        results[item["step"]] = result
        # (进阶)把结果回灌模型,问"计划要不要调整?" 触发 replan
```

**预期**：模型一次拆出 2-3 步计划，逐步执行后给答案。进阶版能做到"执行中发现某步无意义 → 重新规划"。

### 作业 3：故意制造死循环（体感痛点）

把 `get_weather` 改成"城市不存在时返回 `未知`"，问一个模型名也模糊的问题，观察模型可能反复调 `get_weather` 直到撞 `max_iters`。**把这个错误记下来**——这就是 W10 "doom_loop gate" 要治的病。

## 5. 面试问答卡

**Q1：手写 ReAct 循环时，怎么判断该结束循环？**
- 参考答案：看模型返回的 `message.tool_calls`——为空说明模型不再要工具，给的就是最终答案，结束；非空就执行工具回填继续。同时用 `max_iters` 兜底，防死循环。
- 话术：「空 tool_calls 就结束，非空就执行回填，max_iters 兜底防死锁。」

**Q2：Function Calling 的本质是什么？**
- 参考答案：模型不执行任何东西，只输出结构化的"我想调哪个函数+参数"（JSON Schema 约束），真实执行由调用方代码完成，结果以 `tool` 角色消息回填，模型再据此决策。
- 源码佐证：agentscope `Toolkit.call_tool`（`tool/_toolkit.py:225`）做的就是"模型要的工具由框架执行"。
- 话术：「模型只决策不执行，参数走 JSON Schema，结果以 tool 角色回填。」

**Q3：ReAct 和 Plan-Execute 实现上差在哪？**
- 参考答案：ReAct 每轮只走一步且无全局计划；Plan-Execute 多一个前置规划阶段产出 JSON 步骤列表，逐步执行，且支持 replan。Plan-Execute 更适合长任务，ReAct 更灵活。
- 话术：「Plan-Execute 就是在 ReAct 前面加了个规划阶段，还能中途 replan。」

**Q4：你手写时遇到了什么问题？框架怎么解决的？**
- 参考答案：上下文越来越长（→W07 `compress_context` 按 `trigger_ratio` 压缩）、工具结果太长（→`tool_result_limit=50000` 截断）、死循环（→W10 stop gate 如 doom_loop）。这是从"会用框架"到"懂框架"的分水岭。
- 话术：「手写撞上长上下文、长工具结果、死循环三个坑，正好对应框架的压缩、截断、stop gate。」

## 6. 从 1.0 到 2.0 / 避坑

- 你这个 50 行轮子，逻辑上约等于 agentscope 1.0 的 `ReActAgent.reply()`，也约等于 2.0 的 `Agent._reply_impl`（`agent/_agent.py:664`）的极简版。
- 区别：1.0 把它做成独立子类，2.0 内建进统一 `Agent`，并加了并发/权限/压缩/事件流。**你会写这 50 行，就基本懂了框架核心。**

## 附：本周 checkpoint

- [ ] 作业 1 跑通：看到一个不依赖框架的 ReAct Agent 真的连续调工具
- [ ] 作业 2 跑通：Plan-Execute 能一次出计划再执行
- [ ] 作业 3：复现一次死循环，记下来
- [ ] 能讲清"模型决策、我执行、结果回填、循环终止"四要素

---
地基阶段结束。下周进入 [W04 AgentScope 入门与 Agent 内核](../阶段二-框架/W04-agent scope入门与Agent内核.md)，把你的轮子和框架对照着学。