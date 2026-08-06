# ============================================================
# SuperBizAgent - 应用镜像（FastAPI + LangGraph Agent）
# 构建：docker compose build
# ============================================================
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# 先复制依赖声明，利用镜像层缓存
COPY pyproject.toml README.md ./
COPY app ./app
COPY mcp_servers ./mcp_servers
COPY static ./static
COPY aiops-docs ./aiops-docs

RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir .

EXPOSE 9900

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "9900"]
