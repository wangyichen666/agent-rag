# code/w10/repeat_gate.py
# ============================================================
# W10 作业1:仿 QwenPaw Loop Engineering,写"连续重复调用"停止门控(中间件版)
# 对照 QwenPaw loop/gates/doom_loop.py:43(DoomLoopGate) 治"反复调同工具不收敛"
# 思路:用 on_acting 中间件数工具调用,连续同名超过阈值就往 context 注入
#   "立即停止并总结"指令,诱导 Agent 收敛(配合 max_iters 兜底)。
# 前置: export DASHSCOPE_API_KEY="sk-xxx"
# 运行:  python code/w10/repeat_gate.py
# 预期:  Agent 反复调同一工具时,第 N 次触发 GATE 警告并注入停止指令
# ============================================================
import asyncio
import os
from collections import defaultdict
from typing import AsyncGenerator, Callable

from agentscope.agent import Agent, ReActConfig
from agentscope.credential import DashScopeCredential
from agentscope.event import EventType
from agentscope.message import UserMsg
from agentscope.middleware import MiddlewareBase
from agentscope.model import DashScopeChatModel
from agentscope.tool import Bash, Toolkit


class RepeatToolGate(MiddlewareBase):
    """Stop Gate 迷你版:同一工具连续调用 N 次就注入停止指令。
    真实版(QwenPaw StopGate)能真正中断循环;本教学版用"注入停止指令 + max_iters 兜底"
    演示 gate 的判定逻辑与接入点(on_acting)。
    """

    def __init__(self, max_repeat: int = 3) -> None:
        self.max_repeat = max_repeat
        self._counts: dict[str, int] = defaultdict(int)
        self._last: str | None = None

    async def on_acting(
        self,
        agent: Agent,
        input_kwargs: dict,
        next_handler: Callable[[], AsyncGenerator],
    ) -> AsyncGenerator:
        # acting 前:看上一轮 reasoning 产出的工具调用,数重复
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
                        print(
                            f"🛑 GATE 触发: {b.name} 连续 {self.max_repeat} 次,"
                            "注入停止指令"
                        )
                        # 往 context 注入"立即停止"指令诱导收敛
                        from agentscope.message import UserMsg

                        agent.state.context.append(
                            UserMsg(
                                "system",
                                "<system>检测到重复工具调用,请立即停止调用工具,"
                                "用已有信息总结回答。</system>",
                            )
                        )

        async for item in next_handler():
            yield item


async def main() -> None:
    model = DashScopeChatModel(
        credential=DashScopeCredential(api_key=os.environ["DASHSCOPE_API_KEY"]),
        model="qwen-plus",
        stream=True,
    )
    agent = Agent(
        name="gated",
        system_prompt="你是助手,只在有把握时调工具。",
        model=model,
        toolkit=Toolkit(tools=[Bash()]),
        middlewares=[RepeatToolGate(max_repeat=3)],
        react_config=ReActConfig(max_iters=10),  # max_iters 兜底
    )
    async for e in agent.reply_stream(
        UserMsg("u", "列出当前目录文件(只列一次就好,别反复执行)。")
    ):
        if e.type == EventType.TEXT_BLOCK_DELTA:
            print(e.delta, end="", flush=True)
    print()


if __name__ == "__main__":
    asyncio.run(main())