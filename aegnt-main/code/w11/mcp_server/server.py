# code/w11/mcp_server/server.py
# ============================================================
# W11 作业1:自建企业级 MCP Server(毕业项目核心)
# 要素:工具注册 + schema(装饰器自动) + 鉴权(token) + 超时 + 审计 + 危险拦截
# 对照 QwenPaw app/routers/mcp.py 的策略/白名单/审计(本文件是其简化骨架)
# 前置: uv pip install mcp
# 运行:  python code/w11/mcp_server/server.py  (作为 stdio MCP server 运行,
#        它自己不打印业务日志到 stdout——stdio 通道 stdout 会被协议占用。
#        审计写 stderr / 文件。下面用 NoneType 占位,实际请从环境读 token)
# 验证:  被 code/w11/team_skeleton.py 通过 MCPClient 接入并 list_tools
# ============================================================
import os
import time

from mcp.server.fastmcp import FastMCP  # uv pip install mcp

mcp = FastMCP("research-mcp")

# 鉴权 token(生产从密钥管理读,别硬编码)
API_TOKEN = os.environ.get("MCP_TOKEN", "dev-token")

# 假知识库(教学用;真实场景接 RAG/数据库)
KB = {
    "agent": "Agent 是能感知环境、自主决策、调用工具行动的智能体。",
    "react": "ReAct 是推理(Reasoning)与行动(Act)交替的 Agent 范式。",
    "mcp": "MCP 是 Model Context Protocol,标准化工具/资源的发现与调用。",
}


def _audit(tool: str, args: dict, ok: bool, result: str) -> None:
    """调用审计:记谁/何时/调什么/结果。生产落库,此处写 stderr。"""
    import sys

    line = (
        f"[AUDIT] ts={time.time():.0f} tool={tool} args={args} "
        f"ok={ok} res_len={len(result)}\n"
    )
    sys.stderr.write(line)  # 注意:stdout 被 MCP 协议占用,审计走 stderr
    sys.stderr.flush()


def _auth(token: str | None) -> bool:
    return token == API_TOKEN


@mcp.tool()
def search_kb(query: str, token: str = "") -> str:
    """在本地知识库搜索。

    Args:
        query: 搜索关键词(如 agent/react/mcp)。
        token: 调用凭证。
    """
    if not _auth(token):
        _audit("search_kb", {"query": query}, False, "unauthorized")
        return "ERROR: unauthorized"
    hits = [v for k, v in KB.items() if query.lower() in k]
    result = hits[0] if hits else f"未找到关于 {query} 的资料"
    _audit("search_kb", {"query": query}, True, result)
    return result


@mcp.tool()
def fetch_url(url: str, token: str = "") -> str:
    """抓取网页正文(带超时,拦危险 url)。

    Args:
        url: 要抓取的网址。
        token: 调用凭证。
    """
    if not _auth(token):
        _audit("fetch_url", {"url": url}, False, "unauthorized")
        return "ERROR: unauthorized"
    # 简易沙箱:拦截内网/本地/文件协议(防 SSRF/读本地文件)
    if any(b in url for b in ("file://", "127.0.0.1", "localhost", "169.254", "::1")):
        _audit("fetch_url", {"url": url}, False, "blocked")
        return "ERROR: blocked dangerous url"
    # 生产用 httpx + readability 抽正文,带超时。此处 mock
    result = f"（模拟抓取 {url} 的正文内容……）"
    _audit("fetch_url", {"url": url}, True, result)
    return result


if __name__ == "__main__":
    # stdio 传输:被 MCPClient(StdioMCPConfig) 拉起
    mcp.run(transport="stdio")