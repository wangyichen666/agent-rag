# code/w09/mini_runtime.py
# ============================================================
# W09 作业1:仿 QwenPaw,用 3 阶段 Runtime + Envelope 把 agentscope Agent 包成 SSE
# 对照 QwenPaw runtime/runtime.py(8阶段) + runtime/envelope.py(状态机)
# 前置: export DASHSCOPE_API_KEY="sk-xxx"
# 运行:  python code/w09/mini_runtime.py
# 预期:  输出标准 SSE 行(data: {"seq":1,"type":"phase","data":"pre_build"} ... [DONE])
# ============================================================
import asyncio
import json
import os
from typing import AsyncGenerator

from agentscope.agent import Agent
from agentscope.credential import DashScopeCredential
from agentscope.event import EventType
from agentscope.message import UserMsg
from agentscope.model import DashScopeChatModel
from agentscope.tool import Bash, Toolkit


class Envelope:
    """迷你 SSE 状态机:把 AgentEvent 翻成 {seq, type, data} 的 SSE 行。
    对照 QwenPaw runtime/envelope.py:27(translate_event + _text_blocks 状态字典)。
    """

    def __init__(self) -> None:
        self._seq = 0

    def _next(self) -> int:
        self._seq += 1
        return self._seq

    def emit(self, etype: str, data: str) -> str:
        payload = json.dumps(
            {"seq": self._next(), "type": etype, "data": data},
            ensure_ascii=False,
        )
        return f"data: {payload}\n\n"

    def done(self) -> str:
        return "data: [DONE]\n\n"


class MiniRuntime:
    """3 阶段:pre_build → execute → post_response。
    对照 QwenPaw Runtime.run()(runtime/runtime.py:49)的 8 阶段生命周期。
    每阶段是可插拔 hook 点:pre_build 可放鉴权,execute 前(pre_execute)可放限流,
    post_response 可放审计。本 demo 先跑通主流程。
    """

    def __init__(self, api_key: str) -> None:
        self.api_key = api_key

    async def run(self, query: str) -> AsyncGenerator[str, None]:
        env = Envelope()
        # [phase 1] PRE_BUILD:组装 Agent
        yield env.emit("phase", "pre_build")
        model = DashScopeChatModel(
            credential=DashScopeCredential(api_key=self.api_key),
            model="qwen-plus",
            stream=True,
        )
        agent = Agent(
            name="mini",
            system_prompt="你是助手",
            model=model,
            toolkit=Toolkit(tools=[Bash()]),
        )
        # [phase 2] EXECUTE:跑 Agent,事件经 Envelope 翻译成 SSE
        yield env.emit("phase", "execute")
        async for e in agent.reply_stream(UserMsg("u", query)):
            if e.type == EventType.TEXT_BLOCK_DELTA:
                yield env.emit("text", e.delta)
            elif e.type == EventType.TOOL_CALL_END:
                yield env.emit("tool", e.name)
        # [phase 3] POST_RESPONSE:收尾(审计/统计挂这)
        yield env.emit("phase", "post_response")
        yield env.done()


async def main() -> None:
    rt = MiniRuntime(os.environ["DASHSCOPE_API_KEY"])
    # SSE 是文本行,逐行打印(模拟前端/网关收到的流)
    async for sse_line in rt.run("当前目录有几个文件?数一数。"):
        print(sse_line, end="")


if __name__ == "__main__":
    asyncio.run(main())