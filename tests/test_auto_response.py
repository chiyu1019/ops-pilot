"""自动响应功能单元测试（不依赖 Milvus / LLM / 真实 Prometheus）"""

import pytest

import app.services.auto_response_service as ars
from app.api import alerts as alerts_api
from fastapi import FastAPI
from fastapi.testclient import TestClient


async def _fake_run_diagnosis(alert, task_input, session_id):
    return None


@pytest.fixture(autouse=True)
def _reset_state():
    ars._handled.clear()
    ars._events.clear()
    ars._seen_active_by_poll.clear()
    yield
    ars._handled.clear()
    ars._events.clear()
    ars._seen_active_by_poll.clear()


def test_alert_fingerprint_stable():
    a1 = {"labels": {"b": "1", "a": "2", "alertname": "X"}}
    a2 = {"labels": {"alertname": "X", "a": "2", "b": "1"}}
    assert ars.alert_fingerprint(a1) == ars.alert_fingerprint(a2)
    assert ars.alert_fingerprint(a1) != ars.alert_fingerprint({"labels": {"b": "2", "a": "2"}})


async def test_consume_alert_dedup_in_cooldown(monkeypatch):
    monkeypatch.setattr(ars.config, "alert_cooldown_seconds", 3600)
    monkeypatch.setattr(ars, "_run_diagnosis", _fake_run_diagnosis)

    alert = {"labels": {"alertname": "HighCPUUsage", "instance": "s1"}, "annotations": {}, "state": "firing"}
    assert await ars.consume_alert(alert) is True
    # 冷却期内同一告警不重复触发
    assert await ars.consume_alert(alert) is False

    types = [e["type"] for e in ars.get_events()]
    assert types.count("alert_received") == 1


async def test_consume_alert_different_fingerprint_triggers(monkeypatch):
    monkeypatch.setattr(ars.config, "alert_cooldown_seconds", 0)
    monkeypatch.setattr(ars, "_run_diagnosis", _fake_run_diagnosis)

    a1 = {"labels": {"alertname": "HighCPUUsage", "instance": "s1"}, "annotations": {}, "state": "firing"}
    a2 = {"labels": {"alertname": "HighMemoryUsage", "instance": "s2"}, "annotations": {}, "state": "firing"}
    assert await ars.consume_alert(a1) is True
    assert await ars.consume_alert(a2) is True


@pytest.fixture
def client():
    app = FastAPI()
    app.include_router(alerts_api.router)
    return TestClient(app)


def test_webhook_alertmanager_format(client, monkeypatch):
    calls = []

    async def fake_consume(alert):
        calls.append(alert)
        return True

    monkeypatch.setattr(ars, "consume_alert", fake_consume)

    resp = client.post(
        "/webhook/alerts",
        json={
            "status": "firing",
            "alerts": [
                {"labels": {"alertname": "A"}, "annotations": {}},
                {"labels": {"alertname": "B"}, "annotations": {}, "status": "resolved"},
            ],
        },
    )
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["received"] == 1
    assert data["triggered"] == 1
    assert len(calls) == 1
    assert calls[0]["labels"]["alertname"] == "A"


def test_webhook_single_alert_format(client, monkeypatch):
    async def fake_consume(alert):
        return True

    monkeypatch.setattr(ars, "consume_alert", fake_consume)
    resp = client.post(
        "/webhook/alerts",
        json={"labels": {"alertname": "Single"}, "annotations": {}},
    )
    assert resp.json()["data"]["triggered"] == 1


def test_alert_events_endpoint(client, monkeypatch):
    monkeypatch.setattr(ars, "get_events", lambda: [{"type": "alert_received", "alertname": "X"}])
    resp = client.get("/alerts/events")
    assert resp.status_code == 200
    assert resp.json()["data"][0]["alertname"] == "X"


# ---------- 「同一次告警只报一次」相关用例（本次新增能力） ----------

