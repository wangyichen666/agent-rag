# code/w06/mcp_client.py
# ============================================================
# W06 作业2:用 MCPClient 接入一个现成 MCP Server,动态发现工具
# 用法对照 examples/agent_service/main.py 的真实写法
# 前置:
#   export DASHSCOPE_API_KEY="sk-xxx"
#   需要 Node.js(npx) 来拉起 @playwright/mcp。若没有 node,本脚本会在 list_tools 处失败,
#   你可换成本地已有 MCP server,或先读控制流程理解。
# 运行:  python code/w06/mcp_client.py
# 预期:  先打印发现的 MCP 工具名列表,Agent 调 playwright 工具完成操作
# ============================================================
import asyncio
import os

from agentscope.agent import Agent, ReActConfig
from agentscope.credential import DashScopeCredential
from agentscope.message import UserMsg
from agentscope.mcp import MCPClient, StdioMCPConfig
from agentscope.model import DashScopeChatModel
from agentscope.permission import PermissionContext, PermissionMode
from agentscope.state import AgentState
from agentscope.tool import Toolkit


async def main() -> None:
    # MCPClient 是 pydantic model,字段直接构造
    # Stdio 模式必须 is_stateful=True(框架校验)
    mcp = MCPClient(
        name="playwright",
        mcp_config=StdioMCPConfig(
            command="npx",
            args=["@playwright/mcp@latest"],
        ),
        is_stateful=True,
        execution_timeout=30.0,
    )

    # 有状态连接必须显式 connect;放 try/finally 保证 close
    await mcp.connect()
    try:
        tools = await mcp.list_tools()  # 动态发现远端工具 -> list[ToolBase]
        print(f"🔍 发现 MCP 工具({len(tools)} 个): {[t.name for t in tools]}")

        if not tools:
            print("⚠️ 未发现工具(MCP server 未正常启动?)，退出。")
            return

        model = DashScopeChatModel(
            credential=DashScopeCredential(api_key=os.environ["DASHSCOPE_API_KEY"]),
            model="qwen-plus",
            stream=True,
        )
        state = AgentState()
        state.permission_context = PermissionContext(
            permission_mode=PermissionMode.BYPASS  # MCP 工具默认 ASK,教学直跑设 BYPASS
        )
        agent = Agent(
            name="web",
            system_prompt="你能操作浏览器，用提供的 MCP 工具完成任务。",
            model=model,
            toolkit=Toolkit(tools=tools),
            react_config=ReActConfig(max_iters=10),
            state=state,
        )
        async for e in agent.reply_stream(
            UserMsg("u", "打开 example.com 并告诉我页面标题。")
        ):
            if e.type.value == "TEXT_BLOCK_DELTA":
                print(e.delta, end="", flush=True)
        print()
    finally:
        await mcp.close()  # 别忘了关,否则子进程泄漏


if __name__ == "__main__":
    asyncio.run(main())