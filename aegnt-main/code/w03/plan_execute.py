# code/w03/plan_execute.py
# ============================================================
# W03 作业2:手写 Plan-and-Execute(不依赖框架)
# 与 ReAct 区别:先让模型一次性出 JSON 计划,再逐步执行;支持 replan
# 前置: export DASHSCOPE_API_KEY="sk-xxx"
# 运行:  python code/w03/plan_execute.py
# 预期:  模型先输出计划(JSON),逐步执行工具,最后汇总答案
# ============================================================
import json
import os

from openai import OpenAI

client = OpenAI(
    api_key=os.environ["DASHSCOPE_API_KEY"],
    base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
)


def get_weather(city: str) -> str:
    return {"杭州": "28度晴", "北京": "30度多云"}.get(city, "未知")


def calc(expression: str) -> str:
    try:
        return str(eval(expression, {"__builtins__": {}}, {}))
    except Exception as e:
        return f"计算错误: {e}"


NAME2FN = {"get_weather": get_weather, "calc": calc}

PLANNER_SYS = """你是任务规划器。把用户任务拆成 JSON 步骤数组,严格只输出 JSON。
每步格式: {"step": 整数, "tool": "get_weather"|"calc"|"done", "args": {...}, "desc": "说明"}
- get_weather 的 args: {"city": "..."}
- calc 的 args: {"expression": "如 28*3 的字符串"}
- done 表示所有步骤完成,给出最终答案放进 args: {"answer": "..."}
示例输出:
[{"step":1,"tool":"get_weather","args":{"city":"杭州"},"desc":"查杭州天气"},
 {"step":2,"tool":"done","args":{"answer":"根据天气回答"},"desc":"汇总"}]"""


def plan_execute(user_query: str) -> str:
    # ===== 步骤1: 规划(模型出 JSON 计划) =====
    resp = client.chat.completions.create(
        model="qwen-plus",
        messages=[
            {"role": "system", "content": PLANNER_SYS},
            {"role": "user", "content": user_query},
        ],
        response_format={"type": "json_object"},  # 强制 JSON 输出
    )
    raw = resp.choices[0].message.content
    # 模型可能返回 {"plan": [...]} 或直接 [...]，做兼容
    parsed = json.loads(raw)
    plan = parsed["plan"] if isinstance(parsed, dict) and "plan" in parsed else parsed
    print(f"📋 计划:")
    for step in plan:
        print(f"   {step}")

    # ===== 步骤2: 逐步执行(可触发 replan) =====
    results: dict[int, str] = {}
    for step in plan:
        tool = step["tool"]
        args = step.get("args", {})
        if tool == "done":
            # 汇总阶段:可把已收集结果回灌模型做最终总结(replan 也在这做)
            summary_prompt = (
                f"用户问题:{user_query}\n已收集信息:{results}\n"
                f"模型原计划答案:{args.get('answer','')}\n请据此给最终自然语言答案。"
            )
            final = client.chat.completions.create(
                model="qwen-plus",
                messages=[{"role": "user", "content": summary_prompt}],
            )
            return final.choices[0].message.content
        # 执行真实工具
        result = NAME2FN[tool](**args)
        print(f"   ▶ 执行 step{step['step']} {tool}({args}) -> {result}")
        results[step["step"]] = result

        # 进阶 replan:把结果回灌,问模型"计划要不要调整?"
        # (此处简化跳过;真实 Plan-Execute 在发现某步无意义时会重新调规划器)

    return "(计划执行完但未见 done 步骤)"


if __name__ == "__main__":
    print(plan_execute("杭州天气温度乘以3是多少?"))