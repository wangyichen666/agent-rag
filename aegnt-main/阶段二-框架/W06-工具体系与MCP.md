# W06 · 工具体系与 MCP

> 本周目标 | 会用 FunctionTool/ToolBase/ToolGroup；理解 MCP 客户端；把 MCP 接进 Toolkit；理解权限五档。
> JD 考点：MCP Client/Server、工具注册中心、动态发现、权限、超时重试、标准化接口协议。

## 1. 本周你将搞懂什么

W03 你手写的工具是"函数名 → 字典映射"，很糙。真实工程里工具体系要解决：怎么从 Python 函数自动生成 schema？工具怎么分组按需激活而非全显示？外部 MCP 工具怎么动态发现？工具调用要不要鉴权？超时/重试怎么做？

agentscope 2.0 的 `tool/` 子系统回答了这些。本周吃透它。

> 重要定位：agentscope 是 **MCP 客户端**（消费别人提供的 MCP 工具）。**MCP Server 端**（自建一个对外暴露工具的服务）放到毕业项目 W11-W12，本周只讲客户端。

## 2. 原理铺垫

### 2.1 三种工具来源

1. **FunctionTool**：包一个本地 Python 函数，从签名+docstring 自动生成 schema。最常用。
2. **ToolBase 子类**：要更强控制（自定义权限、状态、schema）时继承它。MCP/A2A 适配器就是这么做的。
3. **MCPTool**：从远端 MCP Server 动态拉来的工具，客户端不写实现，只做代理调用。

三种都注册进同一个 `Toolkit`，对模型一视同仁——模型不关心工具是本地函数还是远端 MCP。

### 2.2 ToolGroup：工具不是"全可见"的

老做法：所有工具一股脑塞给模型。问题：工具一多，模型选择困难、token 浪费、误调用。

2.0 用 **ToolGroup**：工具分组，每轮只激活需要的组，用元工具 `ResetTools` 切换。类似"工具箱里分 Drawer，按任务打开对应抽屉"。

### 2.3 MCP 是什么

MCP（Model Context Protocol）是个**标准协议**，让"工具/资源/Prompt"能被任何客户端（Claude Code、Cursor、agentscope…）统一发现和调用。你起一个 MCP Server 暴露工具，任何 MCP 客户端都能动态 `list_tools` 拿到、`call_tool` 调用——解耦了 Agent 和工具实现。

两个 transport：`Stdio`（命令行拉起 server 进程，stdio 通信，本地用）和 `Http`（HTTP/SSE，远程用）。

### 2.4 权限五档

`PermissionMode`（`permission/_types.py:18`）：DEFAULT / ACCEPT_EDITS / EXPLORE / BYPASS / DONT_ASK。配合 `PermissionDecision`（`:99`）：ALLOW / DENY / ASK / PASSTHROUGH。工具调用前过权限引擎，可以放行/拒绝/问人/透传。W10 会讲 QwenPaw 怎么把这套加厚成企业级策略。

## 3. 源码精读

### 3.1 FunctionTool（`tool/_adapters.py:31`）

`FunctionTool.__init__(func, name=None, description=None, ...)`（`:19`）：传一个普通 Python 函数，它**从签名 + docstring 自动生成 JSON Schema**（`name` 默认取函数名，`description` 默认取 docstring）。返回值归一化成 `ToolResponse`。你在 W03 手写的 `TOOLS` 字典，这里一行搞定。

```python
FunctionTool(my_func, name="get_weather", description="查询天气")
```

### 3.2 Toolkit（`tool/_toolkit.py:66`）

`Toolkit.__init__`（`:88`）：聚合 `tools` / `skills_or_loaders` / `mcps` / `tool_groups`，是"唯一工具来源"。

- `get_tool_schemas()`（`:171`）：产出工具 schema 列表给模型（按激活组过滤）。
- `call_tool()`（`:225`）：统一流式调用入口，模型说"调 X",框架就在这执行。

### 3.3 ToolGroup（`tool/_tool_group.py:10`）

分组容器。Toolkit 维护 `activated_groups`，模型可调元工具 `ResetTools`（`tool/_builtin/_meta.py` 区）切换激活组，取代"工具全可见"。

### 3.4 MCPClient（`mcp/_mcp_client.py:24`）

2.0 的 MCP 客户端。两种配置（`mcp/_config.py`）：
- `StdioMCPConfig`（`:9`）：`command` 启动一个本地 server 进程（如 `npx @playwright/mcp`）。
- `HttpMCPConfig`（`:44`）：`url` 连远程 MCP（HTTP/SSE）。

