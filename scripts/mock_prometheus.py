"""模拟 Prometheus 服务：为 AIOps 演示提供告警数据

提供 GET /api/v1/alerts（与 Prometheus 告警 API 格式一致）。
告警内容与 aiops-docs 知识库文档对应，方便演示"告警 -> 检索知识库 -> 诊断报告"闭环。

用法：
    python scripts/mock_prometheus.py              # 默认监听 0.0.0.0:9090
    MOCK_PROM_PORT=9091 python scripts/mock_prometheus.py

Docker 模式：由 docker-compose.yml 中 mock-prometheus 服务启动，
应用容器通过 http://mock-prometheus:9090 访问；本地模式可直接运行本脚本。
"""

from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timedelta, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer


# 运行时动态追加的告警（POST /api/v1/alerts/trigger）
_EXTRA_ALERTS: list[dict] = []


def _rfc3339(offset_minutes: int) -> str:
    """返回 offset_minutes 分钟前的 RFC3339 时间（Prometheus activeAt 格式）。"""
    now = datetime.now(timezone.utc) - timedelta(minutes=offset_minutes)
    return now.strftime("%Y-%m-%dT%H:%M:%SZ")


def build_alerts_payload() -> dict:
    """构造与 Prometheus /api/v1/alerts 一致的响应。"""
    alerts = [
        {
            "labels": {
                "alertname": "HighCPUUsage",
                "severity": "critical",
                "instance": "data-sync-service",
                "job": "node-exporter",
                "namespace": "default",
            },
            "annotations": {
                "summary": "CPU 使用率过高",
                "description": "data-sync-service CPU 使用率持续 5 分钟超过 80%",
            },
            "state": "firing",
            "activeAt": _rfc3339(25),
        },
        {
            "labels": {
                "alertname": "HighMemoryUsage",
                "severity": "warning",
                "instance": "payment-service",
                "job": "node-exporter",
                "namespace": "default",
            },
            "annotations": {
                "summary": "内存使用率过高",
                "description": "payment-service 内存使用率超过 70% 阈值",
            },
            "state": "pending",
            "activeAt": _rfc3339(12),
        },
        {
            "labels": {
                "alertname": "HighDiskUsage",
                "severity": "warning",
                "instance": "order-service",
                "job": "node-exporter",
                "namespace": "default",
            },
            "annotations": {
                "summary": "磁盘使用率过高",
                "description": "order-service 数据盘使用率超过 85%",
            },
            "state": "pending",
            "activeAt": _rfc3339(3),
        },
    ]
    alerts.extend(_EXTRA_ALERTS)
    return {"status": "success", "data": {"alerts": alerts}}


class MockPrometheusHandler(BaseHTTPRequestHandler):
    server_version = "MockPrometheus/1.0"

    def _send_json(self, payload: dict, status: int = 200) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _send_text(self, text: str, status: int = 200) -> None:
        body = text.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, fmt: str, *args) -> None:
        sys.stdout.write(
            "[mock-prometheus] %s - %s\n" % (self.log_date_time_string(), fmt % args)
        )
        sys.stdout.flush()

    def do_POST(self) -> None:
        """动态注入/重置告警，便于演示"新告警自动响应"。"""
        self.log_message("POST %s", self.path)
        length = int(self.headers.get("Content-Length") or 0)
        raw = self.rfile.read(length) if length else b"{}"
        try:
            body = json.loads(raw.decode("utf-8") or "{}")
        except json.JSONDecodeError:
            body = {}

        path = self.path.rstrip("/")
        if path == "/api/v1/alerts/trigger":
            alert = {
                "labels": {
                    "alertname": body.get("alertname", "ServiceUnavailable"),
                    "severity": body.get("severity", "warning"),
                    "instance": body.get("instance", "checkout-service"),
                    "job": "node-exporter",
                    "namespace": "default",
                },
                "annotations": {
                    "summary": body.get("summary", "服务不可用"),
                    "description": body.get(
                        "description",
                        "checkout-service 连续 3 次健康检查失败，服务不可用",
                    ),
                },
                "state": "firing",
                "activeAt": _rfc3339(0),
            }
            _EXTRA_ALERTS.append(alert)
            self._send_json({"status": "success", "data": {"added": alert}})
        elif path == "/api/v1/alerts/reset":
            _EXTRA_ALERTS.clear()
            self._send_json({"status": "success", "data": {"reset": True}})
        else:
            self._send_json(
                {"status": "error", "errorType": "bad_data", "error": f"no route: {self.path}"},
                status=404,
            )

    def do_GET(self) -> None:
        self.log_message("GET %s", self.path)
        if self.path.rstrip("/") == "/api/v1/alerts":
            self._send_json(build_alerts_payload())
        elif self.path.rstrip("/") == "/api/v1/query":
            # 兼容可能出现的查询调用（当前工具只使用 /api/v1/alerts）
            self._send_json(
                {"status": "success", "data": {"resultType": "vector", "result": []}}
            )
        elif self.path.rstrip("/") in ("/", "/health", "/-/healthy"):
            self._send_text("mock-prometheus ok")
        else:
            self._send_json(
                {"status": "error", "errorType": "bad_data", "error": f"no route: {self.path}"},
                status=404,
            )


def main() -> None:
    host = os.environ.get("MOCK_PROM_HOST", "0.0.0.0")
    port = int(os.environ.get("MOCK_PROM_PORT", "9090"))
    server = ThreadingHTTPServer((host, port), MockPrometheusHandler)
    print(f"mock-prometheus listening on {host}:{port}", flush=True)
    print(
        f"alerts endpoint: http://{host}:{port}/api/v1/alerts "
        f"({len(build_alerts_payload()['data']['alerts'])} alerts)",
        flush=True,
    )
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("mock-prometheus stopped", flush=True)


if __name__ == "__main__":
    main()
