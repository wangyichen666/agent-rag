# code/w11/team_skeleton.py
# ============================================================
# W11 作业2:搭 leader + researcher + writer + reviewer 骨架
#  - researcher:用 MCPClient 接入自建 MCP Server(server.py),动态发现 search_kb/fetch_url
#  - leader:协调三角色(本地顺序版,W12 升级为真异步团队)
# 对照 QwenPaw app/multi_agent_manager.py:23(MultiAgentManager) + drivers/adapters/agentscope_tool.py
# 前置: export DASHSCOPE_API_KEY="sk-xxx"; export MCP_TOKEN="dev-token"
#        uv pip install mcp   (server.py 依赖)
# 运行:  python code/w11/team_skeleton.py
# 预期:  researcher 调 MCP search_kb 拿资料 -> writer 写稿 -> reviewer 审校
# ============================================================
import asyncio
import os
import sys
from pathlib import Path

from agentscope.agent import Agent, ReActConfig
from agentscope.credential import DashScopeCredential
from agentscope.message import UserMsg
from agentscope.mcp import MCPClient, StdioMCPConfig
from agentscope.model import DashScopeChatModel
from agentscope.permission import PermissionContext, PermissionMode
from agentscope.state import AgentState
from agentscope.tool import Toolkit

# 让子进程能找到 server.py
SERVER_PY = str((Path(__file__).parent / "mcp_server" / "server.py").resolve())


def make_model() -> DashScopeChatModel:
    return DashScopeChatModel(
        credential=DashScopeCredential(api_key=os.environ["DASHSCOPE_API_KEY"]),
        model="qwen-plus",
        stream=True,
    )


def bypass_state() -> AgentState:
    """MCP 工具默认 ASK,教学直跑设 BYPASS。生产应配精确权限。"""
    state = AgentState()
    state.permission_context = PermissionContext(permission_mode=PermissionMode.BYPASS)
    return state


async def reply_text(agent: Agent, content: str) -> str:
    parts: list[str] = []
    async for e in agent.reply_stream(UserMsg("u", content)):
        if e.type.value == "TEXT_BLOCK_DELTA":
            parts.append(e.delta)
    return "".join(parts)


async def main() -> None:
    # 1. 接入自建 MCP Server(stdio 拉起 server.py)
    mcp = MCPClient(
        name="research",
        mcp_config=StdioMCPConfig(
            command=sys.executable,          # 用当前 Python 跑 server.py
            args=[SERVER_PY],
            env={"MCP_TOKEN": os.environ.get("MCP_TOKEN", "dev-token")},
        ),
        is_stateful=True,                    # stdio 必须 stateful
        execution_timeout=30.0,
    )
    await mcp.connect()
    try:
        tools = await mcp.list_tools()       # 动态发现 search_kb / fetch_url
        print(f"🔍 researcher 发现 MCP 工具: {[t.name for t in tools]}")

        # 2. 三个角色
        researcher = Agent(
            name="researcher",
            system_prompt=(
                "你是资料研究员。用 search_kb 工具按关键词搜索知识库,"
                "输出 3 条要点。知识库含 agent/react/mcp 等主题。"
            ),
            model=make_model(),
            toolkit=Toolkit(tools=tools),
            react_config=ReActConfig(max_iters=6),
            state=bypass_state(),
        )
        writer = Agent(
            name="writer",
            system_prompt="你是写手。基于提供的资料,写一段 100 字内科普初稿。",
            model=make_model(),
            toolkit=Toolkit(),
        )
        reviewer = Agent(
            name="reviewer",
            system_prompt="你是审校。给文章打分(1-10)并指出最需改进处。",
            model=make_model(),
            toolkit=Toolkit(),
        )

        task = "写一段关于『什么是 AI Agent』的科普"

        print("\n① researcher 查资料(MCP)...")
        research = await reply_text(
            researcher, f"{task}。先用 search_kb 搜 'agent' 再搜 'react'。"
        )
        print(f"   资料: {research[:100]}...\n")

        print("② writer 写初稿...")
        draft = await reply_text(writer, f"资料:\n{research}\n\n任务:\n{task}")
        print(f"   初稿: {draft}\n")

        print("③ reviewer 审校...")
        review = await reply_text(reviewer, f"请审校:\n{draft}")
        print(f"   审校: {review}\n")

        print("✅ Leader 聚合:三角色 + 自建 MCP 协作完成。")
    finally:
        await mcp.close()


if __name__ == "__main__":
    asyncio.run(main())