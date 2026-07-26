# W11 · 多 Agent 协作平台实战（上）

> 本周目标 | 搭出毕业项目骨架——研究+写作+审校 三 Agent 协作平台，并自建一个企业级 MCP Server 接入。
> JD 考点：多 Agent 编排、MCP Server 全链路（注册/schema/鉴权/超时重试/审计/沙箱）、Agent 工具化。

## 1. 本周你将搞懂什么

W08 你尝过框架的 Team 多 Agent。现在你要自己造一个**能当简历项目讲**的多 Agent 协作平台，场景定为「研究 + 写作 + 审校」：

```
用户提问 → Leader 拆任务
  ├→ Researcher（RAG + Web 检索，负责找资料）
  ├→ Writer（基于资料产出初稿）
  └→ Reviewer（审校纠错打分）
Leader 聚合 → 输出成稿
```

且本阶段并入一个**自建 MCP Server**：W6 只学了客户端，现在你从零搭一个 Server（把"搜索知识库/抓取 URL"等能力标准化暴露），供 Researcher Agent 调用。这是 JD 里 MCP 研发岗的核心。

本周搭骨架（通信/角色/MCP Server），下周 W12 加治理+Runtime+可观测性，达到毕业交付。

## 2. 原理铺垫（架构与数据流）

### 2.1 工程结构（文字版架构图）

```
multi-agent-platform/
├── mcp_server/              # 自建 MCP Server（企业级，供 Agent 调用）
│   ├── server.py            # MCP Server 入口（stdio/http）
│   ├── tools.py             # 工具实现：search_kb / fetch_url
│   ├── auth.py              # 鉴权（API key/token）
│   └── audit.py             # 调用审计日志
├── agents/
│   ├── leader.py            # Leader：拆任务/调度/聚合
│   ├── researcher.py        # Researcher：用 MCP + RAG 找资料
│   ├── writer.py            # Writer：产出初稿
│   └── reviewer.py          # Reviewer：审校打分
├── knowledge/               # 共享知识库（RAG）
├── runtime/                 # 迷你 Runtime + Envelope（W09 仿写）
├── app/                     # FastAPI + SSE
└── tests/
```

### 2.2 角色职责与通信时序

```
Leader 收到「写一篇 X 的科普文」:
  1. TeamCreate 建团队
  2. AgentCreate(researcher) → AgentCreate(writer) → AgentCreate(reviewer)
  3. TeamSay(researcher, "搜集 X 的要点") → 等 result
  4. TeamSay(writer, "基于资料写初稿:<资料>") → 等 draft
  5. TeamSay(reviewer, "审校:<draft>") → 等评分+修改建议
  6. (若评分低) TeamSay(writer, "按建议改:<建议>") → 再 review
  7. Leader 聚合输出
```

通信走 agentscope MessageBus（单机 InMemory 起步，可换 Redis）。Leader 调度本质是工具调用（W08 讲过），不是代码 pipeline。

### 2.3 MCP Server 要素（对标 JD）

一个企业级 MCP Server 要有：**工具注册**（声明 tools）、**schema**（JSON Schema 参数）、**鉴权**（谁能调）、**超时重试**、**调用审计**（记谁/何时/调什么/结果）、**简易沙箱**（fetch_url 防危险）。这些正好是 W10 学过的治理在 Server 侧的体现。

## 3. 源码精读（参考脚手架，绝对路径）

不是照抄，是借鉴写法：

### 3.1 MCP Server 产品级参考（QwenPaw）

- `app/routers/mcp.py`：FastAPI router 管理 MCP——`list_mcp_tools:78`、`update_mcp_tool_whitelist:102`（白名单）、`get/update_mcp_policy:125/139`（策略）、`create/toggle/get_mcp_client:179/194/214`（客户端管理）。看它怎么把"MCP 配置/权限/审计"做成管理 API。
- `drivers/handlers/mcp.py`：`MCPDriverHandler(DriverHandler):51`，`list_tools:124`——协议中立的驱动层，stdio/http 传输统一。
- `drivers/adapters/agentscope_tool.py`：`DriverCapabilityTool(ToolBase):135` 把 MCP 能力包成 agentscope 工具，`check_permissions:161` 把权限检查嵌入工具，`__call__:171` 执行。这是"外部能力 → 框架工具 → 安全调用"的桥。

### 3.2 多 Agent 参考

- `app/multi_agent_manager.py`：`MultiAgentManager:23`，`get_agent:54`、`reload_agent:321`（零停机热重载）。看它怎么管理多个 Agent 生命周期。
- agentscope 框架侧 `app/_tool/_team_create.py`/`_team_say.py`（W08）：Team 工具即编排，这才是你 Leader 要用的。
- `agents/react_agent.py:47`：QwenPaw 怎么扩展框架 Agent——你的 leader/researcher 等可仿这个 pattern（继承 `Agent` 加料）。

## 4. 动手作业

放 `code/w11/`。本周产出可跑骨架。

### 作业 1：自建 MCP Server

