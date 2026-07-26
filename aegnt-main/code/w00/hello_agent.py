# code/w00/hello_agent.py
# ============================================================
# 环境验收:跑通 agentscope 2.0.4 第一个能调工具的 Agent
# 前置:
#   1. Python >= 3.11,已装 agentscope==2.0.4  (uv pip install "agentscope==2.0.4")
#   2. export DASHSCOPE_API_KEY="sk-xxx"  (阿里云百炼控制台获取)
# 运行:  python code/w00/hello_agent.py
# 预期:  Agent 调 Bash 查操作系统,逐字流式输出一句"当前操作系统是 ..."
# ============================================================
import asyncio
import os

from agentscope.agent import Agent
from agentscope.credential import DashScopeCredential
from agentscope.event import EventType
from agentscope.message import UserMsg
from agentscope.model import DashScopeChatModel
from agentscope.tool import Bash, Read, Toolkit


async def main() -> None:
    # 1. 模型:DashScope(通义 Qwen),stream=True 才能拿到流式事件
    model = DashScopeChatModel(
        credential=DashScopeCredential(api_key=os.environ["DASHSCOPE_API_KEY"]),
        model="qwen-plus",
        stream=True,
    )

    # 2. 工具:先给它 Bash + Read 兜底
    toolkit = Toolkit(tools=[Bash(), Read()])

    # 3. Agent:2.0 只有统一的 Agent 类(没有 ReActAgent 子类)
    agent = Agent(
        name="hello",
        system_prompt="你是一个乐于助人的助手,可以执行命令查看环境。",
        model=model,
        toolkit=toolkit,
    )

    # 4. 流式消费:await reply_stream + async for
    #    注意:文本增量事件字段是 .delta(不是 text_delta)
    async for event in agent.reply_stream(
        UserMsg("user", "用一句话告诉我当前操作系统是什么。"),
    ):
        if event.type == EventType.TEXT_BLOCK_DELTA:
            print(event.delta, end="", flush=True)
        elif event.type == EventType.TOOL_CALL_END:
            print(f"\n  ⚙️ 调用工具 {event.name}")
        elif event.type == EventType.REPLY_END:
            print(f"\n  ✅ 完成,reason={event.reason.value}")
    print()


if __name__ == "__main__":
    asyncio.run(main())