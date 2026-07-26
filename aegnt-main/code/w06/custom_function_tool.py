# code/w06/custom_function_tool.py
# ============================================================
# W06 作业1:用 FunctionTool 把 Python 函数变 Agent 工具,自动生成 schema
# 对照 W03 手写的 TOOLS 字典:这里一行 FunctionTool 从 docstring 抽 schema
# 前置: export DASHSCOPE_API_KEY="sk-xxx"
# 运行:  python code/w06/custom_function_tool.py
# 预期:  Agent 连调两次 get_stock(AAPL / 0700.HK),汇总回答
# ============================================================
import asyncio
import os

from agentscope.agent import Agent, ReActConfig
from agentscope.credential import DashScopeCredential
from agentscope.message import UserMsg
from agentscope.model import DashScopeChatModel
from agentscope.permission import PermissionContext, PermissionMode
from agentscope.tool import FunctionTool, Toolkit


def get_stock(symbol: str) -> str:
    """查询股票实时价格。

    Args:
        symbol: 股票代码，如 "AAPL" 或 "0700.HK"。
    """
    # mock,演示用。真实场景接行情 API。
    db = {"AAPL": "192.5", "0700.HK": "412.0"}
    return f"{symbol} 当前价格 {db.get(symbol, '未知')}"


async def main() -> None:
    model = DashScopeChatModel(
        credential=DashScopeCredential(api_key=os.environ["DASHSCOPE_API_KEY"]),
        model="qwen-plus",
        stream=True,
    )
    # 注意:自定义 FunctionTool 默认权限是 ASK(要用户确认)。
    # 教学直跑设 BYPASS,跳过确认;生产中应配置精确权限而非 BYPASS。
    from agentscope.state import AgentState

    state = AgentState()
    state.permission_context = PermissionContext(permission_mode=PermissionMode.BYPASS)

    agent = Agent(
        name="fin",
        system_prompt="你是金融助手，可查股价。",
        model=model,
        toolkit=Toolkit(tools=[FunctionTool(get_stock)]),  # 一行变工具
        react_config=ReActConfig(max_iters=8),
        state=state,
    )
    async for e in agent.reply_stream(
        UserMsg("u", "苹果(AAPL)和腾讯(0700.HK)股价分别多少？")
    ):
        if e.type.value == "TEXT_BLOCK_DELTA":
            print(e.delta, end="", flush=True)
    print()


if __name__ == "__main__":
    asyncio.run(main())