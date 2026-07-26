# W10 · Loop Engineering 与治理、沙箱、安全

> 本周目标 | 理解 QwenPaw 如何治理 Agent 失控（死循环/超预算/无效迭代）、做权限策略与内核级沙箱、接 Token 监控与可观测性、审批人在回路。
> JD 考点：Agent Loop 治理（断连/无效循环/执行失控）、安全沙箱执行、调用审计、熔断限流——全文最深、面试最亮眼一周。

## 1. 本周你将搞懂什么

W03 你手写 ReAct 时埋了第三个钉子：**死循环**。W07 拔了前两个（上下文爆炸、工具结果过长），本周拔最后一个，而且拔得最彻底——这就是"Loop Engineering"。

但 W10 不只是拔钉子。一个企业级 Agent 还要回答：怎么防 Agent 花光预算？怎么防它跑危险命令？怎么把工具执行隔离到沙箱防逃逸？怎么审计每次调用？危险操作怎么让人在回路审批？怎么监控 Token 与链路？JD 里"Agent Loop 治理""安全沙箱执行""调用审计""熔断降级限流"全在这一周。QwenPaw 给了生产级答案，我们拆它。

## 2. 原理铺垫

### 2.1 Loop Engineering：可插拔的停止门控（Stop Gate）

死循环不止是"同名工具调到天荒地老"。真实失控形态多样：

| 失控形态 | 例子 | 对应 Gate |
|---|---|---|
| 死循环 | 反复调同一工具不收敛 | `DoomLoopGate` |
| 超预算 | 一轮烧掉 50 万 token | `BudgetGate` |
| 超迭代 | 20+ 轮还没完 | `IterationGate` |
| 文件循环 | 反复读写同一文件 | `FileLoopGate` |
| 不达标 | 永远达不到"完成"判据 | `StandaloneRubricGate`（评分门控） |

治理思路：**把"该不该停"抽成可插拔的 Stop Gate**。每个 gate 是一个独立判据，Agent 每轮执行前过一遍所有 gate，任一触发就停。这样新增一种治理规则 = 加一个 gate，不改核心。QwenPaw 把它叫 Loop Engineering。

这是"是否会做生产 Agent"的分水岭：业余的靠 `max_iters` 兜底（粗暴），专业的用多 gate 精准治理（每种病一服药）。

### 2.2 治理 + 权限 + 沙箱 + 审计 = 企业级工具调用

工具调用链路在产品里要过四道关：

```
模型要调工具
  → 权限引擎：该 Agent 有权调这工具吗？(PolicyGuardedTool)
  → 执行级别：STRICT/SMART/AUTO/OFF 决定要不要审批
  → 沙箱：在隔离环境执行(macOS Seatbelt/Linux bubblewrap)
  → 审计：记录谁、何时、调了什么、结果
  → (危险操作) ApprovalService 人在回路
```

### 2.3 Token 监控与可观测性

- **Token 监控**：用 `TokenRecordingModelWrapper` 包装模型，每次调用记 token，`TokenUsageManager` 聚合，可配预算熔断（与 BudgetGate 联动）。
- **Trace**：agentscope 有 `TracingMiddleware`（W07），QwenPaw 接 Langfuse 做更完整可观测性（trace/metrics）。
- **审计**：工具调用全程记日志（谁/何时/调什么/结果），供合规追溯。

## 3. 源码精读（QwenPaw，绝对路径）

### 3.1 Loop Gates（`loop/gates/`）

`StopGate`（`loop/gates/base.py:61`）：所有停止门控的抽象基类，定义"检测 + 决定停否"接口。

`LoopGate`（`loop/gates/loop_gate.py:40`）：门控基类，具体 gate 继承它：

| Gate | 文件:行 | 治什么 |
|---|---|---|
| `DoomLoopGate` | `loop/gates/doom_loop.py:43` | 反复调同工具不收敛 |
| `BudgetGate` | `loop/gates/budget.py:27` | 一轮/总量超预算 |
| `IterationGate` | `loop/gates/iteration.py:27` | 超迭代次数 |
| `FileLoopGate` | `loop/gates/file_loop_gate.py:41` | 反复读写同文件 |
| `StandaloneRubricGate` | `loop/gates/rubric.py:154` | 评分判据不达标 |