`code/w11/mcp_server/server.py`：用官方 `mcp` Python SDK 起一个 Server，暴露两个工具：`search_kb(query)`（查本地知识库）、`fetch_url(url)`（抓网页正文）。带鉴权 + 审计。

```python
# code/w11/mcp_server/server.py（骨架，用 mcp 官方 SDK）
# pip install mcp
import json, os, time
from mcp.server.fastmcp import FastMCP

mcp = FastMCP("research-mcp")
API_TOKEN = os.environ.get("MCP_TOKEN", "dev-token")

def _audit(tool: str, args: dict, ok: bool, result=""):
    """调用审计：记谁/何时/调什么/结果。生产落库，此处 print。"""
    print(f"[AUDIT] {time.time():.0f} tool={tool} args={args} ok={ok} "
          f"res_len={len(str(result))}")

def _auth(token: str | None) -> bool:
    return token == API_TOKEN

@mcp.tool()
def search_kb(query: str, token: str = "") -> str:
    """在本地知识库搜索。

    Args:
        query: 搜索关键词。
        token: 调用凭证。
    """
    if not _auth(token):
        _audit("search_kb", {"query": query}, False, "unauthorized")
        return "ERROR: unauthorized"
    # 简化：本地知识库 = 一个 dict
    kb = {"agent": "Agent 是能感知环境、自主决策、调用工具行动的智能体。",
          "react": "ReAct 是推理与行动交替的 Agent 范式。"}
    hits = [v for k, v in kb.items() if query.lower() in k]
    result = hits[0] if hits else "未找到相关资料"
    _audit("search_kb", {"query": query}, True, result)
    return result

@mcp.tool()
def fetch_url(url: str, token: str = "") -> str:
    """抓取网页正文（带超时，防危险 url）。"""
    if not _auth(token):
        _audit("fetch_url", {"url": url}, False, "unauthorized")
        return "ERROR: unauthorized"
    if any(b in url for b in ("file://", "127.0.0.1", "localhost")):
        _audit("fetch_url", {"url": url}, False, "blocked")
        return "ERROR: blocked dangerous url"
    # 生产用 httpx + readability 抽正文；此处 mock
    result = f"（模拟抓取 {url} 的正文内容...）"
    _audit("fetch_url", {"url": url}, True, result)
    return result

if __name__ == "__main__":
    mcp.run(transport="stdio")  # 本地用 stdio；生产可换 streamable-http
```

**预期**：这是个真的 MCP Server，任何 MCP 客户端（含 agentscope `MCPClient`）都能 `list_tools` 发现 `search_kb`/`fetch_url` 并调用。鉴权失败返回 `unauthorized`，危险 url 被拦，每次调用有 AUDIT。**对照 QwenPaw `app/routers/mcp.py` 的策略/白名单/审计，你的 Server 是其简化骨架。**

### 作业 2：搭 Leader + 三 Worker 骨架

`code/w11/agents/leader.py` 等：用 agentscope Team 模型。Leader 用 `TeamCreate`/`AgentCreate`/`TeamSay` 调度；三个 worker 各有 system_prompt；Researcher 用 W06 的 `MCPClient` 接你的 Server + RAG。

```python
# code/w11/agents/leader.py（骨架，对照 examples/agent_service/main.py 的 SubAgentTemplate）
import asyncio, os
from agentscope.agent import Agent
from agentscope.credential import DashScopeCredential
from agentscope.message import UserMsg
from agentscope.model import DashScopeChatModel
from agentscope.mcp._config import StdioMCPConfig
from agentscope.mcp import MCPClient
from agentscope.tool import Toolkit, FunctionTool

def make_model():
    return DashScopeChatModel(
        credential=DashScopeCredential(api_key=os.environ["DASHSCOPE_API_KEY"]),
        model="qwen-plus", stream=True)

async def build_researcher():
    # 把作业1的 MCP Server 作为 stdio 工具接进 Researcher
    mcp = MCPClient(name="research", is_stateful=True,
                    mcp_config=StdioMCPConfig(
                        command="python", args=["code/w11/mcp_server/server.py"],
                        env={"MCP_TOKEN": "dev-token"}))
    await mcp.connect()
    tools = await mcp.list_tools()  # 发现 search_kb / fetch_url
    return Agent(name="researcher",
                 system_prompt="你是资料研究员，用 MCP 工具搜索知识库/抓网页找资料，输出要点。",
                 model=make_model(), toolkit=Toolkit(tools=tools))

async def build_writer():
    return Agent(name="writer",
                 system_prompt="你是写手，基于资料写一篇结构清晰的科普初稿。",
                 model=make_model(), toolkit=Toolkit())

async def build_reviewer():
    return Agent(name="reviewer",
                 system_prompt="你是审校，给文章打分(1-10)并指出问题，必要时给修改建议。",
                 model=make_model(), toolkit=Toolkit())

async def main():
    researcher = await build_researcher()
    writer = await build_writer()
    reviewer = await build_reviewer()
    leader = Agent(name="leader",
                   system_prompt="你是 Leader，依次让 researcher 查资料、writer 写稿、reviewer 审校，最终聚合。",
                   model=make_model(), toolkit=Toolkit())
    # 完整版用 TeamCreate/AgentCreate/TeamSay 编排(服务层)。
    # 单进程教学可先顺序 await 三个 Agent 模拟流水线，W12 再升级为真 Team。
    from agentscope.message import AssistantMsg
    query = "写一篇 200 字的『什么是 AI Agent』科普"
    r1 = await researcher.reply(UserMsg("u", query))
    r2 = await writer.reply(UserMsg("u", f"资料:{r1.get_text_content()}\n任务:{query}"))
    r3 = await reviewer.reply(UserMsg("u", f"审校:{r2.get_text_content()}"))
    print("最终审校意见:", r3.get_text_content())

asyncio.run(main())
```

