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

    # ---- Embedding（BGE-M3）----
    embedding_model_name: str = "BAAI/bge-m3"
    embedding_device: str = "auto"          # auto / cpu / cuda / cuda:0
    embedding_batch_size: int = 32
    embedding_query_instruction: str = "为这个句子生成表示以用于检索相关文章："
    embedding_use_fp16: bool = True
    embedding_enabled: bool = True          # False 时用伪向量（仅联通性调试）

    # ---- Reranker ----
    reranker_model_name: str = "BAAI/bge-reranker-v2-m3"
    reranker_enabled: bool = True
    reranker_max_length: int = 1024

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