async def test_once_per_incident_never_retriggers(monkeypatch):
    """默认模式：同一次持续告警只处理一次，即使冷却窗口为 0 也不重复触发"""
    monkeypatch.setattr(ars.config, "alert_dedup_mode", "once_per_incident")
    monkeypatch.setattr(ars.config, "alert_cooldown_seconds", 0)
    monkeypatch.setattr(ars, "_run_diagnosis", _fake_run_diagnosis)

    alert = {"labels": {"alertname": "HighCPUUsage", "instance": "s1"},
             "annotations": {}, "state": "firing", "activeAt": "2026-09-22T10:00:00Z"}

    results = [await ars.consume_alert(alert) for _ in range(3)]
    assert results == [True, False, False], "同一告警事件只应触发一次"
    assert [e["type"] for e in ars.get_events()].count("alert_received") == 1


async def test_cooldown_mode_still_retriggers_after_expiry(monkeypatch):
    """兼容旧行为：显式切换到 cooldown 模式后，窗口过期仍会重新触发"""
    monkeypatch.setattr(ars.config, "alert_dedup_mode", "cooldown")
    monkeypatch.setattr(ars.config, "alert_cooldown_seconds", 0)
    monkeypatch.setattr(ars, "_run_diagnosis", _fake_run_diagnosis)

    alert = {"labels": {"alertname": "HighCPUUsage", "instance": "s1"},
             "annotations": {}, "state": "firing", "activeAt": "2026-09-22T10:00:00Z"}
    assert await ars.consume_alert(alert) is True
    assert await ars.consume_alert(alert) is True, "cooldown 模式下窗口过期应可再次触发"


async def test_resolved_allows_retrigger(monkeypatch):
    """恢复后再触发属于新事件，应重新诊断"""
    monkeypatch.setattr(ars.config, "alert_dedup_mode", "once_per_incident")
    monkeypatch.setattr(ars, "_run_diagnosis", _fake_run_diagnosis)

    alert = {"labels": {"alertname": "HighCPUUsage", "instance": "s1"},
             "annotations": {}, "state": "firing", "activeAt": "2026-09-22T10:00:00Z"}
    assert await ars.consume_alert(alert) is True
    assert await ars.consume_alert(alert) is False

    # 告警恢复 -> 清理去重状态
    assert ars.mark_resolved(alert) is True
    assert await ars.consume_alert(alert) is True, "恢复后再次触发应重新诊断"
    types = [e["type"] for e in ars.get_events()]
    assert "alert_resolved" in types


async def test_new_active_at_is_new_incident(monkeypatch):
    """activeAt 变化 = 新一次告警，应重新诊断"""
    monkeypatch.setattr(ars.config, "alert_dedup_mode", "once_per_incident")
    monkeypatch.setattr(ars, "_run_diagnosis", _fake_run_diagnosis)

    a1 = {"labels": {"alertname": "HighCPUUsage", "instance": "s1"},
          "annotations": {}, "state": "firing", "activeAt": "2026-09-22T10:00:00Z"}
    a2 = dict(a1, activeAt="2026-09-22T12:00:00Z")

    assert await ars.consume_alert(a1) is True
    assert await ars.consume_alert(a1) is False
    assert await ars.consume_alert(a2) is True, "activeAt 变化应视为新事件"


def test_webhook_resolved_clears_dedup_state(client, monkeypatch):
    """Webhook 收到 resolved 时应调用 mark_resolved 并计入 resolved 计数"""
    called = []

    async def fake_consume(alert):
        return True

    def fake_resolved(alert):
        called.append(alert)
        return True

    monkeypatch.setattr(ars, "consume_alert", fake_consume)
    monkeypatch.setattr(ars, "mark_resolved", fake_resolved)

    resp = client.post(
        "/webhook/alerts",
        json={"status": "resolved", "alerts": [{"labels": {"alertname": "A"}, "annotations": {}}]},
    )
    data = resp.json()["data"]
    assert data["triggered"] == 0
    assert data["resolved"] == 1
    assert len(called) == 1 and called[0]["labels"]["alertname"] == "A"