`runner.py`/`handler.py`：把所有 gate 串起来，每轮过一遍。QwenPawAgent 的 `_reasoning`（`react_agent.py:366`）是 gate 接入点。

### 3.2 治理：PolicyGuardedTool（`governance/tool_adapter.py:108`）

`PolicyGuardedTool`（`:108`）：**包装**任意工具，强加策略检查 + `check_permissions`。模型"以为"在调原工具，实际过了一层治理壳。`GovernancePolicy`（`governance/policy.py:550`）：策略引擎，定义"哪些 Agent 能调哪些工具、什么条件"。

> 呼应 W06：agentscope 原生有 `PermissionEngine`/`PermissionMode` 五档；QwenPaw 用 `BYPASS` 绕过原生引擎，自己用 `PolicyGuardedTool` 实现更细的企业级策略。组合拳。

### 3.3 执行级别 ToolExecutionLevel（`security/tool_guard/execution_level.py`）

四档（`:21/28/37/44`）：

| 级别 | 行号 | 行为 |
|---|---|---|
| `STRICT` | `:21` | 所有工具都要审批 |
| `SMART` | `:28` | 低危自动放行，中危+要审批 |
| `AUTO` | `:37` | 仅 guarded_tools 要审批（向后兼容，默认） |
| `OFF` | `:44` | 完全关闭 tool guard |

`security/tool_guard/engine.py` 是判定引擎，`approval.py` 管审批流，`models.py` 定义规则模型，`utils.py` 有 shell 逃逸守护（拦截 `rm -rf`/管道注入等）。

### 3.4 内核级沙箱（`sandbox/`）

按操作系统分别实现隔离执行：

| 文件 | 平台 | 机制 |
|---|---|---|
| `macos_sandbox.py` | macOS | Seatbelt（sandbox-exec） |
| `bubblewrap_sandbox.py` | Linux | bubblewrap |
| `linux_sandbox.py` | Linux | landlock |
| `windows_sandbox.py` | Windows | AppContainer |
| `local_sandbox.py` | 通用 | 本地无隔离（仅开发用） |

`config.py` 统一配置。工具（如 `execute_shell_command`）在沙箱里跑，即使被 prompt 注入跑了恶意命令，也被内核级隔离挡住逃逸。

### 3.5 技能扫描（`security/skill_scanner/`）

`scanner.py`/`scan_policy.py`/`models.py`：加载第三方 Skill/插件前扫描，防恶意 Skill 夹带危险代码。skill 是 W11 会讲的"SKILL.md"技能体系，扫描是它的安全前置。

### 3.6 Token 监控（`token_usage/`）

`TokenRecordingModelWrapper(ChatModelBase)`（`token_usage/model_wrapper.py:15`）：包装模型，每次 `__call__` 记 token。`TokenUsageManager`（`token_usage/manager.py:65`）聚合统计，`buffer.py` 缓冲，`storage.py` 持久化，`turn_usage.py` 按轮次统计。与 `BudgetGate` 联动实现"超预算熔断"。

### 3.7 可观测性（`observability/langfuse.py`）

接 Langfuse，产 trace/metrics，比框架 `TracingMiddleware`（OTel）更偏产品侧的可视化看板。

### 3.8 人在回路审批（`app/approvals/`）

`ApprovalService`（`app/approvals/service.py:72`）：管 pending 审批、解决、GC。`PendingApproval`（`:39`）数据模型。`driver_gate.py`：驱动级操作的审批门。配合 W04 框架的 `REQUIRE_USER_CONFIRM` 事件 + W06 的 `ASK` 权限决策，实现"危险操作暂停 → 人审批 → 继续/拒绝"。

## 4. 动手作业

放 `code/w10/`。

### 作业 1：给 agentscope Agent 加一个自定义 Stop Gate

`code/w10/repeat_gate.py`：仿 QwenPaw 思路，写一个"连续 3 次调同一工具就停"的 gate，用中间件挂到 Agent。

