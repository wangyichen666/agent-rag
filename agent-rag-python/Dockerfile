FROM python:3.11-slim AS base

WORKDIR /srv

# 基础依赖（模型推理依赖单独一层，便于缓存与裁剪）
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 模型推理依赖（GPU 镜像可换 torch cu 版本源）
RUN pip install --no-cache-dir torch --index-url https://download.pytorch.org/whl/cpu \
    && pip install --no-cache-dir FlagEmbedding>=1.2.10

COPY app ./app

ENV RAG_PORT=8000
EXPOSE 8000

CMD ["python", "-m", "app.main"]
