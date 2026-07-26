# code/w08/rag_two_modes.py
# ============================================================
# W08 作业1:建知识库做 RAG,对比 static(自动注入)与 agentic(主动搜索)两种模式
# 对照官方示例:examples/rag/integrate_with_agent.py
# 前置: export DASHSCOPE_API_KEY="sk-xxx"
# 运行:  python code/w08/rag_two_modes.py
# 预期:
#   - 索引一段 FAQ 文本到向量库(Qdrant 内存版,零外部依赖)
#   - static 模式:自动检索用 HintBlock 注入,Agent 据此答
#   - agentic 模式:Agent 主动调 search_knowledge 工具检索再答
# ============================================================
import asyncio
import os

from agentscope.agent import Agent
from agentscope.credential import DashScopeCredential
from agentscope.embedding import DashScopeEmbeddingModel
from agentscope.message import UserMsg
from agentscope.middleware import RAGMiddleware
from agentscope.model import DashScopeChatModel
from agentscope.rag import (
    ApproxTokenChunker,
    KnowledgeBase,
    QdrantStore,
    TextParser,
)
from agentscope.tool import Toolkit

# 一段假 FAQ 文档(模型自带知识里没有的"虚构内容",验证它确实在用 RAG)
FAQ = b"""小白公司退货政策:
- 7天内未拆封商品可全额退款。
- 拆封商品需扣 20% 折旧费。
- 食品类商品一经售出不退换。
- 退款到原支付账户,3-5 工作日到账。
"""


async def build_kb() -> KnowledgeBase:
    # 注意:dimensions 是 __init__ 的第 3 个必填位置参数(契约层 required)
    # text-embedding-v4 支持 1024/768 等,这里用 1024
    embedding = DashScopeEmbeddingModel(
        credential=DashScopeCredential(api_key=os.environ["DASHSCOPE_API_KEY"]),
        model="text-embedding-v4",
        dimensions=1024,
    )
    kb = KnowledgeBase(
        name="faq",
        description="小白公司退货政策FAQ",
        embedding_model=embedding,
        vector_store=QdrantStore(location=":memory:"),  # 内存版,零依赖
        collection="faq",
    )
    # 解析 -> 分块 -> 入库
    parser = TextParser()
    chunker = ApproxTokenChunker(chunk_size=128, overlap=32)
    sections = await parser.parse(file=FAQ, filename="refund_policy.txt")
    chunks = await chunker.chunk(sections)
    await kb.insert_document(chunks)
    return kb


def make_model() -> DashScopeChatModel:
    return DashScopeChatModel(
        credential=DashScopeCredential(api_key=os.environ["DASHSCOPE_API_KEY"]),
        model="qwen-plus",
        stream=True,
    )


async def run(agent: Agent, query: str, tag: str) -> None:
    print(f"\n=== {tag} ===")
    print(f"👤 {query}")
    print("🤖 ", end="")
    async for e in agent.reply_stream(UserMsg("u", query)):
        if e.type.value == "TEXT_BLOCK_DELTA":
            print(e.delta, end="", flush=True)
    print()


async def main() -> None:
    kb = await build_kb()

    # ---- static 模式:首轮自动检索,HintBlock 一次性注入(模型被动看) ----
    static_mw = RAGMiddleware(
        knowledge_bases=[kb],
        parameters=RAGMiddleware.Parameters(mode="static"),
    )
    static_agent = Agent(
        name="static_qa",
        system_prompt="你是文档问答助手,根据检索到的资料回答。",
        model=make_model(),
        toolkit=Toolkit(),
        middlewares=[static_mw],
    )
    await run(static_agent, "拆封过的商品能退吗?扣多少?", "static 模式(自动注入)")

    # ---- agentic 模式:暴露 search_knowledge 工具,模型主动决定何时搜 ----
    agentic_mw = RAGMiddleware(knowledge_bases=[kb])  # 默认 agentic
    agentic_agent = Agent(
        name="agentic_qa",
        system_prompt="你是文档问答助手。需要查资料时用 search_knowledge 工具检索后再答。",
        model=make_model(),
        toolkit=Toolkit(),
        middlewares=[agentic_mw],
    )
    await run(agentic_agent, "退款多久到账?", "agentic 模式(主动搜索)")


if __name__ == "__main__":
    asyncio.run(main())