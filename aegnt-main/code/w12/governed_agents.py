# code/w12/governed_agents.py
# ============================================================
# W12 作业1:在 W11 骨架上加 Stop Gate(BudgetGate)治理 —— 防 Agent 烧钱
# 对照 QwenPaw loop/gates/budget.py:27(BudgetGate) + token_usage/model_wrapper.py:15
# 用 on_model_call 中间件累计 token,超预算就注入停止指令 + max_iters 兜底
# 前置: export DASHSCOPE_API_KEY="sk-xxx"
# 运行:  python code/w12/governed_agents.py
# 预期:  Agent 跑若干轮,token 达预算(BUDGET)时触发 BUDGET 警告并停止迭代
# ============================================================
import asyncio
import os
from typing import AsyncGenerator, Callable

from agentscope.agent import Agent, ReActConfig
from agentscope.credential import DashScopeCredential
from agentscope.message import UserMsg
from agentscope.middleware import MiddlewareBase
from agentscope.model import DashScopeChatModel
from agentscope.tool import Bash, Toolkit


class BudgetGate(MiddlewareBase):
    """预算门控:累计 token 超预算就注入停止指令。
    对照 QwenPaw BudgetGate(budget.py:27)。真实版能熔断;教学版注入指令 + max_iters 兜底。
    """

    def __init__(self, budget: int = 4000) -> None:
        self.budget = budget
        self.used = 0

    async def on_model_call(
        self,
        agent: Agent,
        input_kwargs: dict,
        next_handler: Callable[[], AsyncGenerator],
    ) -> AsyncGenerator:
        async for item in next_handler():
            yield item
        # 调用后累加 token(从最后一条消息的 usage 取)
        last = agent.state.context[-1] if agent.state.context else None
        u = getattr(last, "usage", None) if last else None
        if u:
            self.used += getattr(u, "input_tokens", 0) + getattr(u, "output_tokens", 0)
            print(f"   💰 累计 token: {self.used}/{self.budget}")
            if self.used > self.budget:
                print(f"🛑 BUDGET 超限 {self.used}>{self.budget},注入停止指令")
                agent.state.context.append(
                    UserMsg(
                        "system",
                        "<system>预算超限,请立即停止调用工具,用已有信息收尾回答。</system>",
                    )
                )


async def main() -> None:
    model = DashScopeChatModel(
        credential=DashScopeCredential(api_key=os.environ["DASHSCOPE_API_KEY"]),
        model="qwen-plus",
        stream=True,
    )
    agent = Agent(
        name="governed",
        system_prompt="你是助手,需要时调工具查目录信息。",
        model=model,
        toolkit=Toolkit(tools=[Bash()]),
        middlewares=[BudgetGate(budget=4000)],   # 预算 4000 token(教学调小)
        react_config=ReActConfig(max_iters=8),   # max_iters 兜底
    )
    async for e in agent.reply_stream(
        UserMsg("u", "统计当前目录各类文件数量,给出报告。")
    ):
        if e.type.value == "TEXT_BLOCK_DELTA":
            print(e.delta, end="", flush=True)
    print("\n\n✅ 完成。把 budget 调更小可观察更早触发熔断。")


if __name__ == "__main__":
    asyncio.run(main())