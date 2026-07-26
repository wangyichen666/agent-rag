# code/ · 12 周可运行作业代码

> 每周一个子目录，代码自包含、能跑。所有路径相对于本目录（`2027年/code/`）。

## 0. 环境准备（一次性）

```bash
# Python >= 3.11
mkdir -p ~/agent-lab && cd ~/agent-lab
uv venv --python 3.12 && source .venv/bin/activate

# 框架 + 通用依赖
uv pip install "agentscope==2.0.4" openai httpx pydantic pyyaml
# 服务化(RAG/MCP/SSE 相关周次)
uv pip install "mcp" fastapi "uvicorn[standard]"

# API Key(必填 DashScope;阶段二起部分周次可选 Claude/OpenAI)
export DASHSCOPE_API_KEY="sk-xxxxxxxx"
# W11 自建 MCP Server 的鉴权 token
export MCP_TOKEN="dev-token"
```

> 运行任何脚本前，确保在 `2027年/` 的上级能 `import agentscope`（即上面 venv 已激活）。
> 所有脚本**从 `2027年/` 目录运行**，例如 `python code/w04/quickstart.py`。

## 1. 重要 API 约定（踩过坑总结）

- **事件文本增量字段是 `event.delta`，不是 `text_delta`**。 Consumption 写法：
  ```python
  from agentscope.event import EventType
  async for e in agent.reply_stream(UserMsg("u", "你好")):
      if e.type == EventType.TEXT_BLOCK_DELTA:
          print(e.delta, end="", flush=True)
  ```
- **统一 Agent**：`from agentscope.agent import Agent`（模块名单数）。无 ReActAgent/DialogAgent 子类。
- **全异步**：`await agent.reply(...)` 或 `async for e in agent.reply_stream(...)`，无同步 `agent(msg)`。
- **MCP**：`from agentscope.mcp import MCPClient, StdioMCPConfig, HttpMCPConfig`。Stdio 必须 `is_stateful=True` 且 `await client.connect()`；用完 `await client.close()`。
- **自定义 FunctionTool 默认权限 ASK**：教学脚本设 `PermissionMode.BYPASS`/`ACCEPT_EDITS` 跳过确认，生产应配精确权限。
- **RAG**：`RAGMiddleware(knowledge_bases=[kb])` 默认 agentic（暴露 `search_knowledge` 工具）；static 模式传 `parameters=RAGMiddleware.Parameters(mode="static")`。

## 2. 每周运行清单

| 周次 | 脚本 | 依赖 | 说明 |
|---|---|---|---|
| w00 | `hello_agent.py` | agentscope, DASHSCOPE | 环境验收，跑通第一个 Agent |
| w01 | `sse_handwrite.py` | httpx, DASHSCOPE | 手写 SSE 流式解析 |
| w01 | `concurrent_providers.py` | httpx, DASHSCOPE | 并发 vs 串行对比 |
| w02 | `react_prompt.py` | openai, DASHSCOPE | 纯 prompt 演绎 ReAct 格式 |
| w02 | `cot_compare.py` | openai, DASHSCOPE | CoT vs 直接回答 |
| w03 | `react_handcraft.py` | openai, DASHSCOPE | **手写 50 行 ReAct**（不依赖框架） |
| w03 | `plan_execute.py` | openai, DASHSCOPE | 手写 Plan-Execute |
| w04 | `quickstart.py` | agentscope, DASHSCOPE | 框架最小 Agent + 事件流 |
| w04 | `reply_final_msg.py` | agentscope, DASHSCOPE | reply() 拿最终 Msg + token |
| w05 | `event_colorize.py` | agentscope, DASHSCOPE | 事件流染色打印 |
| w05 | `structured.py` | agentscope+pydantic, DASHSCOPE | 结构化输出（Pydantic） |
| w06 | `custom_function_tool.py` | agentscope, DASHSCOPE | FunctionTool 自动 schema |
| w06 | `mcp_client.py` | agentscope+mcp+**Node.js** | 接 playwright MCP（需 npx） |
| w06 | `tool_group_switch.py` | agentscope, DASHSCOPE | ToolGroup + ResetTools 分组 |
| w07 | `audit_middleware.py` | agentscope, DASHSCOPE | 自定义审计中间件 |
| w07 | `long_memory.py` | agentscope, DASHSCOPE | AgenticMemory 自写 MEMORY.md |
| w08 | `rag_two_modes.py` | agentscope, DASHSCOPE | RAG static/agentic 双模式 |
| w08 | `multi_agent_local.py` | agentscope, DASHSCOPE | 多 Agent 协作（本地版） |
| w09 | `mini_runtime.py` | agentscope, DASHSCOPE | MiniRuntime + Envelope → SSE |
| w09 | `fastapi_sse.py` | +fastapi+uvicorn | SSE 端点，curl 验证 |
| w10 | `repeat_gate.py` | agentscope, DASHSCOPE | 自定义 Stop Gate |
| w10 | `tool_guard_demo.py` | pyyaml | YAML 危险命令拦截判定 |
| w11 | `mcp_server/server.py` | mcp | **自建 MCP Server**（被 w11 接入） |
| w11 | `team_skeleton.py` | agentscope+mcp, DASHSCOPE | leader+researcher+writer+reviewer 骨架 |
| w12 | `governed_agents.py` | agentscope, DASHSCOPE | BudgetGate 治理 |
| w12 | `app.py` | +fastapi+uvicorn | 毕业项目 SSE 服务入口 |
| w12 | `Dockerfile` | Docker | 容器化（`docker build`） |
| w12 | `讲稿.md` | — | 5 分钟面试话术 |

## 3. 快速冒烟测试（验证环境）

先跑这 3 个，全过说明环境 OK：

```bash
python code/w00/hello_agent.py        # 最小 Agent
python code/w03/react_handcraft.py    # 不依赖框架的 ReAct（验证 LLM + tools）
python code/w04/quickstart.py         # 框架 Agent + 事件流
```

## 4. 常见问题

- **`KeyError: 'DASHSCOPE_API_KEY'`** → 环境变量没设。
- **`ModuleNotFoundError: agentscope`** → venv 没激活或没装 agentscope==2.0.4（注意：别用装了旧版的 Python）。
- **w06/w11 MCP 连不上** → w06 需 Node.js（npx）；w11 的 `mcp_server/server.py` 用当前 Python 跑，确保 `uv pip install mcp`。
- **w07 写不出 MEMORY.md** → 确认 `PermissionMode.ACCEPT_EDITS` + workspace 权限已配（脚本内已处理）。
- **w08 RAG 报 embedding 模型错** → DashScope 用 `text-embedding-v4`，确认账号开通了该模型。
- **事件没文字输出** → 检查是不是写成了 `event.text_delta`（应是 `event.delta`），或没有 `stream=True`。

## 5. 代码与正文对照

每篇代码顶部注释都标了「对照 W## 正文哪一节」和「预期输出」。遇到代码与 weekly 正文里片段不完全一致时，**以本目录代码为准**（这里行号/API 都按 agentscope 2.0.4 实际核对过）。

## 6. 诚实边界

- 我无法在你机器上逐行运行验证（无你的 key/环境）。所有代码按 agentscope **2.0.4 源码真实 API** 编写。
- 少数带外部依赖的脚本（w06 需要 Node、w08 用 DashScope embedding、w09/w12 起服务）需你按顶部注释配好环境。
- 如遇 2.0.4 小版本 API 微调，以报错信息 + `agentscope/src/agentscope/` 源码为准微调。