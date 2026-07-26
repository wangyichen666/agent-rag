# W01 · Python 异步与 LLM API 调用

> 本周目标 | 打通 asyncio 心智模型，能用原生 SDK 流式调通 LLM，并手写一个 SSE 字节流解析器。
> JD 考点：Python 异步编程基础、LLM API 流式调用、Function Calling 预备。

## 1. 本周你将搞懂什么

agentscope 2.0 **从头到尾是异步的**——`Agent.reply_stream()` 是个 `AsyncGenerator`，模型 `__call__` 是 `async def`，工具并发执行靠 `asyncio`。如果你对 asyncio 还停留在"知道有这东西"，本周就会被代码每一个角落卡住。

本周不碰框架的高级概念，只做一件事：**把异步和流式彻底搞懂**，顺带用原生方式把几个主流大模型 API 调通，为 W03 手写 ReAct 循环铺路。

学完能答：
- 为什么要异步？协程比线程好在哪？
- `async for` 是什么？为什么 LLM 要"流式"返回？
- SSE 是什么？字节流怎么变成一行行 token？
- 多个模型请求怎么并发跑、怎么等一起回来？

## 2. 原理铺垫

### 2.1 asyncio 心智模型

```
传统同步：你点外卖→盯着骑手→拿到→继续干   (线程被"阻塞"，闲着等)
异步：    你点外卖→去做别的→骑手到了通知你  (事件循环帮你"等"，CPU 去干别的)
```

关键三件套：

- `async def` 定义的函数是**协程函数**，调用它返回一个**协程对象**，不会立刻执行——必须被 `await` 或放进事件循环。
- `await` = "我在等某个异步操作，事件循环你先去调度别人"。
- `asyncio.run(coro)` = 启动事件循环，跑一个协程直到结束（程序入口用一次）。

```python
import asyncio

async def say(name, delay):
    await asyncio.sleep(delay)   # 模拟 IO 等待，让出控制权
    return f"{name} done in {delay}s"

async def main():
    # 并发：两个协程同时"等"，总耗时约 max(1,2)=2s，而不是 3s
    r = await asyncio.gather(say("A", 1), say("B", 2))
    print(r)  # ['A done in 1s', 'B done in 2s']

asyncio.run(main())
```

经验法则：**IO 密集（等网络/磁盘/模型）用异步**；CPU 密集（大计算）用多进程。调 LLM 就是典型的"等网络"，异步最合适——一个进程能同时等几十个请求。

### 2.2 LLM 为什么要"流式"

生成式模型是一个 token 一个 token 吐出来的。如果等整句生成完再返回，用户要干等几秒到几十秒才看到第一个字；流式则边生成边推，首字延迟降到几百毫秒。

两种获取方式：
- **非流式**：一次 `POST`，等模型生成完，返回完整 JSON。代码简单，体验差。
- **流式（SSE）**：服务器用 `text/event-stream` 一条条推 `data: {...}` 块，客户端边收边解析。

### 2.3 SSE 协议长什么样

SSE（Server-Sent Events）本质是 HTTP 长连接上，服务器按这个格式推文本：

```
data: {"choices":[{"delta":{"content":"你"}}]}

data: {"choices":[{"delta":{"content":"好"}}]}

data: [DONE]
```

- 每条消息以 `data: ` 开头，以**两个换行**分隔。
- 字节流可能在你收到时被切断（"半个 JSON"），所以解析时要维护一个缓冲区，按行/按分隔符拼。

## 3. 源码精读

agentscope 的模型入口是 `ChatModelBase.__call__`（`src/agentscope/model/_base.py:157`，`async def`）。它把一次模型调用抽象成 `await model(...)`，流式时返回异步生成器。

DashScope 模型 `DashScopeChatModel._call_api`（`model/_dashscope/_model.py:176`）内部用 OpenAI 兼容 SDK：构造 `openai.AsyncClient(api_key=..., base_url=...)`，然后 `await client.chat.completions.create(stream=True, ...)`——这正是你本周要手写的底层。

`count_tokens`（`_base.py:350`）和 `generate_structured_output`（`_base.py:438`）是后面 W07/W05 会用到的，本周先知道有这两个口子。

> 本周不精读框架，重点是**自己用 httpx 把这条流式链路手写一遍**，这样后面看框架源码时才不会觉得"这堆 async for 是天书"。

## 4. 动手作业

代码放在 `2027年/code/w01/`。三个小任务，逐个加难度。

### 作业 1：手写 SSE 流式解析器（不依赖 SDK）

`code/w01/sse_handwrite.py`：