> import 与 Team 工具确切 API 以本机 agentscope 导出为准（参考 `examples/agent_service/main.py`）。本周先跑通"顺序流水线"骨架，验证三个角色 + MCP 接入通；W12 升级为真 Team（MessageBus 异步）。

**预期**：researcher 调 `search_kb` 拿到"Agent 是…智能体"，writer 据此写初稿，reviewer 给评分与建议。三角色 + 自建 MCP 跑通。

### 作业 3：升级为真 Team（进阶）

若有余力，参照 `examples/agent_service/main.py` 起服务，用 `TeamCreate`/`AgentCreate`/`TeamSay` 把上面顺序流改成真异步团队（leader spawn worker、TeamSay 通信）。这是 W12 的重点，本周先试。

## 5. 面试问答卡

**Q1：你的多 Agent 平台怎么编排？为什么不用代码 pipeline？**
- 参考答案：Leader-Worker 模型，Leader 用 agentscope 服务层 Team 工具（`TeamCreate`/`AgentCreate`/`TeamSay`）动态调度 researcher/writer/reviewer，消息走 MessageBus。不用代码 pipeline 因为编排由模型按任务动态决策（资料不够再查、稿差再审），比写死 `pipeline([a,b,c])` 灵活、可扩展、可多租户。
- 话术：「Leader 用 Team 工具动态调度三 worker，编排由模型决策而非写死代码。」

**Q2：你自建的 MCP Server 有哪些企业级要素？**
- 参考答案：工具注册（FastMCP `@mcp.tool`）、JSON Schema（签名+docstring 自动）、鉴权（API token 校验）、超时（fetch_url 限时）、调用审计（记谁/何时/调什么/结果）、简易沙箱（拦截 file://、内网 url）。对照 QwenPaw `app/routers/mcp.py` 的策略/白名单/审计，是其简化版。
- 话术：「注册+schema+鉴权+超时+审计+危险拦截，对标 QwenPaw MCP 管理面。」

**Q3：Researcher 怎么用上你自建的 Server？**
- 参考答案：用 agentscope `MCPClient`（`mcp/_mcp_client.py:24`）配 `StdioMCPConfig` 拉起 Server 进程，`list_tools` 动态发现 `search_kb`/`fetch_url` 变 `MCPTool` 注册进 Researcher 的 Toolkit，模型像调本地工具一样调。对照 QwenPaw `DriverCapabilityTool`（`drivers/adapters/agentscope_tool.py:135`）。
- 话术：「MCPClient stdio 拉起 Server，list_tools 发现工具注册进 Toolkit，本地远端同构。」

**Q4：researcher/writer/reviewer 上下文怎么隔离与聚合？**
- 参考答案：每个 worker 独立 session/Agent 实例，context 天然隔离；Leader 通过 TeamSay 单播只把需要的产物（资料/初稿）传给下游，不让全量历史串味；Leader 最后聚合三份产物。这就是 W02 讲的"上下文隔离与结果聚合"在工程上的落地。
- 话术：「各 worker 独立 context 隔离，Leader 只传必要产物，最后聚合，避免历史串味。」

## 6. 从 1.0 到 2.0 / 避坑

- 多 Agent 别再找 `Pipeline`/`MsgHub`（W08 强调过）——用服务层 Team 工具。
- MCP Server 是你自己起的进程（`mcp` SDK），不是 agentscope 提供——agentscope 只消费。
- 本周先顺序流水线跑通骨架，别一上来就追求真异步 Team（易卡在 MessageBus 配置）。W12 再升级。
- 鉴权 token 别硬编码，从环境变量读；审计要落库别只 print（面试会被问）。

## 附：本周 checkpoint

- [ ] 作业 1：MCP Server 起来，`list_tools` 能看到 `search_kb`/`fetch_url`
- [ ] 作业 1：鉴权失败/危险 url 被拦，有 AUDIT 日志
- [ ] 作业 2：三角色 + MCP 接入跑通，顺序流水线出结果
- [ ] 能画出平台架构图（角色、通信、MCP 位置）

---
下周：[W12 毕业交付](W12-多Agent协作平台实战(下)-毕业交付.md)——加治理+Runtime+可观测性+Docker+话术，达到简历项目完成度。