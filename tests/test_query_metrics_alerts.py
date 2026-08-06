"""Prometheus 告警工具单元测试（不依赖真实 Prometheus）"""

from datetime import datetime, timezone

import httpx

from app.tools.query_metrics_alerts import (
    _labels_identity,
    _pick_common_labels,
    _simplify_alerts,
    calculate_duration,
    query_prometheus_alerts_api,
)


def test_labels_identity_is_stable():
    a = {"b": "1", "a": "2", "alertname": "HighCPU"}
    b = {"alertname": "HighCPU", "a": "2", "b": "1"}
    assert _labels_identity(a) == _labels_identity(b)


def test_pick_common_labels():
    labels = {"alertname": "HighCPU", "severity": "critical", "pod": "api-0", "custom": "x"}
    picked = _pick_common_labels(labels)
    assert "alertname" not in picked
    assert picked["severity"] == "critical"
    assert picked["pod"] == "api-0"
    assert "custom" not in picked


def test_calculate_duration_never_unknown_for_valid_input():
    # 使用固定的历史时间，保证与当前时间的差值始终有效
    active_at = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    duration = calculate_duration(active_at)
    assert duration != "unknown"
    assert duration[-1] in ("s", "m", "h")


def test_simplify_alerts_dedup_and_sort():
    payload = {
        "data": {
            "alerts": [
                {
                    "labels": {"alertname": "HighCPU", "severity": "critical"},
                    "annotations": {"description": "cpu 高"},
                    "state": "firing",
                    "activeAt": "2026-08-06T10:00:00Z",
                },
                {
                    "labels": {"alertname": "HighCPU", "severity": "critical"},
                    "annotations": {},
                    "state": "firing",
                    "activeAt": "2026-08-06T10:01:00Z",
                },
                {
                    "labels": {"alertname": "HighMem"},
                    "annotations": {},
                    "state": "pending",
                    "activeAt": "2026-08-06T09:00:00Z",
                },
            ]
        }
    }
    alerts, counts = _simplify_alerts(payload)

    assert len(alerts) == 2  # 相同 labels 的重复告警只保留一条
    assert counts == {"firing": 1, "pending": 1}  # 去重后按唯一告警计数
    assert alerts[0]["alert_name"] == "HighCPU"  # 最新的 activeAt 排在最前


def test_query_alerts_api_returns_error_tuple(monkeypatch):
    class FakeResponse:
        def raise_for_status(self):
            raise httpx.HTTPError("boom")

    class FakeClient:
        def __init__(self, *args, **kwargs):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def get(self, url):
            return FakeResponse()

    import app.tools.query_metrics_alerts as mod

    monkeypatch.setattr(mod.httpx, "Client", FakeClient)
    body, err = query_prometheus_alerts_api()
    assert body == {}
    assert err and "boom" in err
