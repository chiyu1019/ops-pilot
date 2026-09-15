"""通知注入点集成测试：验证 aiops_service 只在 source=alert_auto 时触发通知

做法：用假的 graph 替换真实工作流（不调用 LLM），直接验证收尾处的注入逻辑。
"""

import asyncio
from types import SimpleNamespace

import pytest

from app.config import config
from app.services.aiops_service import AIOpsService
from notification import SOURCE_ALERT_AUTO, SOURCE_USER_CHAT, notification_service

_FINAL_STATE = {
    "response": "# 诊断报告\n\n根因：死循环导致 CPU 打满。",
    "diagnosis": {"root_cause": "死循环导致 CPU 打满", "claims": [], "recommendations": ["重启实例"], "status": "verified"},
    "verification": {"strict_pass": True, "coverage": 1.0, "total_claims": 1, "supported_claims": 1},
    "evidence": [{"evidence_id": "ev-1", "tool": "query_cpu_metrics", "summary": "cpu avg=92"}],
    "past_steps": [("查询指标", "cpu avg=92")],
    "repair_rounds": 0,
}

_ALERT = {
    "labels": {"alertname": "CPUUsageHigh", "severity": "critical", "instance": "order-service"},
    "annotations": {"description": "CPU 持续超过 90%"},
}


class _FakeGraph:
    """假图：不跑真实工作流，只返回预设的最终状态"""

    def __init__(self, state):
        self._state = state

    async def astream(self, input=None, config=None, stream_mode=None):
        yield {"diagnose": {"diagnosis": self._state["diagnosis"], "verification": self._state["verification"]}}

    async def aget_state(self, config):
        return SimpleNamespace(values=self._state)


@pytest.fixture
def service_with_fake_graph(monkeypatch):
    """构造一个图被替换掉的 AIOpsService，并默认关闭知识沉淀（避免真实写入）"""
    svc = AIOpsService()

    async def _noop_ensure_graph():
        return None

    monkeypatch.setattr(svc, "_ensure_graph", _noop_ensure_graph)
    monkeypatch.setattr(svc, "graph", _FakeGraph(dict(_FINAL_STATE)))
    monkeypatch.setattr(config, "knowledge_distill_enabled", False)
    return svc


async def _drain(svc, source: str):
    async for _ in svc.execute("诊断任务", session_id=f"s-{source}", alert=_ALERT, source=source):
        pass
    await asyncio.sleep(0.05)  # 等待后台通知任务执行


async def test_alert_auto_triggers_notification(service_with_fake_graph, monkeypatch):
    calls = []

    async def fake_notify(**kwargs):
        calls.append(kwargs)
        return SimpleNamespace(sent=True)

    monkeypatch.setattr(notification_service, "notify_diagnosis", fake_notify)
    await _drain(service_with_fake_graph, SOURCE_ALERT_AUTO)

    assert len(calls) == 1, "自动告警入口应触发一次飞书通知"
    assert calls[0]["source"] == SOURCE_ALERT_AUTO
    assert calls[0]["alert"] == _ALERT
    assert calls[0]["session_id"] == "s-alert_auto"
    # 传入的 state 必须包含结构化诊断与校验结果
    assert "diagnosis" in calls[0]["state"] and "verification" in calls[0]["state"]


async def test_user_chat_does_not_trigger_notification(service_with_fake_graph, monkeypatch):
    calls = []

    async def fake_notify(**kwargs):
        calls.append(kwargs)
        return SimpleNamespace(sent=True)

    monkeypatch.setattr(notification_service, "notify_diagnosis", fake_notify)
    await _drain(service_with_fake_graph, SOURCE_USER_CHAT)

    assert calls == [], "用户对话入口不应触发飞书通知"


async def test_notification_failure_does_not_break_diagnosis(service_with_fake_graph, monkeypatch):
    async def boom(**kwargs):
        raise RuntimeError("feishu down")

    monkeypatch.setattr(notification_service, "notify_diagnosis", boom)

    events = []
    async for ev in service_with_fake_graph.execute("诊断任务", session_id="s-fail", alert=_ALERT, source=SOURCE_ALERT_AUTO):
        events.append(ev)
    await asyncio.sleep(0.05)

    # 诊断流程仍然完整产出报告（通知异常在后台任务中被吞掉）
    assert any(e.get("type") == "complete" for e in events)
    complete = [e for e in events if e.get("type") == "complete"][0]
    assert complete["response"]
