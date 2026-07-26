# code/w04/quickstart.py
# ============================================================
# W04 作业1:agentscope 2.0 最小 Agent,观察事件流事件的种类
# 对照 W03 手写轮子,体会框架替你做了什么
# 前置: export DASHSCOPE_API_KEY="sk-xxx"
# 运行:  python code/w04/quickstart.py
# 预期:  Agent 调 Bash 找 .md 文件,结尾事件统计里能看到若干种事件类型
# ============================================================
import asyncio
import os
from collections import defaultdict

from agentscope.agent import Agent, ReActConfig
from agentscope.credential import DashScopeCredential
from agentscope.event import EventType
from agentscope.message import UserMsg
from agentscope.model import DashScopeChatModel
from agentscope.tool import Bash, Read, Toolkit


async def main() -> None:
    model = DashScopeChatModel(
        credential=DashScopeCredential(api_key=os.environ["DASHSCOPE_API_KEY"]),
        model="qwen-plus",
        stream=True,
    )
    agent = Agent(
        name="demo",
        system_prompt="你是助手,可执行命令。",
        model=model,
        toolkit=Toolkit(tools=[Bash(), Read()]),
        react_config=ReActConfig(max_iters=10),  # 显式限步(默认20)
    )

    counts: dict[str, int] = defaultdict(int)
    async for evt in agent.reply_stream(
        UserMsg("user", "列出当前目录下的 .md 文件数量。")
    ):
        t = evt.type.value
        counts[t] += 1
        if evt.type == EventType.TEXT_BLOCK_DELTA:  # 文本增量字段是 .delta
            print(evt.delta, end="", flush=True)
        elif evt.type == EventType.TOOL_CALL_END:
            print(f"\n  ⚙️ 调用工具: {evt.name}")
        elif evt.type == EventType.REPLY_END:
            print(f"\n  ✅ 完成 reason={evt.reason.value}")
    print("\n\n事件统计:", dict(counts))


if __name__ == "__main__":
    asyncio.run(main())