`MCPClient.list_tools()`（`:348`）动态拉远端工具，转成 `MCPTool`（`tool/_adapters.py:167`）注册进 Toolkit。

### 3.5 内置工具（`tool/_builtin/`）

`_bash.py`(Bash) / `_read.py`(Read) / `_write.py`(Write) / `_edit.py`(Edit) / `_glob.py`(Glob) / `_grep.py`(Grep) / `_meta.py`(ResetTools 等元工具) / `_backend.py`(LocalBackend/DockerBackend)。任务工具 `tool/_task/`：TaskCreate/Update/List/Get（W04 提过，做 Plan-Execute 用）。

### 3.6 权限引擎

`Agent.__init__` 里 `self._engine = PermissionEngine(self.state.permission_context)`（`_agent.py:156`）。工具调用前过引擎，按 `PermissionMode` + 工具自己的 `check_permissions` 决定 ALLOW/DENY/ASK/PASSTHROUGH。W10 对比 QwenPaw 的 `PolicyGuardedTool`。

## 4. 动手作业

放 `code/w06/`。

### 作业 1：自定义 FunctionTool（带超时/重试）

`code/w06/custom_tool.py`：

```python
# code/w06/custom_tool.py
# 目标：用 FunctionTool 把一个 Python 函数变成 Agent 工具，体会"自动 schema"
import asyncio, os, functools
from agentscope.agent import Agent
from agentscope.credential import DashScopeCredential
from agentscope.message import UserMsg
from agentscope.model import DashScopeChatModel
from agentscope.tool import FunctionTool, Toolkit

def get_stock(symbol: str) -> str:
    """查询股票实时价格。

    Args:
        symbol: 股票代码，如 "AAPL" 或 "0700.HK"。
    """
    # mock，演示用。真实场景这里接行情 API。
    db = {"AAPL": "192.5", "0700.HK": "412.0"}
    return f"{symbol} 当前价格 {db.get(symbol, '未知')}"

async def main():
    model = DashScopeChatModel(
        credential=DashScopeCredential(api_key=os.environ["DASHSCOPE_API_KEY"]),
        model="qwen-plus", stream=True)
    agent = Agent(
        name="fin", system_prompt="你是金融助手，可查股价。",
        model=model,
        toolkit=Toolkit(tools=[FunctionTool(get_stock)]),  # 一行变工具
    )
    async for e in agent.reply_stream(UserMsg("u", "苹果和腾讯股价分别多少？")):
        if e.type.value == "text_block_delta":
            print(e.text_delta, end="", flush=True)
    print()

asyncio.run(main())
```

**预期**：Agent 调两次 `get_stock`（"AAPL"/"0700.HK"），汇总回答。注意你**没手写 JSON Schema**——FunctionTool 从 docstring `Args:` 段自动抽出来的。

> 超时/重试进阶：把 `get_stock` 用 `asyncio.wait_for(func(), timeout=5)` 包一层加超时；重试可用 `tenacity` 库装饰。本期示例先点到，W10 Loop 治理会接入框架级方案。

### 作业 2：接一个现成 MCP

`code/w06/mcp_client.py`：用 `MCPClient` 接高德 amap MCP（需自备 key）或 `@playwright/mcp`（需 node）。给两种 config 模板：

```python
# code/w06/mcp_client.py
import asyncio, os
from agentscope.agent import Agent
from agentscope.credential import DashScopeCredential
from agentscope.message import UserMsg
from agentscope.model import DashScopeChatModel
from agentscope.mcp import MCPClient, MCPClientConfig  # 按 2.0 实际导出调整
from agentscope.model._dashscope._config import StdioMCPConfig  # 路径以源码为准
from agentscope.tool import Toolkit

async def main():
    # 方式A：stdio 拉起 playwright MCP
    mcp_stdio = StdioMCPConfig(command="npx", args=["@playwright/mcp@latest"])
    # 方式B：http 连远程(填你的 url)
    # from agentscope.mcp._config import HttpMCPConfig
    # mcp_http = HttpMCPConfig(url="https://your-mcp-server/sse")

    client = MCPClient(configs=[mcp_stdio])
    tools = await client.list_tools()  # 动态发现远端工具
    print("发现 MCP 工具:", [t.name for t in tools])

    model = DashScopeChatModel(
        credential=DashScopeCredential(api_key=os.environ["DASHSCOPE_API_KEY"]),
        model="qwen-plus", stream=True)
    agent = Agent(name="web", system_prompt="你能操作浏览器", model=model,
                  toolkit=Toolkit(tools=tools))
    async for e in agent.reply_stream(UserMsg("u", "打开 example.com 截图")):
        if e.type.value == "text_block_delta":
            print(e.text_delta, end="", flush=True)
    print()

asyncio.run(main())
```

