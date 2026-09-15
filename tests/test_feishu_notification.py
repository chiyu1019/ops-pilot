"""飞书通知单元测试（全部 mock 网络，不依赖真实 webhook）

覆盖要求：
1. 正常诊断结果可以发送（卡片字段完整、payload 结构正确）
2. webhook 为空时不发送（且不影响流程）
3. 飞书接口异常不影响 Agent（不抛异常）
4. 来源过滤：只有 alert_auto 推送，user_chat 不推送
5. 幂等保护：同会话同告警同状态在窗口内只发一次
"""

import httpx
import pytest

from app.config import config
from notification import (
    SOURCE_ALERT_AUTO,
    SOURCE_USER_CHAT,
    DiagnosisNotification,
    NotificationService,
)
from notification.feishu import FeishuClient

# ---------- 测试用状态 ----------
def _state(status="verified", strict_pass=True, repair_rounds=0):
    return {
        "diagnosis": {
            "root_cause": "data-sync-service 出现死循环导致 CPU 打满",
            "claims": [
                {"claim": "CPU 持续超过 90%", "evidence_ids": ["ev-aaa"], "confidence": 0.9},
                {"claim": "日志出现大量超时", "evidence_ids": ["ev-bbb"], "confidence": 0.8},
            ],
            "recommendations": ["重启受影响实例", "排查近期发布", "为该服务增加 CPU 告警阈值"],
            "status": status,
        },
        "verification": {"strict_pass": strict_pass, "coverage": 1.0, "total_claims": 2, "supported_claims": 2},
        "evidence": [
            {"evidence_id": "ev-aaa", "tool": "query_cpu_metrics", "summary": "cpu_metrics：avg=92.5 max=98.1"},
            {"evidence_id": "ev-bbb", "tool": "search_log", "summary": "search_log：返回 42 条日志，疑似错误 12 次"},
        ],
        "repair_rounds": repair_rounds,
    }


_ALERT = {
    "labels": {"alertname": "CPUUsageHigh", "severity": "critical", "instance": "order-service"},
    "annotations": {"description": "order-service CPU 持续 5 分钟超过 90%"},
}


class _FakeResponse:
    def __init__(self, payload, status_code=200):
        self._payload = payload
        self.status_code = status_code

    def raise_for_status(self):
        if self.status_code >= 400:
            raise httpx.HTTPStatusError("boom", request=None, response=None)

    def json(self):
        return self._payload


@pytest.fixture
def posted(monkeypatch):
    """记录所有 httpx POST 请求，并返回可控响应"""
    calls = []
    payload = {"code": 0, "msg": "success"}

    async def fake_post(self, url, json=None, **kwargs):
        calls.append({"url": url, "json": json})
        return _FakeResponse(payload)

    monkeypatch.setattr(httpx.AsyncClient, "post", fake_post)
    return calls, payload


# ---------- 1) 卡片渲染 ----------
def test_build_card_contains_all_required_fields():
    n = DiagnosisNotification.from_agent_state(_state(), _ALERT, "任务描述", SOURCE_ALERT_AUTO, "auto-123")
    card = FeishuClient(webhook_url="https://example.com/hook").build_card(n)

    assert card["msg_type"] == "interactive"
    text = str(card)
    for expected in ["告警名称", "告警级别", "影响服务", "故障现象", "分析结论", "关键证据", "处理建议", "Agent执行状态", "生成时间"]:
        assert expected in text, f"卡片缺少字段: {expected}"


def test_from_agent_state_maps_evidence_and_suggestions():
    n = DiagnosisNotification.from_agent_state(_state(), _ALERT, "任务", SOURCE_ALERT_AUTO, "auto-123")

    assert n.alert_name == "CPUUsageHigh"
    assert n.severity == "critical"
    assert n.service == "order-service"
    assert "CPU 持续 5 分钟" in n.summary
    assert "死循环" in n.diagnosis
    # 证据来自 evidence_id -> EvidenceRecord.summary
    assert any("avg=92.5" in e for e in n.evidence)
    assert "1." in n.suggestion and "重启受影响实例" in n.suggestion
    assert "已验证" in n.status


def test_status_labels_preserve_three_states():
    for status, keyword in [("verified", "已验证"), ("hypothesis", "假设"), ("safe_report", "安全报告")]:
        n = DiagnosisNotification.from_agent_state(
            _state(status=status, strict_pass=(status == "verified")), _ALERT, "任务", SOURCE_ALERT_AUTO, "s"
        )
        assert keyword in n.status


def test_long_text_is_truncated():
    long_text = "长" * 2000
    state = _state()
    state["diagnosis"]["root_cause"] = long_text
    state["diagnosis"]["recommendations"] = [long_text]
    n = DiagnosisNotification.from_agent_state(state, _ALERT, long_text, SOURCE_ALERT_AUTO, "s")

    assert len(n.diagnosis) <= 800
    assert len(n.summary) <= 300


# ---------- 2) 正常发送 ----------
async def test_notify_success(posted):
    calls, _ = posted
    service = NotificationService(client=FeishuClient(webhook_url="https://example.com/hook"))
    result = await service.notify_diagnosis(_state(), _ALERT, "任务", "auto-1", SOURCE_ALERT_AUTO)

    assert result.sent is True
    assert len(calls) == 1
    assert calls[0]["url"] == "https://example.com/hook"
    assert calls[0]["json"]["msg_type"] == "interactive"
    assert "OpsPilot故障诊断报告" in str(calls[0]["json"])


