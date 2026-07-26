# code/w02/cot_compare.py
# ============================================================
# W02 作业2:对比"直接回答" vs "CoT 逐步想",体会 CoT 对复杂推理的提升
# 前置: export DASHSCOPE_API_KEY="sk-xxx"
# 运行:  python code/w02/cot_compare.py
# 预期:  打印两种 prompt 下的回答;复杂题 CoT 通常更准
# ============================================================
import os

from openai import OpenAI

client = OpenAI(
    api_key=os.environ["DASHSCOPE_API_KEY"],
    base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
)

QUESTION = "小明有 15 个苹果,给了小红一半又多 2 个,又买回 5 个,现在有几个?"


def ask(system_prompt: str, tag: str) -> str:
    resp = client.chat.completions.create(
        model="qwen-plus",
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": QUESTION},
        ],
    )
    print(f"=== {tag} ===\n{resp.choices[0].message.content}\n")
    return resp.choices[0].message.content


def main() -> None:
    # 直接回答
    ask("你是数学助手,直接给出答案。", "直接回答")
    # CoT:让它逐步想(几乎免费,几乎总有效)
    ask("你是数学助手,请一步步想,先列出每一步的计算,再给最终答案。",
        "CoT 逐步想(Chain-of-Thought)")


if __name__ == "__main__":
    main()