**预期**：先打印发现的 MCP 工具名列表，Agent 调 playwright 工具完成操作。**关键是"动态发现"**——你事先不知道 server 有什么工具，运行时 `list_tools` 拉取。

> import 路径与 `MCPClient`/config 的确切类名请对照你本机 `src/agentscope/mcp/__init__.py` 真实导出（不同小版本有微调），上面是结构示例。最小验证：先 `python -c "from agentscope.mcp import MCPClient; print(MCPClient)"`。

### 作业 3：体验 ToolGroup + ResetTools

建两个组（"读文件组": Read/Glob/Grep；"写文件组": Write/Edit），默认激活读组，让 Agent 做个只读任务；再让它切换到写组。体会"按需打开抽屉"。代码较长，参考 `tool/_tool_group.py:10` 注释与 `examples/` 里 group 用法。

## 5. 面试问答卡

**Q1：怎么把一个 Python 函数变成 Agent 工具？**
- 参考答案：`FunctionTool(func, name?, description?)`（`tool/_adapters.py:31`），从函数签名+docstring 自动生成 JSON Schema，返回值归一化成 `ToolResponse`，注册进 `Toolkit`。比手写字典稳，docstring 即文档即 schema。
- 话术：「FunctionTool 从 docstring 自动出 schema，函数即工具。」

**Q2：MCP 解决什么问题？agentscope 里怎么用？**
- 参考答案：MCP 标准化了工具/资源/Prompt 的发现与调用，让 Server 与 Client 解耦——一个 MCP Server 可被任何 MCP 客户端复用。agentscope 是客户端：用 `MCPClient`（`mcp/_mcp_client.py:24`）配 `StdioMCPConfig`/`HttpMCPConfig`，`list_tools()` 动态拉远端工具变现地 `MCPTool`，注册进 Toolkit 与本地工具一视同仁。
- 话术：「MCP 是工具的标准协议，agentscope 当客户端，动态发现 + 注册，本地远端工具同构。」

**Q3：ToolGroup 解决什么问题？**
- 参考答案：工具多了模型选择困难、token 浪费、误调用。ToolGroup（`tool/_tool_group.py:10`）把工具分组、按需激活，用元工具 `ResetTools` 切换,取代"全可见"。类似工具箱分抽屉。
- 话术：「工具分组按需激活，元工具 ResetTools 切换抽屉。」

**Q4：权限五档分别什么含义？**
- 参考答案：`PermissionMode`（`permission/_types.py:81`）：DEFAULT（默认问）、ACCEPT_EDITS（自动允许编辑类）、EXPLORE（只读探索）、BYPASS（全放行）、DONT_ASK（不问）。工具调用过 `PermissionEngine`，产出 ALLOW/DENY/ASK/PASSTHROUGH 决策。W10 QwenPaw 在其上加 `PolicyGuardedTool` 做企业级策略。
- 话术：「五档权限模式 + 四种决策，工具调用前过引擎，企业级再叠策略。」

## 6. 从 1.0 到 2.0 / 避坑

- 1.0：`ServiceToolkit` + `register_tool`，较繁琐 → 2.0：统一 `Toolkit`，函数即工具（FunctionTool）。
- 1.0：工具全可见 → 2.0：ToolGroup 分组按需激活。
- 2.0 新增：MCP 客户端（`mcp/`）、PermissionEngine、统一 `call_tool` 流式入口（`:225`）。
- agentscope **没有**内置 MCP Server——它是消费方。要自建 Server 看 W11-W12（可参考 QwenPaw `app/routers/mcp.py`）。

## 附：本周 checkpoint

- [ ] 作业 1 跑通：FunctionTool 自动 schema 生效
- [ ] 作业 2 跑通（或至少 `list_tools` 打印出 MCP 工具名）
- [ ] 能讲清 FunctionTool / ToolBase / MCPTool 三者区别
- [ ] 能背出权限五档

---
下周：[W07 中间件、记忆与上下文治理](W07-中间件记忆与上下文治理.md)——洋葱模型 + 三层记忆 + 拔掉 W03 的痛。