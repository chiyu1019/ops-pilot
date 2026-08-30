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
    yield
    ars._handled.clear()
    ars._events.clear()


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
