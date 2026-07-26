# W08 · RAG 与多 Agent Team + 服务化

> 本周目标 | 建知识库做 RAG；理解 2.0 多 Agent 的 Team+MessageBus 模型；跑服务化 SSE。
> JD 考点：RAG/向量检索、多 Agent 编排、会话管理、SSE 流式服务。

## 1. 本周你将搞懂什么

W07 给了单 Agent 的记忆。本周把视野放大两件事：

1. **RAG**：让 Agent 查外部知识库（PDF/Word/网页），而不是只靠模型自带知识。
2. **多 Agent**：W02 讲过 Multi-Agent 范式，现在看 agentscope 2.0 怎么实现——答案是**服务层 Team + MessageBus**，而不是 1.0 的代码级 Pipeline。这是 2.0 迁移最反直觉的点。

顺带把框架最后的拼图补上：**服务化**——把 Agent 跑成 HTTP 服务，SSE 推流，这才是生产形态。

## 2. 原理铺垫

### 2.1 RAG 两要素 + 两模式

RAG（检索增强生成）= 先**检索**相关片段，再把它塞进 prompt 让模型基于"查到的证据"回答。两要素：

- **知识库构建**：解析文档 → 分块（chunk）→ 向量化（embedding）→ 存向量库。
- **检索使用**：用户问题向量化 → 向量库找 Top-K 相似片段 → 注入 prompt。

agentscope 提供两种注入模式：

```
static  模式：RAGMiddleware 在首轮自动检索，用 HintBlock 一次性注入(模型被动看)
agentic 模式：暴露 search_knowledge 工具，模型自主决定何时检索(模型主动搜)
```

agentic 更灵活（模型判断要不要查、查几次），是默认推荐。

### 2.2 多 Agent：从"代码编排"到"服务编排"（关键范式转变）

W02 讲过 Multi-Agent 通信三模式（消息传递/共享内存/leader-worker）。1.0 的做法是**代码级编排**：你在 Python 里写 `pipeline(agent1, agent2)`，或用 `MsgHub` 共享消息。问题是：编排逻辑写死在代码里，难扩展、难并发、难多租户。

2.0 转成**服务级编排**：

```
Leader Agent 通过"工具"管理团队：
  TeamCreate  → 建团队,当前 session 成为 leader
  AgentCreate → spawn 一个 worker(自带 prompt + 权限)
  TeamSay     → leader↔worker 通信(单播/广播)
  TeamDelete  → 解散
MessageBus   → 消息总线(InMemory/Redis),解耦 leader/worker
```

精髓：**多 Agent 协作 = Leader 用工具调度的子任务**。Leader 自己也是 Agent，它"管理团队"这个动作，本质上和"调用 Bash"一样，是个工具调用。这样：

- 编排逻辑由模型决策（动态），不是写死代码（静态）；
- Worker 是独立 session，天然隔离、可并发；
- 换成 Redis MessageBus 就能横向扩展、多租户。

这是理解 2.0 多 Agent 的钥匙：**不要找 Pipeline，它在服务层。**

### 2.3 服务化与 SSE

`Agent.reply_stream` 是异步生成器，但浏览器/curl 拿不到生成器——要 HTTP。服务化就是把 `reply_stream` 包成 `GET /sessions/{sid}/stream` 长连接 SSE，前端边收边渲染。agentscope 用 ag-ui-protocol 标准。

## 3. 源码精读

### 3.1 RAG 模块（`rag/`）

| 组件 | 文件 | 作用 |
|---|---|---|
| `KnowledgeBase` | `rag/_knowledge.py` | 核心句柄：`insert_document` / `search` / `list_documents` / `delete_document`，绑定 embedding + vector_store + collection |
| Parser | `rag/_parser/_pdf.py` `_word.py` `_ppt.py` `_excel.py` `_text.py` `_image.py` | 各格式解析 |
| Chunker | `rag/_chunker/_approx_token_chunker.py` | 按 chunk_size/overlap 分块 |
| VectorStore | `rag/_vdb/_qdrant.py` `_milvus_lite.py` `_mongodb.py` | 向量库后端（`_vector_store.py` 基类） |

### 3.2 两种 RAG 模式

- **static**：`RAGMiddleware`（`middleware/_rag.py:456`）在首轮 reasoning 自动检索，结果包成 `HintBlock`（W05 讲过，给模型的隐式提示，不回显）一次性注入。
- **agentic**（默认）：暴露 `search_knowledge` 工具，模型自主调用。见 `examples/rag/integrate_with_agent.py` 两个模式对照。

