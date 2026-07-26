# 面试问答卡 04 · 工具与 MCP

> 覆盖：W6 / W11。对应 JD：MCP Server/Client、工具注册中心、动态发现、权限、超时重试、标准化接口协议。

---

## Q1：MCP 是什么？为什么需要它？agentscope 是 Client 还是 Server？

### 【模范回答】

MCP，Model Context Protocol，模型上下文协议。它是一个**标准协议**，把「工具、资源、Prompt」的发现和调用标准化了。

要理解为什么需要它，先看没有 MCP 之前的痛点。假设你有 10 个不同的 Agent 框架（LangChain、agentscope、各种自研），还有 10 个不同的工具来源（公司内部 API、数据库、文件系统、第三方服务）。没有 MCP 时，每对「框架×工具」都要单独写适配——N×M 的集成地狱。而且每个框架定义工具的方式还不一样，工具换个框架就得重写。

MCP 干的事是**解耦**：它定义了一套标准协议——一个 MCP Server 按协议暴露工具，任何符合协议的 MCP Client 都能用同一套方式 `list_tools` 发现、`call_tool` 调用，不用关心 Server 内部是 Python 还是 Node、是本地还是远程。于是变成 N+M：N 个框架都支持 MCP 协议，M 个工具都做成 MCP Server，任意组合即插即用。工具做一次，到处能用；框架支持一次协议，接入所有工具。这就是协议层的价值，类似 USB 接口标准化。

关于 client/server 定位——**agentscope 是 MCP 客户端**。它用 `MCPClient` 去连接别人提供的 MCP Server，动态拉取工具列表、调用工具。agentscope 自己**不内置 MCP Server**。这一点 JD 里常问。所以「自建 MCP Server」是另一件事——你要自己用官方 `mcp` SDK（比如 FastMCP）起一个 Server 进程，把你的能力（查内部 wiki、调内部 API）按协议暴露出来，然后 agentscope 当客户端接入。这就是我毕业项目里做的：自己搭了个 research MCP Server，暴露 `search_kb`/`fetch_url`，Researcher Agent 通过 MCPClient 接入。

两种传输方式：**Stdio** 是用命令行拉起一个本地 Server 子进程，通过标准输入输出通信，适合本地开发（比如 `npx @playwright/mcp`）；**Http** 是连远程 MCP Server，适合云端部署。Stdio 模式必须是有状态连接（`is_stateful=True`，要显式 connect/close），Http 可以无状态。

> **要点速记**：① MCP 是工具/资源/Prompt 发现调用的标准协议；② 解决 N×M 集成地狱，变成 N+M 解耦（类似 USB）；③ agentscope 是 Client，不内置 Server；④ 自建 Server 用官方 mcp SDK（FastMCP）；⑤ 两种传输 Stdio（本地子进程，必有状态）/Http（远程，可无状态）。
>
> **源码佐证**：客户端 `MCPClient`（`mcp/_mcp_client.py:24`）+ `StdioMCPConfig`/`HttpMCPConfig`（`mcp/_config.py:9/44`）+ `list_tools`（:348）；产品级 Server 参考 QwenPaw `app/routers/mcp.py` + `drivers/handlers/mcp.py:51`。
>
> **压轴一句话**：MCP 是工具的 USB 接口——Server 按协议暴露、任意 Client 即插即用，把 N×M 集成降成 N+M；agentscope 当 Client 接入，自建 Server 用官方 SDK 另起进程。

---

## Q2：怎么把一个 Python 函数变成 Agent 工具？三种工具源有什么区别？

### 【模范回答】

agentscope 里工具主要有三种来源，都继承自 `ToolBase`，对模型一视同仁——模型不关心一个工具是本地函数还是远端 MCP，它只看到统一的 schema。

**第一种 FunctionTool，最常用**。把一个普通 Python 函数包成工具。做法是 `FunctionTool(my_func, name="...", description="...")`，它会**从函数的签名（类型注解）+ docstring 自动生成 JSON Schema**——函数名默认做工具名，docstring 的描述做工具说明，参数的类型注解做 schema 的 properties。比我 W3 手写 TOOLS 字典省心多了，而且 docstring 即文档即 schema，改一处全更新。工具的返回值会被归一化成 `ToolChunk`。

**第二种 ToolBase 子类**。当你要更强控制——比如自定义权限检查、维护内部状态、动态生成 schema 时，直接继承 `ToolBase` 实现 `__call__`、`check_permissions`、`input_schema`。MCP 工具适配器（MCPTool）就是这么做的。这种适合框架级适配，业务工具一般用 FunctionTool 就够。

**第三种 MCPTool**。从远端 MCP Server 动态拉来的工具。客户端本身不写实现，只是个代理——模型要调它，代理把请求转发给远端 Server 执行，再把结果转回来。命名上 MCPTool 带 `mcp__{server}__{tool}` 前缀，方便区分来源。

三种都注册进同一个 `Toolkit`。`Toolkit` 是工具的统一管理入口：`get_tool_schemas` 产出给模型的 schema 列表，`call_tool` 统一执行。模型说「调 X」，框架在 Toolkit 里找到 X、执行、回填。

