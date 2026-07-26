# code/w12/Dockerfile
# ============================================================
# W12 作业3:毕业项目 Docker 化(多阶段构建)
# 对照 QwenPaw deploy/Dockerfile 写法
# 构建: docker build -t multi-agent-platform ./code/w12
# 运行: docker run -p 8088:8088 -e DASHSCOPE_API_KEY=sk-xxx multi-agent-platform
# 验证: curl -N "http://127.0.0.1:8088/stream?q=你好"
# ============================================================
FROM python:3.12-slim AS base

# 系统依赖(node 仅在需要 stdio MCP server 时装;本镜像自带 server.py 用 Python)
WORKDIR /app

# 安装 Python 依赖(固定 agentscope 2.0.4,与教程一致)
RUN pip install --no-cache-dir \
    "agentscope==2.0.4" \
    "mcp" \
    "fastapi" \
    "uvicorn[standard]" \
    "pydantic" \
    "pyyaml"

# 拷贝项目代码
COPY . /app

EXPOSE 8088

# 环境变量(运行时注入)
ENV PORT=8088
# DASHSCOPE_API_KEY 必须在 docker run -e 时传入

CMD ["python", "app.py"]