# ---------- 3) webhook 为空 ----------
async def test_skip_when_webhook_not_configured(posted):
    calls, _ = posted
    service = NotificationService(client=FeishuClient(webhook_url=""))
    result = await service.notify_diagnosis(_state(), _ALERT, "任务", "auto-1", SOURCE_ALERT_AUTO)

    assert result.sent is False
    assert result.skipped is True
    assert result.reason == "webhook_not_configured"
    assert calls == []  # 没有发出任何请求


# ---------- 4) 飞书异常不影响 Agent ----------
async def test_feishu_error_does_not_raise(posted, monkeypatch):
    calls, _ = posted

    async def boom(self, url, json=None, **kwargs):
        raise httpx.ConnectError("connection refused")

    monkeypatch.setattr(httpx.AsyncClient, "post", boom)
    service = NotificationService(client=FeishuClient(webhook_url="https://example.com/hook"))

    result = await service.notify_diagnosis(_state(), _ALERT, "任务", "auto-1", SOURCE_ALERT_AUTO)

    assert result.sent is False
    assert "ConnectError" in (result.error or "")


async def test_feishu_nonzero_code_marks_failed(posted):
    _, payload = posted
    payload.clear()
    payload.update({"code": 19021, "msg": "invalid webhook"})

    service = NotificationService(client=FeishuClient(webhook_url="https://example.com/hook"))
    result = await service.notify_diagnosis(_state(), _ALERT, "任务", "auto-1", SOURCE_ALERT_AUTO)

    assert result.sent is False
    assert "19021" in (result.error or "")


# ---------- 5) 来源过滤（本次新增的核心需求） ----------
async def test_user_chat_source_is_not_pushed(posted):
    calls, _ = posted
    service = NotificationService(client=FeishuClient(webhook_url="https://example.com/hook"))
    result = await service.notify_diagnosis(_state(), _ALERT, "任务", "chat-1", SOURCE_USER_CHAT)

    assert result.sent is False
    assert result.reason == "source_not_allowed"
    assert calls == []  # 用户对话入口不推送


async def test_alert_auto_source_is_pushed(posted):
    calls, _ = posted
    service = NotificationService(client=FeishuClient(webhook_url="https://example.com/hook"))
    result = await service.notify_diagnosis(_state(), _ALERT, "任务", "auto-9", SOURCE_ALERT_AUTO)

    assert result.sent is True
    assert len(calls) == 1


# ---------- 6) 幂等保护 ----------
async def test_idempotency_prevents_duplicate(posted):
    calls, _ = posted
    service = NotificationService(client=FeishuClient(webhook_url="https://example.com/hook"))

    first = await service.notify_diagnosis(_state(), _ALERT, "任务", "auto-dup", SOURCE_ALERT_AUTO)
    second = await service.notify_diagnosis(_state(), _ALERT, "任务", "auto-dup", SOURCE_ALERT_AUTO)

    assert first.sent is True
    assert second.sent is False and second.reason == "duplicate"
    assert len(calls) == 1  # 只发了一次


async def test_idempotency_force_allows_resend(posted):
    calls, _ = posted
    service = NotificationService(client=FeishuClient(webhook_url="https://example.com/hook"))

    await service.notify_diagnosis(_state(), _ALERT, "任务", "auto-force", SOURCE_ALERT_AUTO)
    again = await service.notify_diagnosis(_state(), _ALERT, "任务", "auto-force", SOURCE_ALERT_AUTO, force=True)

    assert again.sent is True
    assert len(calls) == 2


async def test_different_alert_is_not_treated_as_duplicate(posted):
    calls, _ = posted
    service = NotificationService(client=FeishuClient(webhook_url="https://example.com/hook"))

    await service.notify_diagnosis(_state(), _ALERT, "任务", "auto-a", SOURCE_ALERT_AUTO)
    other_alert = {"labels": {"alertname": "HighMemoryUsage", "severity": "warning", "instance": "pay"}}
    result = await service.notify_diagnosis(_state(), other_alert, "任务", "auto-b", SOURCE_ALERT_AUTO)

    assert result.sent is True
    assert len(calls) == 2


# ---------- 7) 总开关与签名 ----------
async def test_notification_disabled_skips(posted, monkeypatch):
    calls, _ = posted
    monkeypatch.setattr(config, "notification_enabled", False)
    service = NotificationService(client=FeishuClient(webhook_url="https://example.com/hook"))

    result = await service.notify_diagnosis(_state(), _ALERT, "任务", "auto-x", SOURCE_ALERT_AUTO)

    assert result.sent is False and result.reason == "notification_disabled"
    assert calls == []


async def test_signature_added_when_secret_configured(posted):
    calls, _ = posted
    service = NotificationService(
        client=FeishuClient(webhook_url="https://example.com/hook", secret="test-secret")
    )
    await service.notify_diagnosis(_state(), _ALERT, "任务", "auto-sign", SOURCE_ALERT_AUTO)

    body = calls[0]["json"]
    assert "timestamp" in body and "sign" in body
