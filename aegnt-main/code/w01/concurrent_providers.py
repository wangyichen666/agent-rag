# code/w01/concurrent_providers.py
# ============================================================
# W01 作业2:并发调多个模型,用 asyncio.gather 对比串行
# 体会:IO 密集用异步,gather 让总耗时≈最慢的那个(而非三者之和)
# 前置: export DASHSCOPE_API_KEY="sk-xxx"
# 运行:  python code/w01/concurrent_providers.py
# 预期:  三行几乎同时打印(并发),总耗时≈单次最慢者。
#        把下面 gather 换成顺序 await,总耗时会变成三者之和——对照体验
# ============================================================
import asyncio
import os
import time

import httpx

URL = "https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions"


async def call_once(label: str, model: str, prompt: str) -> str:
    headers = {"Authorization": f"Bearer {os.environ['DASHSCOPE_API_KEY']}"}
    payload = {"model": model, "messages": [{"role": "user", "content": prompt}]}
    t0 = time.perf_counter()
    async with httpx.AsyncClient(timeout=60) as client:
        r = await client.post(URL, headers=headers, json=payload)
        r.raise_for_status()
        text = r.json()["choices"][0]["message"]["content"]
    dt = time.perf_counter() - t0
    print(f"[{label}] {dt:.2f}s -> {text[:40]}", flush=True)
    return text


async def main() -> None:
    prompt = "一句话回答:1+1 等于几?"
    print("--- 并发版本(asyncio.gather) ---")
    t0 = time.perf_counter()
    # 三个协程并发,总耗时 ≈ max(三者),不是三者之和
    await asyncio.gather(
        call_once("qwen-plus-a", "qwen-plus", prompt),
        call_once("qwen-turbo", "qwen-turbo", prompt),
        call_once("qwen-plus-b", "qwen-plus", prompt),
    )
    print(f"并发总耗时: {time.perf_counter() - t0:.2f}s")

    # 对照:把上面 gather 改成下面顺序 await,看总耗时变成三者之和
    # print("\n--- 串行版本(对照) ---")
    # t0 = time.perf_counter()
    # await call_once("a", "qwen-plus", prompt)
    # await call_once("b", "qwen-turbo", prompt)
    # await call_once("c", "qwen-plus", prompt)
    # print(f"串行总耗时: {time.perf_counter() - t0:.2f}s")


if __name__ == "__main__":
    asyncio.run(main())