这里还有个工程优化点——**ToolGroup 分组激活**。工具一多（几十上百个）全塞给模型，模型选择困难、token 浪费、还容易误调。2.0 用 `ToolGroup` 把工具分组，每轮只激活需要的组，用元工具 `ResetTools` 切换。注意 ResetTools 的输入是各分组的布尔值，代表**最终状态而非增量**——你传「激活 A」会停用其他所有非 basic 组，因为它先清空再设。所以叫 reset 不叫 switch。这个语义容易踩坑（我一开始就以为它是增量切换）。

> **要点速记**：① 三种工具源都继承 ToolBase，对模型一视同仁；② FunctionTool 从签名+docstring 自动生成 schema（最常用）；③ ToolBase 子类用于强控制（权限/状态/动态schema）；④ MCPTool 是远端 MCP 工具代理，命名带 mcp__ 前缀；⑤ Toolkit 统一管理；ToolGroup 分组按需激活，ResetTools 是最终状态非增量。
>
> **源码佐证**：`FunctionTool`（`tool/_adapters.py:31`）、`MCPTool`（:167）、`Toolkit`（`tool/_toolkit.py:66`，`get_tool_schemas:171`/`call_tool:225`）、`ToolGroup`（`tool/_tool_group.py:10`）、`ResetTools`（`tool/_builtin/_meta.py`）。
>
> **压轴一句话**：函数即工具（FunctionTool 自动抽 schema），三种源（FunctionTool/ToolBase子类/MCPTool）对模型一视同仁，Toolkit 统管；工具多了用 ToolGroup 分组按需激活，ResetTools 是最终状态不是增量切换。

---

## Q3：自建 MCP Server 要有哪些企业级要素？怎么做鉴权、动态发现、超时重试、审计？

### 【模范回答】

自建一个「能上线」的 MCP Server，不只是把函数暴露出去那么简单，至少要考虑这六件事——这正好对应 JD 里 MCP 研发岗的核心要求。

**一是工具注册**。用官方 SDK 的装饰器（如 FastMCP 的 `@mcp.tool()`）声明工具，SDK 自动从签名+docstring 生成标准 schema。一个 Server 可以注册多个工具。

**二是 JSON Schema 标准化**。每个工具的参数要有清晰的类型和描述，这样客户端 `list_tools` 拿到的 schema 是自描述的，模型能正确传参。docstring 写清楚每个参数含义，既是给模型看的，也是给调用方文档。

**三是鉴权**。不能让任何人都能调你的 Server。最简单的是 token 校验——每个工具调用要求带 token 参数，Server 端校验，失败返回 unauthorized。生产里要做成 scope/租户级的权限，不同 token 能调不同工具、看不同数据范围。对应 agentscope 客户端侧也有权限模式（PermissionMode 五档），但 Server 端要自己守门。

**四是超时与重试**。工具调用可能慢（外部 API）、可能偶发失败。客户端侧设 `execution_timeout`（MCPClient 的参数），超时就中断；可重试的失败自动重试。Server 端自己也要对外部依赖设超时，别让一个慢请求把 Server 拖死。

**五是调用审计**。每次工具调用要记录「谁（哪个 token/Agent）、何时、调了什么工具、传了什么参数、成功还是失败、结果摘要」——落库供合规追溯。这一条企业必备，否则出问题查不到是谁干的。我在毕业项目的 MCP Server 里就让每次调用都走一个 `_audit` 函数写日志。

**六是简易沙箱/危险拦截**。比如 `fetch_url` 这种工具，要拦截危险 URL（`file://`、内网地址、`127.0.0.1`），防 SSRF 和读本地文件；执行类工具要拦危险命令。这是 Server 侧的安全前置。

对照看 QwenPaw 的产品级实现，它的 `app/routers/mcp.py` 把这些做成了**管理面 API**——list_mcp_tools、update_mcp_tool_whitelist（工具白名单）、get/update_mcp_policy（策略）、create/toggle_mcp_client（客户端管理），相当于把上面这些要素可视化、可配置化了。我的 Server 是其简化骨架，但六要素齐备。MCP 这套「注册+schema+鉴权+超时重试+审计+沙箱」六件套，就是面试讲 MCP Server 时要铺开的点。

> **要点速记**：① 工具注册（装饰器自动 schema）；② schema 标准化（docstring 自描述）；③ 鉴权（token/scope/租户级）；④ 超时重试（client execution_timeout + server 侧超时）；⑤ 调用审计（谁/何时/调什么/参数/结果落库）；⑥ 简易沙箱（危险 URL/命令拦截）。六件套。
>
> **源码佐证**：Server 产品级参考 QwenPaw `app/routers/mcp.py`（list_mcp_tools:78/update_mcp_tool_whitelist:102/get_mcp_policy:125/create_mcp_client:179）、`drivers/handlers/mcp.py:51`（MCPDriverHandler）、`drivers/adapters/agentscope_tool.py:135`（DriverCapabilityTool，check_permissions:161）；客户端 `MCPClient.execution_timeout`（`mcp/_mcp_client.py:39`）。
>
> **压轴一句话**：企业级 MCP Server 六件套——注册+schema+鉴权+超时重试+审计+沙箱，QwenPaw 把它做成可视化管理面，我的毕设 Server 是带齐六要素的简化骨架。