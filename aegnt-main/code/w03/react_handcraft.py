# code/w03/react_handcraft.py
# ============================================================
# W03 作业1:不依赖任何框架,手写 50 行 ReAct 循环(Function Calling 版)
# 核心:模型只决策不执行,你执行工具→回填 tool 消息→循环直到模型直接答
# 前置: export DASHSCOPE_API_KEY="sk-xxx"
# 运行:  python code/w03/react_handcraft.py
# 预期:
#   问题1(杭州天气) -> 直接答
#   问题2(杭州温度*3) -> 看到 [iter0] 执行 get_weather / [iter1] 执行 calc,然后给答案
# ============================================================
import json
import os

from openai import OpenAI  # uv pip install openai

# DashScope OpenAI 兼容入口
client = OpenAI(
    api_key=os.environ["DASHSCOPE_API_KEY"],
    base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
)


# 1. 工具实现(你的真函数;这里 mock,真实场景接天气/计算 API)
def get_weather(city: str) -> str:
    db = {"杭州": "28度晴", "北京": "30度多云"}
    return db.get(city, "未知")


def calc(expression: str) -> str:
    """安全计算:只允许数字和运算符,禁用内置函数。"""
    try:
        return str(eval(expression, {"__builtins__": {}}, {}))
    except Exception as e:
        return f"计算错误: {e}"


# 2. 工具说明书(JSON Schema,喂给模型;对照下方"框架版"就是 FunctionTool 自动生成的)
TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "get_weather",
            "description": "查询某城市天气",
            "parameters": {
                "type": "object",
                "properties": {"city": {"type": "string"}},
                "required": ["city"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "calc",
            "description": "计算数学表达式,如 '28*3'",
            "parameters": {
                "type": "object",
                "properties": {"expression": {"type": "string"}},
                "required": ["expression"],
            },
        },
    },
]

NAME2FN = {"get_weather": get_weather, "calc": calc}


def react(user_query: str, max_iters: int = 8) -> str:
    messages = [
        {"role": "system", "content": "你是助手,能用工具。能直接答就直接答。"},
        {"role": "user", "content": user_query},
    ]
    for i in range(max_iters):
        resp = client.chat.completions.create(
            model="qwen-plus", messages=messages, tools=TOOLS
        )
        msg = resp.choices[0].message
        messages.append(msg.model_dump(exclude_none=True))

        # 模型没有要调工具 -> 它在给最终答案,结束循环
        if not msg.tool_calls:
            return msg.content or "(空回复)"

        # 执行每个工具调用,把结果以 tool 角色消息回填
        for call in msg.tool_calls:
            name = call.function.name
            args = json.loads(call.function.arguments)
            print(f"  [iter {i}] 执行 {name}({args})")
            result = NAME2FN[name](**args)
            messages.append({
                "role": "tool",
                "tool_call_id": call.id,
                "content": str(result),
            })
    return "(达到最大迭代数,强制停止 — 这就是 W10 doom_loop gate 要治的病)"


if __name__ == "__main__":
    print("--- 问题1:杭州天气 ---")
    print(react("杭州天气怎么样?"))
    print("\n--- 问题2:需调两个工具,杭州温度乘以3 ---")
    print(react("杭州天气温度乘以3是多少?"))