# code/w07/audit_middleware.py
# ============================================================
# W07 作业1:写一个审计中间件,记录每次推理的迭代号 + token 用量
# 体会:不动 Agent 源码就给它加行为——洋葱模型 hook
# 前置: export DASHSCOPE_API_KEY="sk-xxx"
# 运行:  python code/w07/audit_middleware.py
# 预期:  每轮推理前后打印 [audit] 行,含迭代号和 token 用量
# ============================================================
import asyncio
import os
from typing import AsyncGenerator, Callable

from agentscope.agent import Agent
from agentscope.credential import DashScopeCredential
from agentscope.message import UserMsg
from agentscope.middleware import MiddlewareBase
from agentscope.model import DashScopeChatModel
from agentscope.tool import Bash, Toolkit


class AuditMiddleware(MiddlewareBase):
    """记录每次推理的迭代号与 token 用量。"""

    async def on_reasoning(
        self,
        agent: Agent,
        input_kwargs: dict,
        next_handler: Callable[[], AsyncGenerator],
    ) -> AsyncGenerator:
        # 前处理:打印迭代号
        print(f"  📝 [audit] reasoning iter={agent.state.cur_iter}")
        # 调下一层洋葱(真正的推理),把事件透传给上层
        async for item in next_handler():
            yield item
        # 后处理:看最后一条消息的 token 用量
        last = agent.state.context[-1] if agent.state.context else None
        usage = getattr(last, "usage", None) if last else None
        print(f"  📝 [audit] done usage={usage}")


async def main() -> None:
    model = DashScopeChatModel(
        credential=DashScopeCredential(api_key=os.environ["DASHSCOPE_API_KEY"]),
        model="qwen-plus",
        stream=True,
    )
    agent = Agent(
        name="audit",
        system_prompt="你是助手",
        model=model,
        toolkit=Toolkit(tools=[Bash()]),
        middlewares=[AuditMiddleware()],  # plug 进去
    )
    async for e in agent.reply_stream(UserMsg("u", "看下当前目录有哪些文件")):
        if e.type.value == "TEXT_BLOCK_DELTA":
            print(e.delta, end="", flush=True)
    print()


if __name__ == "__main__":
    asyncio.run(main())