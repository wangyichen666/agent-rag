# code/w07/long_memory.py
# ============================================================
# W07 作业2:用 AgenticMemoryMiddleware 让 Agent 自己往 Memory/MEMORY.md 写记忆
# 这是"模型自己管记忆"的体感:它决定记什么、写哪里、何时读
# 前置: export DASHSCOPE_API_KEY="sk-xxx"
# 运行:  python code/w07/long_memory.py
# 预期:
#   - Agent 用 Write 工具创建 demo_workspace/Memory/MEMORY.md
#   - 第二轮能"记得"第一轮告知的偏好
# 对应官方示例:examples/long_term_memory/agentic_memory/main.py
# ============================================================
import asyncio
import os
import shutil
from pathlib import Path

from agentscope.agent import Agent
from agentscope.credential import DashScopeCredential
from agentscope.message import UserMsg
from agentscope.middleware import AgenticMemoryMiddleware
from agentscope.model import DashScopeChatModel
from agentscope.permission import (
    AdditionalWorkingDirectory,
    PermissionContext,
    PermissionMode,
)
from agentscope.state import AgentState
from agentscope.tool import Read, Toolkit, Write

WORKSPACE = Path(__file__).with_name("demo_workspace")


def build_agent() -> Agent:
    model = DashScopeChatModel(
        credential=DashScopeCredential(api_key=os.environ["DASHSCOPE_API_KEY"]),
        model="qwen-plus",
        stream=True,
    )
    memory = AgenticMemoryMiddleware(workdir=str(WORKSPACE))
    state = AgentState()
    # 允许 Agent 在该 workspace 读写(记忆文件落这里)
    state.permission_context = PermissionContext(
        permission_mode=PermissionMode.ACCEPT_EDITS,
        additional_working_directories=[
            AdditionalWorkingDirectory(
                source="file-system-memory-demo",
                path=str(WORKSPACE),
            )
        ],
    )
    return Agent(
        name="memory_assistant",
        system_prompt=(
            "你是助手。当用户告诉你需要记住的偏好或事实时,用文件系统记忆指令"
            "持久化到 Memory 文件(Read/Write 工具)。"
        ),
        model=model,
        toolkit=Toolkit(tools=[Read(), Write()]),
        middlewares=[memory],
        state=state,
    )


async def run_turn(agent: Agent, text: str) -> None:
    print(f"\n👤 用户: {text}")
    print("🤖 助手: ", end="")
    async for e in agent.reply_stream(UserMsg("alice", text)):
        if e.type.value == "TEXT_BLOCK_DELTA":
            print(e.delta, end="", flush=True)
    print()


async def main() -> None:
    # 清理上次的记忆,便于复现
    if WORKSPACE.exists():
        shutil.rmtree(WORKSPACE)
    WORKSPACE.mkdir(parents=True, exist_ok=True)

    agent = build_agent()
    # 第一轮:告诉 Agent 一个要记住的偏好
    await run_turn(agent, "请记住:我最喜欢的编程语言是 Python,用它回答我后续问题。")
    # 第二轮:验证 Agent 记得(它会读 MEMORY.md)
    await run_turn(agent, "根据你记住的我的偏好,推荐一个入门项目。")

    memory_md = WORKSPACE / "Memory" / "MEMORY.md"
    if memory_md.exists():
        print(f"\n📄 Agent 自写的记忆文件 {memory_md}:")
        print(memory_md.read_text(encoding="utf-8"))
    else:
        print(f"\n⚠️ 未找到 {memory_md}(Agent 可能没写记忆)")


if __name__ == "__main__":
    asyncio.run(main())