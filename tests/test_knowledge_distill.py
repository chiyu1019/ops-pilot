"""闭环沉淀功能单元测试（不依赖 Milvus / LLM）"""

import pytest

from app.services import knowledge_distill_service as kds


def test_fingerprint_stable_and_label_order_independent():
    a1 = {"labels": {"b": "1", "a": "2", "alertname": "X"}}
    a2 = {"labels": {"alertname": "X", "a": "2", "b": "1"}}
    assert kds.fingerprint(a1, "task") == kds.fingerprint(a2, "task")


def test_extract_alertname_from_labels():
    assert (
        kds.extract_alertname({"labels": {"alertname": "HighCPUUsage"}}, "任意输入")
        == "HighCPUUsage"
    )


def test_extract_alertname_from_task_input():
    task = "收到新告警：ServiceDown（级别 warning）影响服务 checkout-service..."
    assert kds.extract_alertname(None, task) == "ServiceDown"


def test_extract_alertname_fallback():
    assert kds.extract_alertname(None, "普通任务描述") == "AIOps诊断经验"


def test_source_path_deterministic():
    p1 = kds.source_path(None, "任务A", "X")
    p2 = kds.source_path(None, "任务A", "X")
    assert p1 == p2
    assert p1.startswith("generated/X-")
    assert p1.endswith(".md")


async def test_distill_writes_generated_document(monkeypatch):
    """验证：总结 -> 去重删除旧条目 -> 写入带 _generated 标记的文档。"""
    calls = {}

    async def fake_summarize(alert_info, steps_info, report):
        return "# 经验：HighCPUUsage\n\n根因：CPU 打满。"

    monkeypatch.setattr(kds, "_summarize", fake_summarize)
    monkeypatch.setattr(
        kds.vector_store_manager,
        "delete_by_source",
        lambda source: calls.setdefault("deleted", source),
    )
    monkeypatch.setattr(
        kds.vector_store_manager,
        "add_documents",
        lambda docs: calls.setdefault("docs", docs),
    )

    ok = await kds.distill(
        alert={"labels": {"alertname": "HighCPUUsage", "instance": "s1"}},
        task_input="收到新告警：HighCPUUsage...",
        past_steps=[("查询日志", "发现大量超时"), ("查询监控", "CPU 95%")],
        response="# 告警分析报告\nCPU 过高",
    )
    assert ok is True
    assert calls["deleted"].startswith("generated/HighCPUUsage-")
    assert calls["docs"][0].metadata["_generated"] == 1
    assert calls["docs"][0].metadata["_alertname"] == "HighCPUUsage"


async def test_distill_skips_empty_response(monkeypatch):
    called = {}

    async def fake_summarize(alert_info, steps_info, report):
        called["summarize"] = True
        return "x"

    monkeypatch.setattr(kds, "_summarize", fake_summarize)
    assert await kds.distill(None, "任务", [], "") is False
    assert "summarize" not in called
