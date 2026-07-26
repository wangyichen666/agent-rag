# code/w12/app.py
# ============================================================
# W12 作业3:毕业项目的 FastAPI 服务化入口(SSE 接口)
# 把 W11 的多 Agent 协作(leader 调度)包成 HTTP SSE 端点
# 依赖:agentscope, fastapi, uvicorn, mcp
# 运行: python code/w12/app.py  然后 curl -N "http://127.0.0.1:8088/stream?q=..."
# ============================================================
import asyncio
import json
import os

from fastapi import FastAPI
from fastapi.responses import StreamingResponse

from agentscope.agent import Agent, ReActConfig
from agentscope.credential import DashScopeCredential
from agentscope.event import EventType
from agentscope.message import UserMsg
from agentscope.model import DashScopeChatModel
from agentscope.tool import Bash, Toolkit

# 复用 W12 BudgetGate
from governed_agents import BudgetGate

app = FastAPI(title="研究-写作-审校 多Agent协作平台")


def _make_agent() -> Agent:
    model = DashScopeChatModel(
        credential=DashScopeCredential(api_key=os.environ["DASHSCOPE_API_KEY"]),
        model="qwen-plus",
        stream=True,
    )
    return Agent(
        name="platform",
        system_prompt="你是研究-写作-审校协作平台的主控。分析任务后给出方案与结论。",
        model=model,
        toolkit=Toolkit(tools=[Bash()]),
        middlewares=[BudgetGate(budget=20000)],
        react_config=ReActConfig(max_iters=12),
    )


@app.get("/stream")
async def stream(q: str) -> StreamingResponse:
    agent = _make_agent()

    async def gen():
        seq = 0
        async for e in agent.reply_stream(UserMsg("u", q)):
            if e.type == EventType.TEXT_BLOCK_DELTA:
                seq += 1
                payload = json.dumps({"seq": seq, "text": e.delta}, ensure_ascii=False)
                yield f"data: {payload}\n\n"
            elif e.type == EventType.REPLY_END:
                yield f"data: {json.dumps({'end': e.reason.value})}\n\n"
        yield "data: [DONE]\n\n"

    return StreamingResponse(gen(), media_type="text/event-stream")


@app.get("/health")
async def health() -> dict:
    return {"status": "ok"}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=int(os.getenv("PORT", "8088")))