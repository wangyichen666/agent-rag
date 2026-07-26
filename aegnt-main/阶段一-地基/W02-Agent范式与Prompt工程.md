# W02 · Agent 范式与 Prompt 工程

> 本周目标 | 建立完整的 Agent 范式世界观，讲得清 ReAct/Plan-Execute/Multi-Agent/CoT/ToT 各是什么、何时用。
> JD 考点：Agent 核心范式、Prompt Engineering（Few-shot/CoT/ToT/Self-Consistency）、Transformer 原理速通。

## 1. 本周你将搞懂什么

JD 里反复出现这些词：ReAct、Plan-and-Execute、Sub-Agent、Multi-Agent、CoT、ToT、Self-Consistency、Few-shot。面试官最爱问"讲讲你知道的 Agent 范式"——这一题答得好，技术基本盘就立住了。

本周**不写循环代码**（那是 W03 的事），只把概念地图建起来：每种范式解决什么问题、什么场景用、对应到 agentscope 2.0 是什么。务必能脱稿讲。

## 2. 原理铺垫

### 2.1 先分清三个层次（很多人混淆）

```
Prompt 技术      Agent 范式         Agent 系统
─────────────    ─────────────      ─────────────
Few-shot         ReAct              单 Agent + 工具
CoT              Plan-Execute       多 Agent 团队
ToT              Multi-Agent        服务化 + MessageBus
Self-Consistency
```

- **Prompt 技术**：怎么"问"模型（问题本身的组织方式）。
- **Agent 范式**：怎么让模型"行动"（推理与工具调用的组织方式）。
- **Agent 系统**：多个 Agent 怎么"协作 + 工程化"。

agentscope 2.0 是**系统层**框架，但它内部用的就是 ReAct 范式。先把前两层搞懂，框架才看得懂。

### 2.2 Prompt 工程四件套

| 技术 | 干什么 | 何时用 |
|---|---|---|
| **Few-shot** | 给几个"输入→输出"示例，让模型照着做 | 任务有明确格式、模型不够懂事时 |
| **CoT**（Chain-of-Thought） | 让模型"一步步想"再答 | 复杂推理（数学、逻辑），一句"Let's think step by step"就能涨分 |
| **ToT**（Tree-of-Thoughts） | 让模型生成多条思路、自评、回溯 | 搜索/规划类问题，有明确好坏标准可打分 |
| **Self-Consistency** | 同一题采样多次答案，投票取多数 | CoT 仍不稳时，用"多次采样+投票"降噪 |

实操：CoT 是性价比最高的——几乎免费、几乎总有效。ToT 贵（多轮多分支），只在真的需要搜索时用。

### 2.3 Agent 范式三巨头

#### ReAct（Reason + Act）
交替进行"想一步→调一个工具→看结果→再想一步"。这是当下最主流的范式，agentscope 2.0 内建的就是它。

```
Thought: 我需要先查天气
Action: get_weather(城市=杭州)
Observation: 28度，晴
Thought: 天气不错，可以回答了
Final Answer: 杭州今天28度晴天
```

特点：边走边看，灵活；缺点：没有全局计划，长任务容易"漂"。

#### Plan-and-Execute
先让模型**一次性出完整计划**（拆成 N 步），再逐步执行；执行中若发现计划不对，**回头修正计划**。

```
Plan:
  1. 查用户订单状态
  2. 根据状态决定补偿方案
  3. 生成回复话术
Step 1 执行 → 发现订单已退款 → Replan: 跳过补偿,直接告知
```

特点：适合长任务、有明确目标；缺点：计划阶段要花 token，且初始计划可能就错。

#### Multi-Agent
多个分工的 Agent 协作。常见通信模式（JD 明确点名）：

- **消息传递**（message passing）：Agent 之间互发消息，点对点。
- **共享内存 / 黑板模式**（blackboard）：所有 Agent 读写同一块"黑板"，谁有结果往上写，谁需要谁来读。

agentscope 2.0 的多 Agent 用 **Leader-Worker + MessageBus**：leader 拆任务用工具 spawn worker，worker 做完用 `TeamSay` 上报，MessageBus 做消息总线。这在 W08 详讲。

### 2.4 Transformer 速通（JD 要"了解原理"）

只需能讲这几句：

- Transformer 靠 **Self-Attention** 让每个 token "看到"句子中所有其它 token，算出"该关注谁"的权重，加权汇总信息。
- **Positional Encoding** 给每个 token 一个位置信号（因为 Attention 本身没有顺序概念）。
- LLM 生成 = 不断"根据上文预测下一个 token"，一个一个吐（这就是为什么能流式）。
- 上下文窗口 = 模型一次能"看到"多少 token，超了就要截断/压缩（W07 讲）。

不需要会推公式，能讲清"注意力机制让 token 互相 weighting + 自回归逐 token 生成 + 窗口有限"就够了。

## 3. "对应到 agentscope 2.0 是什么"对照表

| JD / 概念 | agentscope 2.0 里的落点 | 几周讲 |
|---|---|---|
| ReAct | `Agent._reply_impl` 内建 reasoning-acting 循环（`agent/_agent.py:664`），`max_iters` 控制迭代 | W03/W04 |
| Plan-and-Execute | 框架没有内建，但可用内置 `TaskCreate/TaskUpdate` 工具实践；QwenPaw 有更完整实现 | W04/W10 |
| Multi-Agent | 服务层 `TeamCreate/AgentCreate/TeamSay` + `MessageBus` | W08/W11 |
| Sub-Agent | `app/_types.py` 的 `SubAgentTemplate`（定义子 Agent 的 prompt/权限） | W08 |
| CoT | prompt 层面，`msg` 里写 "一步步想"；部分模型有 `thinking_enable`（如 DashScope `DashScopeChatModel.Parameters.thinking_enable`） | W05 |
| 结构化输出 | `ChatModelBase.generate_structured_output`（`model/_base.py:438`） | W05 |

