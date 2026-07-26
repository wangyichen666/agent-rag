# code/w04/reply_final_msg.py
# ============================================================
# W04 作业3:用 reply() 拿最终 Msg(阻塞到完成),打印 token 用量与类型
# 体会:reply_stream 拿过程给 UI 渲染,reply 拿最终结果
# 前置: export DASHSCOPE_API_KEY="sk-xxx"
# 运行:  python code/w04/reply_final_msg.py
# 预期:  打印最终 Msg 类型、文本内容、token 用量(input/output)
# ============================================================
import asyncio
import os

from agentscope.agent import Agent
from agentscope.credential import DashScopeCredential
from agentscope.message import UserMsg
from agentscope.model import DashScopeChatModel
from agentscope.tool import Bash, Toolkit


async def main() -> None:
    model = DashScopeChatModel(
        credential=DashScopeCredential(api_key=os.environ["DASHSCOPE_API_KEY"]),
        model="qwen-plus",
        stream=True,
    )
    agent = Agent(
        name="demo",
        system_prompt="你是助手,回答简洁。",
        model=model,
        toolkit=Toolkit(tools=[Bash()]),
    )

    # reply() 消费整个流,返回最终 Msg(阻塞到完成)
    msg = await agent.reply(UserMsg("user", "当前是几点(系统时间)?"))

    print(f"Msg 类型: {type(msg).__name__}")
    print(f"角色: {msg.role}, 发送者: {msg.name}")
    print(f"文本内容: {msg.get_text_content()}")
    if msg.usage:
        print(f"Token: input={msg.usage.input_tokens} output={msg.usage.output_tokens}")
    else:
        print("Token usage: None(该消息未携带用量)")


if __name__ == "__main__":
    asyncio.run(main())