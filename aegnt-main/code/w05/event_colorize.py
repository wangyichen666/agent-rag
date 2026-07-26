# code/w05/event_colorize.py
# ============================================================
# W05 作业1:事件流染色打印器,体会 Agent 生命周期的多种事件
# 前置: export DASHSCOPE_API_KEY="sk-xxx"
# 运行:  python code/w05/event_colorize.py
# 预期:  思考过程(若有)紫色、文字白色、工具调用青色、起止黄色
# 注: qwen-plus 通常无 thinking;若想看紫色,可换支持 thinking 的模型并开 thinking_enable
# ============================================================
import asyncio
import os

from agentscope.agent import Agent
from agentscope.credential import DashScopeCredential
from agentscope.event import EventType
from agentscope.message import UserMsg
from agentscope.model import DashScopeChatModel
from agentscope.tool import Bash, Toolkit

# ANSI 颜色
C = {
    "text": "\033[37m",     # 白
    "think": "\033[35m",    # 紫
    "tool": "\033[36m",     # 青
    "sys": "\033[33m",      # 黄
    "end": "\033[0m",
}


async def main() -> None:
    model = DashScopeChatModel(
        credential=DashScopeCredential(api_key=os.environ["DASHSCOPE_API_KEY"]),
        model="qwen-plus",
        stream=True,
    )
    agent = Agent(
        name="c",
        system_prompt="你是助手",
        model=model,
        toolkit=Toolkit(tools=[Bash()]),
    )
    async for e in agent.reply_stream(
        UserMsg("u", "查看当前目录有哪些文件并总结。")
    ):
        t = e.type
        if t == EventType.THINKING_BLOCK_DELTA:
            print(f"{C['think']}·{e.delta}{C['end']}", end="", flush=True)
        elif t == EventType.TEXT_BLOCK_DELTA:
            print(f"{C['text']}{e.delta}{C['end']}", end="", flush=True)
        elif t == EventType.TOOL_CALL_END:
            print(f"{C['tool']}\n⚙️ tool_call {e.name}{C['end']}")
        elif t == EventType.REPLY_START:
            print(f"{C['sys']}== REPLY_START =={C['end']}")
        elif t == EventType.REPLY_END:
            print(f"{C['sys']}\n== REPLY_END reason={e.reason.value} =={C['end']}")
    print()


if __name__ == "__main__":
    asyncio.run(main())