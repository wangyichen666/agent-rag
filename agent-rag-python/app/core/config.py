"""全局配置：全部支持环境变量覆盖（前缀 RAG_），详见 .env.example。"""
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="RAG_", env_file=".env", extra="ignore")

    # ---- 服务 ----
    app_name: str = "agent-rag-python"
    host: str = "0.0.0.0"
    port: int = 8000
    internal_token: str = "dev-internal-token"  # Java -> Python 内部鉴权

    # ---- 向量库 ----
    vector_store: str = "milvus"
    milvus_uri: str = "http://127.0.0.1:19530"
    milvus_collection: str = "rag_chunks"
    milvus_token: str = ""

    # ---- SiliconFlow API（Embedding / Rerank 共用）----
    siliconflow_api_key: str = ""
    siliconflow_base_url: str = "https://api.siliconflow.cn/v1"

    # ---- Embedding（SiliconFlow Qwen3-Embedding）----
    embedding_model_name: str = "Qwen/Qwen3-Embedding-0.6B"   # 0.6B=1024维, 4B=2560维, 8B=4096维
    embedding_enabled: bool = True          # False 时用伪向量（仅联通性调试）

    # ---- Reranker（SiliconFlow Qwen3-Reranker）----
    reranker_model_name: str = "Qwen/Qwen3-Reranker-0.6B"
    reranker_enabled: bool = True
    reranker_top_n: int = 5                 # 返回 top_n 个文档

    # ---- LLM（OpenAI 兼容协议：DeepSeek / 通义 / vLLM）----
    llm_base_url: str = "https://api.deepseek.com"
    llm_api_key: str = ""
    llm_model: str = "deepseek-chat"
    llm_timeout_s: int = 120

    # ---- Query 改写 ----
    rewrite_enabled: bool = True
    rewrite_model: str = ""                 # 为空则复用 llm_model
    rewrite_max_history_rounds: int = 4

    # ---- 切分默认值（请求可覆盖）----
    chunk_size: int = 512
    chunk_overlap: int = 64
    min_chunk_size: int = 50

    # ---- 检索默认值（请求可覆盖）----
    dense_top_k: int = 20
    sparse_top_k: int = 20
    rrf_k: int = 60
    rerank_top_n: int = 5
    score_threshold: float = 0.35
    search_ef: int = 64

    # ---- 知识图谱（Neo4j）----
    graph_enabled: bool = True              # False 时图谱构建与检索整体跳过
    neo4j_uri: str = "bolt://127.0.0.1:7687"
    neo4j_user: str = "neo4j"
    neo4j_password: str = "neo4j"
    graph_extract_model: str = ""           # 为空则复用 llm_model
    graph_extract_batch_size: int = 6       # 每次 LLM 抽取的 chunk 数（控制 token 成本）
    graph_max_hops: int = 2                 # 图检索实体扩展跳数
    graph_top_k: int = 8                    # 图通道返回的候选块数
    graph_visual_limit: int = 300           # 可视化接口默认返回节点上限

    # ---- 生成 ----
    temperature: float = 0.1
    max_tokens: int = 1024
    context_token_budget: int = 2000        # 检索上下文预算
    no_context_answer: str = (
        "根据当前知识库中的资料，无法回答该问题。"
        "您可以尝试换一种问法，或联系管理员补充相关文档。"
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()
