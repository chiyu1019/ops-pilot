# ============================================================
# OpsPilot - 应用镜像（FastAPI + LangGraph Agent）
# 构建：docker compose build
# ============================================================
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# 先复制依赖声明并安装（层缓存：代码变更时无需重新安装依赖）
COPY pyproject.toml README.md ./
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir .

# 再复制源码（业务代码变更只影响这些层）
COPY app ./app
COPY notification ./notification
COPY mcp_servers ./mcp_servers
COPY static ./static
COPY aiops-docs ./aiops-docs

EXPOSE 9900

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "9900"]