```python
# code/w10/repeat_gate.py
# 目标：仿 Loop Engineering，写一个"连续重复调用"停止门控
import asyncio, os
from collections import defaultdict
from agentscope.agent import Agent
from agentscope.credential import DashScopeCredential
from agentscope.event import EventType
from agentscope.message import UserMsg
from agentscope.middleware import MiddlewareBase
from agentscope.model import DashScopeChatModel
from agentscope.tool import Bash, Toolkit

class RepeatToolGate(MiddlewareBase):
    """Stop Gate 迷你版：同一工具连续调用 3 次就强制注入停止提示。"""
    def __init__(self, max_repeat=3):
        self.max_repeat = max_repeat
        self._counts = defaultdict(int)
        self._last = None
    async def on_acting(self, *, agent, input_kwargs, next_handler):
        # acting 前检查；这里简化：在 on_reasoning 里数 tool_call
        async for item in next_handler(**input_kwargs):
            yield item

    async def on_reasoning(self, *, agent, input_kwargs, next_handler):
        async for item in next_handler(**input_kwargs):
            yield item
        # 推理后看最后一条 assistant msg 的工具调用
        last = agent.state.context[-1] if agent.state.context else None
        if last and getattr(last, "content", None):
            from agentscope.message import ToolCallBlock
            for b in last.content:
                if isinstance(b, ToolCallBlock):
                    if b.name == self._last:
                        self._counts[b.name] += 1
                    else:
                        self._last, self._counts[b.name] = b.name, 1
                    if self._counts[b.name] >= self.max_repeat:
                        print(f"🛑 GATE 触发: {b.name} 连续 {self.max_repeat} 次,强制停止!")

async def main():
    model = DashScopeChatModel(
        credential=DashScopeCredential(api_key=os.environ["DASHSCOPE_API_KEY"]),
        model="qwen-plus", stream=True)
    agent = Agent(name="g", system_prompt="你是助手", model=model,
                  toolkit=Toolkit(tools=[Bash()]),
                  middlewares=[RepeatToolGate(max_repeat=3)],
                  react_config=agent_react_with_max_iter(15))  # 见下
    async for e in agent.reply_stream(UserMsg("u", "反复执行 ls 直到停下")):
        if e.type == EventType.TEXT_BLOCK_DELTA:
            print(e.text_delta, end="", flush=True)
    print()

def agent_react_with_max_iter(n):
    from agentscope.agent import ReActConfig
    return ReActConfig(max_iters=n)

asyncio.run(main())
```

> 这个 gate 是教学示意（真实 gate 要看 QwenPaw `StopGate` 抽象的 hook 时机与"如何真正中断循环"）。重点是建立"停止条件可插拔"的心智——对照 QwenPaw `loop/gates/` 五个真实 gate。

**预期**：Agent 反复调 Bash 时，第 3 次触发 `🛑 GATE`，对照 QwenPaw `DoomLoopGate`（`doom_loop.py:43`）正是干这个。

### 作业 2：配一条 YAML tool_guard 规则拦截危险命令

`code/w10/tool_guard.yaml`：仿 QwenPaw `security/tool_guard/` 写一条规则，拦截 `rm -rf /`、`curl | sh` 等危险命令。给 YAML 草稿 + 一段说明"如果接到作业 1 的 Bash 工具，会怎么判定 STRICT/SMART/AUTO/OFF"。

```yaml
# code/w10/tool_guard.yaml（仿 QwenPaw security/tool_guard 规则结构）
rules:
  - name: block-destructive-rm
    pattern: "rm\\s+-rf?\\s+(/|~|\\*)"
    level: deny          # 直接拒绝
    message: "禁止递归删除根/家目录"
  - name: block-pipe-exec
    pattern: "(curl|wget).*\\|\\s*(sh|bash)"
    level: deny
    message: "禁止管道下载即执行"
  - name: warn-sudo
    pattern: "sudo\\s"
    level: ask            # 需审批(对应 STRICT/SMART 的审批流)
    message: "sudo 操作需确认"
```

### 作业 3（选做）：接 Langfuse 或 OTel trace

把 W07 的 `TracingMiddleware` 或 Langfuse 接上作业 1，看一次回复的 trace 树（几次模型调用、几次工具、各耗多少 token）。没环境就研究 `token_usage/manager.py:65` 怎么聚合轮次 token。

## 5. 面试问答卡（本周最重——逐条命中 JD）

