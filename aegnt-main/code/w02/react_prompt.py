# code/w02/react_prompt.py
# ============================================================
# W02 作业1:纯 prompt 让模型按 ReAct 格式(Thought/Action/Observation)输出
# 重点体会:模型天然会按 ReAct 格式组织推理——这是 ReAct 范式能成立的基石
# 注意:这里模型只是"演"ReAct 格式,工具并未真执行(W03 才真执行)
# 前置: export DASHSCOPE_API_KEY="sk-xxx"
# 运行:  python code/w02/react_prompt.py
# 预期:  模型输出一段 Thought: ... Action: search(...) 格式的文本
# ============================================================
import os

from openai import OpenAI  # uv pip install openai

# DashScope 的 OpenAI 兼容入口
client = OpenAI(
    api_key=os.environ["DASHSCOPE_API_KEY"],
    base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
)

SYS_PROMPT = """你是 ReAct Agent。严格按此格式回答,可使用的工具:
- search(query): 搜索资料
- calc(expression): 计算数学式

格式:
Thought: <你的推理>
Action: <工具调用,如 search("杭州 人口")>
(等待 Observation 后再继续,你只需给出第一步的 Thought 和 Action)"""


def main() -> None:
    resp = client.chat.completions.create(
        model="qwen-plus",
        messages=[
            {"role": "system", "content": SYS_PROMPT},
            {"role": "user", "content": "杭州人口乘以 3 大约是多少?"},
        ],
    )
    print(resp.choices[0].message.content)


if __name__ == "__main__":
    main()