### 3.3 多 Agent Team（`app/_tool/`，服务层）

| 工具 | 文件 | 作用 |
|---|---|---|
| `TeamCreate` | `app/_tool/_team_create.py` | 建团队，当前 session 成 leader |
| `AgentCreate` | `app/_tool/_agent_create.py` | spawn worker，自带 prompt + 权限模式 |
| `AgentInvite` | `app/_tool/_agent_invite.py` | 邀请已有 agent 入队 |
| `TeamSay` | `app/_tool/_team_say.py` | leader↔worker 通信（单播/广播） |
| `TeamDelete` | `app/_tool/_team_delete.py` | 解散团队 |

子 Agent 模板 `SubAgentTemplate`（`app/_types.py`）：定义 `type/description/system_prompt_template/permission_context`（如 `explorer` 只读 worker）。

### 3.4 MessageBus（`app/message_bus/`）

`_base.py`（基类）+ `_in_memory_message_bus.py`（单机）+ `_redis_message_bus.py`（分布式/多 worker）。Leader 和 Worker 通过总线收发消息，解耦调度。换 Redis 即横向扩展。

### 3.5 会话管理（`app/_service/_session.py`）

`SessionService` 管多租户多会话，`SessionStatus` 状态机，支持 cancel/delete/团队级联。Redis 存储（`app/storage/_redis_storage.py`）。

### 3.6 SSE 长连接（`app/_router/_session.py`）

`GET /sessions/{sid}/stream`：长连接 SSE，推 `AgentEvent` + 心跳；`POST` 触发 run，事件异步下发，符合 ag-ui-protocol。

## 4. 动手作业

放 `code/w08/`。

### 作业 1：建 PDF 知识库，跑 static + agentic 双 RAG

`code/w08/rag_two_modes.py`：先索引一份 PDF（或几个 txt），再用两种模式让 Agent 查。

```python
# code/w08/rag_two_modes.py（结构骨架，按本机 agentscope 导出补全）
import asyncio, os
from agentscope.agent import Agent
from agentscope.credential import DashScopeCredential
from agentscope.message import UserMsg
from agentscope.model import DashScopeChatModel
from agentscope.rag import KnowledgeBase  # 实际导出以 rag/__init__.py 为准

async def build_kb():
    # 1. 建 KB：embedding + 向量库(Qdrant/MilvusLite) + collection
    kb = KnowledgeBase(...)  # 参考 examples/rag/index_and_search.py
    # 2. 解析+分块+入库
    await kb.insert_document("docs/faq.pdf")
    return kb

async def agentic_mode(kb):
    model = DashScopeChatModel(
        credential=DashScopeCredential(api_key=os.environ["DASHSCOPE_API_KEY"]),
        model="qwen-plus", stream=True)
    # agentic：KB 自动暴露 search_knowledge 工具给 Agent
    agent = Agent(name="qa", system_prompt="你是文档问答助手，用工具查知识库", model=model)
    # 把 kb 接成工具(具体 API 见 examples/rag/integrate_with_agent.py)
    ...
    async for e in agent.reply_stream(UserMsg("u", "退换货政策是什么？")):
        if e.type.value == "text_block_delta":
            print(e.text_delta, end="", flush=True)
    print()

async def main():
    kb = await build_kb()
    await agentic_mode(kb)

asyncio.run(main())
```

> 完整可运行的 static/agentic 双模式代码，直接照 `examples/rag/integrate_with_agent.py` 改。**先 clone 跑通官方示例**，再改自己的文档。

**预期**：Agent 调 `search_knowledge` 查 KB，基于检索片段回答（而不是瞎编）。对比 static 模式（首轮自动注入）vs agentic（主动搜）的差异。

### 作业 2：起服务，建 Team 让 leader spawn 2 worker

`code/w08/team_demo.py`：跑 `examples/agent_service/main.py` 起服务，然后用 leader 创建团队、spawn 两个分工 worker。

```bash
# 1. 起服务(照 examples/agent_service/main.py 配好 Redis + Qdrant + key)
cd examples/agent_service && python main.py
```

然后构造一个场景：leader 拿到任务"翻译一段话成英文并润色"，它用 `AgentCreate` spawn 一个"翻译 worker"和一个"润色 worker"，用 `TeamSay` 派活、收结果、汇总。

