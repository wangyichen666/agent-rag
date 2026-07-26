# code/w08/multi_agent_local.py
# ============================================================
# W08 作业2:多 Agent 协作(本地版) —— leader 协调 researcher/writer/reviewer
# 说明:agentscope 2.0 的"真"多 Agent 是服务层 Team(TeamCreate/AgentCreate/TeamSay
#   + MessageBus),需要起 create_app 服务 + Redis。见 examples/agent_service/main.py。
# 本文件是"单进程教学版":用 agent.reply() 顺序串联,演示 leader--worker 数据流,
#   体会角色分工 + 上下文隔离 + 结果聚合。W11 会升级为真异步团队。
# 前置: export DASHSCOPE_API_KEY="sk-xxx"
# 运行:  python code/w08/multi_agent_local.py
# 预期:  researcher 查资料 → writer 写初稿 → reviewer 审校评分,最后 leader 聚合
# ============================================================
import asyncio
import os

from agentscope.agent import Agent, ReActConfig
from agentscope.credential import DashScopeCredential
from agentscope.message import UserMsg
from agentscope.model import DashScopeChatModel
from agentscope.tool import Bash, Toolkit


def make_model() -> DashScopeChatModel:
    return DashScopeChatModel(
        credential=DashScopeCredential(api_key=os.environ["DASHSCOPE_API_KEY"]),
        model="qwen-plus",
        stream=True,
    )


async def reply_text(agent: Agent, content: str) -> str:
    """跑一轮 Agent,返回文本(吃掉流式增量)。"""
    parts: list[str] = []
    async for e in agent.reply_stream(UserMsg("u", content)):
        if e.type.value == "TEXT_BLOCK_DELTA":
            parts.append(e.delta)
    return "".join(parts)


async def main() -> None:
    # 三个分工 Agent,各自独立 context(天然隔离)
    researcher = Agent(
        name="researcher",
        system_prompt="你是资料研究员。用工具查证后,输出 3 条关键事实要点。",
        model=make_model(),
        toolkit=Toolkit(tools=[Bash()]),  # 简化:用 Bash 模拟"查资料"
        react_config=ReActConfig(max_iters=6),
    )
    writer = Agent(
        name="writer",
        system_prompt="你是写手。基于提供的资料,写一段 100 字以内的科普初稿。",
        model=make_model(),
        toolkit=Toolkit(),
    )
    reviewer = Agent(
        name="reviewer",
        system_prompt="你是审校。给文章打分(1-10)并用一句话指出最需改进处。",
        model=make_model(),
        toolkit=Toolkit(),
    )

    task = "写一段关于『Python 异步编程优势』的科普"

    print("① researcher 查资料...")
    research = await reply_text(researcher, task)
    print(f"   资料: {research[:80]}...\n")

    print("② writer 写初稿...")
    draft = await reply_text(writer, f"资料:\n{research}\n\n任务:\n{task}")
    print(f"   初稿: {draft}\n")

    print("③ reviewer 审校...")
    review = await reply_text(reviewer, f"请审校:\n{draft}")
    print(f"   审校: {review}\n")

    print("✅ Leader 聚合:三角色独立上下文协作完成。")
    print("   (注:真异步团队用 examples/agent_service 的 TeamCreate/TeamSay + MessageBus)")


if __name__ == "__main__":
    asyncio.run(main())