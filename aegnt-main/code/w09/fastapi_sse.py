# code/w09/fastapi_sse.py
# ============================================================
# W09 作业2:把 MiniRuntime 包成 FastAPI 的 SSE 端点,curl 验证
# 前置: export DASHSCOPE_API_KEY="sk-xxx"
#        uv pip install fastapi uvicorn
# 运行:  python code/w09/fastapi_sse.py  (起服务)
# 验证:  另开终端 curl -N "http://127.0.0.1:8000/chat/stream?q=你好"
# 预期:  curl 收到逐条 data: {...} 的 SSE 流,最后 [DONE]
# ============================================================
import asyncio
import os

from fastapi import FastAPI  # uv pip install fastapi uvicorn
from fastapi.responses import StreamingResponse

# 复用作业1的 MiniRuntime / Envelope
from mini_runtime import MiniRuntime

app = FastAPI()
_runtime = MiniRuntime(os.environ["DASHSCOPE_API_KEY"])


@app.get("/chat/stream")
async def chat_stream(q: str) -> StreamingResponse:
    """SSE 端点:把 MiniRuntime 的 SSE 行流式返回。
    对照 QwenPaw app/_router/_session.py 的 GET /sessions/{sid}/stream 长连接。
    """

    async def event_gen():
        async for sse_line in _runtime.run(q):
            yield sse_line  # 每行已是 "data: {...}\n\n" 格式

    return StreamingResponse(event_gen(), media_type="text/event-stream")


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="127.0.0.1", port=8000, log_level="info")