**Q1：你怎么治理 Agent 的死循环/超预算/无效迭代？（JD：Agent Loop 治理、解决断连/无效循环/执行失控）**
- 参考答案：用 Loop Engineering——把"该不该停"抽成可插拔 Stop Gate（QwenPaw `loop/gates/base.py:61`），每轮过所有 gate：`DoomLoopGate`（`doom_loop.py:43`）治反复调同工具、`BudgetGate`（`budget.py:27`）治超预算、`IterationGate`（`iteration.py:27`）治超迭代、`FileLoopGate`（`file_loop_gate.py:41`）治文件循环、`StandaloneRubricGate`（`rubric.py:154`）治评分不达标。任一触发即停。比单靠 `max_iters` 精准——每种病一服药，新增治理=加 gate 不改核心。断连靠 state 持久化 + resume（W09 Runtime 阶粒度）。
- 话术：「停止条件做成可插拔 gate，doom/budget/iteration/file/rubric 各治一种失控，任一触发即停。」

**Q2：怎么做安全沙箱执行？防什么？（JD：安全沙箱执行）**
- 参考答案：工具执行隔离到内核级沙箱，按平台分别用 macOS Seatbelt（`sandbox/macos_sandbox.py`）、Linux bubblewrap（`bubblewrap_sandbox.py`）/landlock（`linux_sandbox.py`）、Windows AppContainer（`windows_sandbox.py`）。防 prompt 注入诱导 Agent 跑恶意命令（如 `rm -rf`、`curl|sh`）逃逸到宿主。配 tool_guard YAML 规则前置拦截 + sandbox 兜底隔离，双保险。
- 话术：「工具在内核级沙箱跑，macOS Seatbelt/Linux bubblewrap/Win AppContainer，防注入逃逸，配规则前置拦截。」

**Q3：工具调用怎么做权限和审计？（JD：权限管理、调用审计）**
- 参考答案：四道关——`PolicyGuardedTool`（`governance/tool_adapter.py:108`）强加策略+`check_permissions`，`GovernancePolicy`（`policy.py:550`）定义 Agent↔工具权限映射；执行级别 `ToolExecutionLevel` STRICT/SMART/AUTO/OFF（`tool_guard/execution_level.py:21-44`）决定审批粒度；沙箱隔离执行；全程审计日志记谁/何时/调什么/结果。`ApprovalService`（`app/approvals/service.py:72`）+ 框架 `REQUIRE_USER_CONFIRM` 做危险操作人在回路。
- 话术：「PolicyGuardedTool 管策略，四档执行级别定审批，沙箱隔离，全程审计，危险操作人审批。」

**Q4：怎么做限流熔断和 Token 治理？（JD：限流降级、Token 消耗监控）**
- 参考答案：Token 用 `TokenRecordingModelWrapper`（`token_usage/model_wrapper.py:15`）包装模型记每次用量，`TokenUsageManager`（`:65`）聚合，`BudgetGate` 超预算熔断。限流在 app 层（W09 Runtime pre_execute hook + QwenPaw `app/` 限流中间件）；熔断级联到模型层可用框架 `ModelConfig.max_retries/fallback_model` 降级。Langfuse（`observability/langfuse.py`）做 trace/metrics 可视化。
- 话术：「Token 录制包装+聚合+预算 gate 熔断，限流挂 pre_execute，降级靠 fallback_model，Langfuse 看板。」

## 6. 从 1.0 到 2.0 / 避坑

- 治理不是"加个 max_iters"，而是"多 gate 精准治理"——1.0/业余做法粗放，2.0+QwenPaw 精细。
- agentscope 原生 `PermissionEngine` 五档（W06）是基础，QwenPaw `PolicyGuardedTool` 是企业级加层——别只用原生五档就说"做了权限"。
- 沙箱要按平台选对实现，macOS 用 sandbox-exec（Seatbelt）不是 Linux 的 bubblewrap，别混。
- 审计要落库（谁/何时/调什么/结果），别只 print 到日志。

## 附：本周 checkpoint

- [ ] 作业 1 跑通：自定义 gate 在连续调用时触发
- [ ] 作业 2：写出拦截危险命令的 YAML 规则，能解释四档执行级别
- [ ] 能把 JD 的"Loop 治理/沙箱/审计/限流"逐条对应到 QwenPaw 源码文件
- [ ] 能讲清"停止条件可插拔 gate"比"单靠 max_iters"强在哪

---
下周：[W11 多 Agent 协作平台实战（上）](W11-多Agent协作平台实战(上).md)——开始造毕业项目。