# code/w06/tool_group_switch.py
# ============================================================
# W06 作业3:ToolGroup 分组按需激活,Agent 用 ResetTools 元工具切换"抽屉"
# 有非 basic 组时,Toolkit 自动注入 ResetTools,Agent 自己决定激活哪些组
# 注意:ResetTools 输入是各分组 bool,代表"最终状态非增量"——激活一个会停用其他
# 前置: export DASHSCOPE_API_KEY="sk-xxx"
# 运行:  python code/w06/tool_group_switch.py
# 预期:  Agent 先调 reset_tools 激活对应组,再调组内工具完成任务
# ============================================================
import asyncio
import os

from agentscope.agent import Agent, ReActConfig
from agentscope.credential import DashScopeCredential
from agentscope.message import UserMsg
from agentscope.model import DashScopeChatModel
from agentscope.permission import PermissionContext, PermissionMode
from agentscope.state import AgentState
from agentscope.tool import FunctionTool, ToolGroup, Toolkit


# === 只读搜索组 ===
def search_files(directory: str, pattern: str = "*.py") -> str:
    """列出目录下匹配模式的文件。

    Args:
        directory: 要搜索的目录路径。
        pattern: glob 模式，默认 "*.py"。
    """
    import glob

    matches = glob.glob(os.path.join(directory, pattern))[:5]
    return f"匹配到 {len(matches)} 个: {matches}"


# === 写文件组(有副作用) ===
def write_file(path: str, content: str) -> str:
    """写入文件。

    Args:
        path: 文件路径。
        content: 文件内容。
    """
    with open(path, "w") as f:
        f.write(content)
    return f"已写入 {len(content)} 字符到 {path}"


async def main() -> None:
    model = DashScopeChatModel(
        credential=DashScopeCredential(api_key=os.environ["DASHSCOPE_API_KEY"]),
        model="qwen-plus",
        stream=True,
    )
    state = AgentState()
    state.permission_context = PermissionContext(
        permission_mode=PermissionMode.ACCEPT_EDITS  # 允许编辑类工具自动执行
    )

    toolkit = Toolkit(
        # basic 组(永远激活):放点通用工具
        tools=[],
        tool_groups=[
            ToolGroup(
                name="search_tools",
                description="文件搜索工具组，用于查找文件",
                instructions="这是只读搜索工具组。",
                tools=[FunctionTool(search_files, is_read_only=True)],
            ),
            ToolGroup(
                name="edit_tools",
                description="文件编辑工具组，用于写入文件",
                instructions="这是文件编辑工具组，使用前确认路径。",
                tools=[FunctionTool(write_file, is_read_only=False)],
            ),
        ],
    )

    agent = Agent(
        name="filebot",
        system_prompt=(
            "你是文件管理助手。根据任务先用 reset_tools 激活合适的工具组,"
            "再执行任务。当前工作目录可用 '.' 。"
        ),
        model=model,
        toolkit=toolkit,
        react_config=ReActConfig(max_iters=10),
        state=state,
    )

    print("=== 任务1:搜索 Python 文件 ===")
    async for e in agent.reply_stream(
        UserMsg("u", "搜索当前目录(.)下有哪些 py 文件?")
    ):
        if e.type.value == "TEXT_BLOCK_DELTA":
            print(e.delta, end="", flush=True)
    print("\n")


if __name__ == "__main__":
    asyncio.run(main())