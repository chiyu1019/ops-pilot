"""集成测试：需要 Milvus 已启动（docker compose -f vector-database.yml up -d）

- Milvus 未启动时自动跳过
- DASHSCOPE_API_KEY 未配置时跳过需要调用 LLM 的用例
"""

import os
import socket

import pytest

MILVUS_HOST = os.environ.get("MILVUS_HOST", "localhost")
MILVUS_PORT = int(os.environ.get("MILVUS_PORT", "19530"))


def _milvus_reachable() -> bool:
    try:
        with socket.create_connection((MILVUS_HOST, MILVUS_PORT), timeout=1.5):
            return True
    except OSError:
        return False


requires_milvus = pytest.mark.skipif(
    not _milvus_reachable(), reason="Milvus 未启动，跳过集成测试"
)
requires_llm = pytest.mark.skipif(
    not os.environ.get("DASHSCOPE_API_KEY"), reason="未配置 DASHSCOPE_API_KEY，跳过 LLM 用例"
)


@pytest.fixture(scope="module")
def api_client():
    # 集成测试中关闭自动响应/沉淀，避免 lifespan 启动轮询触发真实诊断导致超时
    from app.config import config

    old_auto = config.auto_response_enabled
    old_distill = config.knowledge_distill_enabled
    config.auto_response_enabled = False
    config.knowledge_distill_enabled = False
    try:
        from fastapi.testclient import TestClient

        from app.main import app

        with TestClient(app) as client:
            yield client
    finally:
        config.auto_response_enabled = old_auto
        config.knowledge_distill_enabled = old_distill


@requires_milvus
def test_health(api_client):
    resp = api_client.get("/health")
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["status"] == "healthy"
    assert data["milvus"]["status"] == "connected"


@requires_milvus
def test_upload_document(api_client, tmp_path):
    md = tmp_path / "it_test_doc.md"
    md.write_text(
        "# 测试文档\n\n这是用于验证上传索引流程的测试内容，包含关键字：接口超时、服务降级。\n",
        encoding="utf-8",
    )
    with md.open("rb") as f:
        resp = api_client.post(
            "/api/upload",
            files={"file": ("it_test_doc.md", f, "text/markdown")},
        )
    assert resp.status_code == 200
    body = resp.json()
    assert body["code"] == 200
    assert body["data"]["filename"] == "it_test_doc.md"


@requires_milvus
@requires_llm
def test_chat_quick(api_client):
    resp = api_client.post(
        "/api/chat",
        json={"Id": "it-test-session", "Question": "你好"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["code"] == 200
    assert body["data"]["success"] is True
    assert body["data"]["answer"]