```python
# code/w01/sse_handwrite.py
# 目标：用 httpx 直接调 DashScope OpenAI 兼容接口，自己解析 SSE 字节流
import asyncio
import json
import os

import httpx

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

    # async with：上下文管理，离开块自动关闭连接
    async with httpx.AsyncClient(timeout=60) as client:
        async with client.stream("POST", DASHSCOPE_URL, headers=headers, json=payload) as resp:
            resp.raise_for_status()
            buf = ""  # 缓冲区：处理"半行"
            # iter_raw 给字节，按 SSE 协议逐块拼
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
                        delta = json.loads(data)["choices"][0].get("delta", {})
                        if "content" in delta:
                            print(delta["content"], end="", flush=True)


async def main():
    await stream_chat("用三句话向我解释什么是协程。")


if __name__ == "__main__":
    asyncio.run(main())
```

跑：`python code/w01/sse_handwrite.py`

**预期**：模型解释协程的三个句子**逐字**出现，最后打印 `[DONE]`。这个手感就是流式。

### 作业 2：并发调 3 个 provider 对比

`code/w01/concurrent_providers.py`：把同样的问题并发丢给 3 个模型（或同模型 3 次），用 `asyncio.gather` 等全部回来，打印各自耗时和首句。

```python
# code/w01/concurrent_providers.py
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
    print(f"[{label}] {time.perf_counter()-t0:.2f}s -> {text[:40]}")
    return text


async def main():
    prompt = "一句话回答：1+1 等于几？"
    # 三个协程并发，总耗时 ≈ 最慢的那个，而不是三者之和
    await asyncio.gather(
        call_once("qwen-plus", "qwen-plus", prompt),
        call_once("qwen-turbo", "qwen-turbo", prompt),
        call_once("qwen-plus-2", "qwen-plus", prompt),
    )


if __name__ == "__main__":
    asyncio.run(main())
```

**预期**：三行几乎同时打印，总耗时接近单次最慢者。把 `asyncio.gather` 换成顺序 `await` 三次你会看到总耗时变成三者之和——这就是并发的价值。

### 作业 3：事件循环嵌套避坑（选做）

如果在 Jupyter / 已有事件循环的环境里直接 `asyncio.run` 会报 "event loop already running"。体会一下：在交互式环境里要么用 `await main()`，要么用 `nest_asyncio`。知道这个坑存在即可，教程示例一律用脚本 `asyncio.run`。

## 5. 面试问答卡

**Q1：协程和线程的区别？为什么调 LLM 用协程而不是线程？**
- 参考答案：线程是 OS 调度的抢占式并发，切换有内核开销，且共享内存要加锁；协程是用户态协作式并发，在 IO 等待点 `await` 主动让出，切换轻量、单线程内无数据竞争。调 LLM 是 IO 密集（等网络），协程用"等待时间"跑别的请求，几千并发只占一个线程，比开几千个线程省内存。
- 源码佐证：agentscope `ChatModelBase.__call__`（`model/_base.py:157`）即 `async def`，`Agent.reply_stream`（`agent/_agent.py:194`）返回 `AsyncGenerator`，全程协程。
- 一句话话术：「调模型就是等网络，协程在等的时候去跑别的请求，单进程撑高并发还不用加锁。」

**Q2：什么是 SSE？和 WebSocket 有什么区别？**
- 参考答案：SSE 是服务器单向推送的 HTTP 长连接，格式是 `data: ...\n\n`，浏览器和 httpx 都内置支持，断线自动重连；WebSocket 是双向全双工，需握手升级，协议更重。LLM 流式输出只需"服务器→客户端"单向推，SSE 足够且更简单。
- 一句话话术：「LLM 流式只需要服务器单向吐 token，SSE 比 WebSocket 轻得多，还自带断线重连。」

**Q3：`asyncio.gather` 和顺序 await 有什么区别？**
- 参考答案：顺序 `await a; await b` 是串行，总耗时 `a+b`；`gather(a,b)` 让两个协程并发跑，总耗时 `max(a,b)`。前提是 `a`、`b` 内部有 `await` 让出点（如 IO），否则协程不会真正并行。
- 一句话话术：「gather 是并发等，顺序 await 是排队等。」

## 6. 从 1.0 到 2.0 / 避坑

- **1.0**：`agent(msg)` 是同步阻塞调用，一行拿到结果。
- **2.0**：全异步，`await agent.reply_stream(msg)` 返回事件流，`await agent.reply(msg)` 才阻塞到拿到最终 `Msg`。
- 你在网上搜到的 `from agentscope.agents import ReActAgent` 之类的 1.0 写法**全部失效**，2.0 是 `from agentscope.agent import Agent`（注意是单数 `agent` 模块）。

## 附：本周 checkpoint

- [ ] 能解释协程/线程区别，不看资料
- [ ] 作业 1 跑通，看到 token 逐字流式打印
- [ ] 作业 2 跑通，亲眼看到并发比串行快
- [ ] 知道为什么 `asyncio.run` 在 Jupyter 里会报错

---
下周：[W02 Agent 范式与 Prompt 工程](W02-Agent范式与Prompt工程.md)