```python
# code/w08/team_demo.py（伪代码骨架，对照 examples/agent_service/main.py 的 SubAgentTemplate）
# leader 通过工具调用完成团队管理，本质和调 Bash 一样
# TeamCreate -> AgentCreate(translator) -> AgentCreate(polisher)
# -> TeamSay(translator, 翻译这句) -> 收 result
# -> TeamSay(polisher, 润色这句) -> 收 result -> 汇总
```

**预期**：日志里看到 leader 调 `team_create`/`agent_create`/`team_say`，两个 worker 各自工作，leader 聚合输出。**这就是 2.0 的"多 Agent 编排"——没有 Pipeline，全是工具调用。**

### 作业 3：SSE 验证

服务起来后，`curl -N http://127.0.0.1:<port>/sessions/<sid>/stream`，看事件一条条推下来。体感"Agent 事件流如何变成 HTTP SSE"。

## 5. 面试问答卡

**Q1：RAG 的 static 和 agentic 模式区别？何时用哪个？**
- 参考答案：static 用 `RAGMiddleware`（`middleware/_rag.py:456`）首轮自动检索、`HintBlock` 一次注入，模型被动看；agentic 暴露 `search_knowledge` 工具，模型主动决定何时查、查几次。简单问答用 static 省事，复杂多步检索用 agentic 灵活。
- 话术：「static 被动注入，agentic 主动搜索，复杂任务用 agentic。」

**Q2：agentscope 2.0 的多 Agent 和 1.0 有什么本质区别？**
- 参考答案：1.0 是代码级编排（`Pipeline`/`MsgHub`，写死 Python）；2.0 是服务级编排——Leader Agent 通过 `TeamCreate`/`AgentCreate`/`TeamSay` 工具管理团队，Worker 是独立 session，MessageBus 解耦并发，换 Redis 即多租户扩展。编排由模型动态决策而非代码静态固定。
- 源码佐证：`app/_tool/_team_create.py` 等五个团队工具 + `app/message_bus/`。
- 话术：「1.0 代码写死 pipeline，2.0 leader 用工具动态调度团队，多 Agent 协作本质是工具调用。」

**Q3：Leader-Worker 怎么通信？怎么扩展？**
- 参考答案：通过 `TeamSay` 单播/广播，消息走 MessageBus（单机 InMemory / 分布式 Redis），Worker 独立 session 隔离、可并发。换 Redis MessageBus + 多 worker 进程即横向扩展、多租户。SessionService 管生命周期与级联清理。
- 话术：「TeamSay 走消息总线，单机内存/分布式 Redis 任选，换 Redis 即扩展。」

**Q4：怎么把 Agent 变成生产服务？**
- 参考答案：用 `app/` 服务层（FastAPI），`reply_stream` 包成 `GET /sessions/{sid}/stream` 长连接 SSE，`POST` 触发 run，事件异步下发符合 ag-ui-protocol。SessionService 管多会话状态（Redis）。见 `examples/agent_service/main.py`。
- 话术：「reply_stream 包成 SSE 长连接，SessionService 管状态，Redis 存储扩展。」

## 6. 从 1.0 到 2.0 / 避坑

- 1.0：`from agentscope.pipelines import SequentialPipeline, MsgHub` → 2.0：**整个 pipelines 模块删除**，多 Agent 用服务层 Team 工具。这是迁移最痛的点，别再找 Pipeline。
- 1.0：多 Agent 代码 `pipeline([a,b,c])(msg)` → 2.0：leader `TeamCreate`+`AgentCreate`+`TeamSay`。
- 1.0：RAG 是独立模块、接入较繁 → 2.0：`KnowledgeBase` + `RAGMiddleware` / `search_knowledge` 工具，static/agentic 双模式开箱即用。
- 找编排原语找不到是对的——2.0 的编排"藏在服务层工具里"，不在框架核心类。

## 附：本周 checkpoint

- [ ] 作业 1 跑通：Agent 基于检索片段回答（非瞎编）
- [ ] 作业 2 跑通：看到 leader 用工具调度 worker
- [ ] 作业 3：curl 看到 SSE 事件流
- [ ] 能讲清"2.0 多 Agent = leader 工具调度 + MessageBus"，不再找 Pipeline

---
框架阶段（W04-W08）完成。下阶段进入 [W09 Runtime 与 SSE 状态机](../阶段三-产品/W09-Runtime与SSE状态机.md)——从"用框架"到"拆解真实产品 QwenPaw"。