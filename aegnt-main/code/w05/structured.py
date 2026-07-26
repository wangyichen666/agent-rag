# code/w05/structured.py
# ============================================================
# W05 作业2:结构化输出 —— 让模型返回强类型 Pydantic 对象,而非自由文本
# 原理:generate_structured_output 内部用"工具调用模拟"强制模型按 schema 输出 JSON
# 前置: export DASHSCOPE_API_KEY="sk-xxx"
# 运行:  python code/w05/structured.py
# 预期:  打印 PersonInfo(name='张三', age=28, hobbies=['爬山','摄影'])
# ============================================================
import asyncio
import os

from pydantic import BaseModel  # uv pip install pydantic

from agentscope.credential import DashScopeCredential
from agentscope.message import UserMsg
from agentscope.model import DashScopeChatModel


class PersonInfo(BaseModel):
    """要抽取的结构化信息。"""

    name: str
    age: int
    hobbies: list[str]


async def main() -> None:
    model = DashScopeChatModel(
        credential=DashScopeCredential(api_key=os.environ["DASHSCOPE_API_KEY"]),
        model="qwen-plus",
    )
    # generate_structured_output 返回 StructuredResponse,res.content 是 dict
    res = await model.generate_structured_output(
        messages=[
            UserMsg("u", "从这句话抽取信息: 张三28岁,喜欢爬山和摄影")
        ],
        structured_model=PersonInfo,
    )
    p = PersonInfo(**res.content)  # dict -> 强类型对象
    print(p)
    print(f"类型: {type(p).__name__}, hobby 数: {len(p.hobbies)}")
    if getattr(res, "usage", None):
        print(f"Token: {res.usage}")


if __name__ == "__main__":
    asyncio.run(main())