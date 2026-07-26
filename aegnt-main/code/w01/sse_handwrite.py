# code/w01/sse_handwrite.py
# ============================================================
# W01 作业1:用 httpx 直接调 DashScope OpenAI兼容接口,手写 SSE 字节流解析
# 体会:LLM 流式就是 HTTP 长连接上一条条 data: {...} 块,要自己拼缓冲区
# 前置: export DASHSCOPE_API_KEY="sk-xxx"
# 运行:  python code/w01/sse_handwrite.py
# 预期:  模型解释协程的三句话逐字流式出现,最后打印 [DONE]
# ============================================================
import asyncio
import json
import os

import httpx  # 你可能需要: uv pip install httpx

DASHSCOPE_URL = "https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions"


async def stream_chat(prompt: str) -> None:
    headers = {
        "Authorization": f"Bearer {os.environ['DASHSCOPE_API_KEY']}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": "qwen-plus",
        "messages": [{"role": "user", "content": prompt}],
        "stream": True,
        "stream_options": {"include_usage": True},
    }

    # async with:上下文管理,离开块自动关连接
    async with httpx.AsyncClient(timeout=60) as client:
        async with client.stream("POST", DASHSCOPE_URL, headers=headers, json=payload) as resp:
            resp.raise_for_status()
            buf = ""  # 缓冲区:处理"半行"(字节流可能在 JSON 中间被切断)
            async for raw in resp.aiter_text():
                buf += raw
                # SSE 以两个换行分隔每条事件
                while "\n\n" in buf:
                    chunk, buf = buf.split("\n\n", 1)
                    for line in chunk.splitlines():
                        if not line.startswith("data:"):
                            continue
                        data = line[len("data:"):].strip()
                        if data == "[DONE]":
                            print("\n[DONE]")
                            return
                        try:
                            delta = json.loads(data)["choices"][0].get("delta", {})
                        except (json.JSONDecodeError, KeyError):
                            continue
                        if "content" in delta:
                            print(delta["content"], end="", flush=True)


async def main() -> None:
    await stream_chat("用三句话向我解释什么是协程。")


if __name__ == "__main__":
    asyncio.run(main())