## 4. 动手作业

本周作业是**纯 Prompt 体感**，不写循环。放 `code/w02/`。

### 作业 1：用纯 prompt 让模型按 ReAct 格式决策

`code/w02/react_prompt.py`：不写任何工具调用代码，只用一次普通 chat 请求，靠 system prompt 约束模型输出 ReAct 格式。体会"模型自己会按这个格式推理"。

```python
# code/w02/react_prompt.py
# 目标：纯 prompt 让模型按 ReAct(Thought/Action/Observation) 格式输出，体会"模型自带推理"
import asyncio
import os

from dashscope import Application  # 或用上周的 httpx 方式


async def main():
    sys_prompt = """你是 ReAct Agent。严格按此格式回答，可使用的工具：
- search(query): 搜索资料
- calc(expression): 计算数学式

格式：
Thought: <你的推理>
Action: <工具调用，如 search("杭州 人口")>
(等待 Observation 后再继续)

现在回答：杭州人口乘以 3 大约是多少？"""

    # 用 dashscope SDK（或上周 httpx）。这里用同步 SDK 简化
    import dashscope
    dashscope.api_key = os.environ["DASHSCOPE_API_KEY"]
    resp = dashscope.Generation.call(
        model="qwen-plus",
        messages=[{"role": "system", "content": sys_prompt},
                  {"role": "user", "content": "杭州人口乘以 3 大约是多少？"}],
    )
    print(resp.output.choices[0].message.content)


if __name__ == "__main__":
    # dashscope 同步 SDK 在 async main 里也能用，演示用
    asyncio.run(main())
```

**预期**：模型输出一段 `Thought: ... Action: search(...)`（注意：它只是"演"这个格式，并没有真的执行工具——因为这是纯 prompt）。重点体会：**模型天然会按 ReAct 格式组织推理**，这正是 ReAct 范式能成立的基础。下周 W03 你会把这个"演"变成"真执行"。

### 作业 2：对比普通回答 vs CoT 回答

用同一个数学题，分别用"直接回答"和"先一步步想再回答"两次请求，看看 CoT 是否让结果更准。记录到 `code/w02/notes.md`。

## 5. 面试问答卡

**Q1：讲讲 ReAct 和 Plan-Execute 的区别，什么场景用哪个？**
- 参考答案：ReAct 是"边想边做"，Thought-Action-Observation 交替，灵活但无全局计划，适合短链、探索性任务；Plan-Execute 是"先规划后执行 + 修正"，适合长任务、目标明确，能避免单步跳跃式漂移，代价是计划阶段多花 token 且初始计划可能错。生产中常混用：先 Plan 出大纲，再按 ReAct 执行每一步。
- 源码佐证：agentscope `Agent._reply_impl`（`agent/_agent.py:664`）内建 ReAct 循环，`max_iters` 限步。
- 话术：「短任务用 ReAct 灵活，长任务先 Plan 防漂，实际常常 Plan 大纲 + ReAct 执行。」

**Q2：Few-shot、CoT、ToT、Self-Consistency 分别是什么？**
- 参考答案：Few-shot 给示例定格式；CoT 让逐步推理（几乎总有效，性价比最高）；ToT 生成多分支自评回溯（适合有打分标准的搜索/规划）；Self-Consistency 多次采样投票降噪（CoT 不稳时用）。
- 话术：「CoT 是免费午餐，ToT 贵且只用在搜索类，Self-Consistency 是给 CoT 加投票保险。」

**Q3：Multi-Agent 有哪几种通信模式？**
- 参考答案：消息传递（点对点）、共享内存/黑板模式（共用一块读写区）、（agentscope 的）Leader-Worker + 消息总线模式。三者可组合。
- 话术：「点对点、黑板、leader-worker，agentscope 用 leader-worker + MessageBus 解耦。」

**Q4：用一句话讲清 Transformer / Attention。**
- 参考答案：Self-Attention 让每个 token 对所有 token 算"该关注谁"的权重并加权汇总，Positional Encoding 注入顺序信息，整体自回归地逐 token 预测下一个，所以能流式输出；受限于上下文窗口，超长要压缩。
- 话术：「注意力让 token 互相加权，模型自回归逐 token 吐字，窗口有限所以要压缩记忆。」

## 6. 从 1.0 到 2.0 / 避坑

- JD / 旧资料常拿 **LangChain 的 Agent / Hermes / OpenClaw** 举例，这些是别家体系。别把它们的概念直接套到 agentscope——比如 LangChain 的 `AgentExecutor` 和 agentscope 的 `Agent._reply_impl` 思路类似但实现完全不同。
- agentscope 1.0 有 `ReActAgent`/`DialogAgent` 子类，2.0 **没了**，统一 `Agent`，范式由配置和 prompt 决定，不再由子类决定。

## 附：本周 checkpoint

- [ ] 能脱稿讲 ReAct / Plan-Execute / Multi-Agent 三者的差别和适用场景
- [ ] 能讲清 Few-shot/CoT/ToT/Self-Consistency 四个 Prompt 技术
- [ ] 作业 1 跑通，看到模型自己输出 ReAct 格式
- [ ] 能用一段话讲清 Attention + 自回归 + 上下文窗口

---
下周：[W03 手写 ReAct 与 Plan-Execute 循环](W03-手写ReAct与Plan-Execute循环.md)——把本周的"演"变成"真执行"。