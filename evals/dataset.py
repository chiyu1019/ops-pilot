"""34 个可控测试用例：覆盖 5 类告警场景 + 无告警场景

每个用例定义：
- alert：告警内容（进入任务描述）
- fixture：该场景下各工具的确定性返回
- expect：期望的诊断状态（verified / 非 verified）与根因关键词
"""

from __future__ import annotations

import json
from typing import Any, Dict, List

ARCHETYPES = {
    "cpu_high": {
        "alertname": "HighCPUUsage",
        "severity": "critical",
        "kb": "HighCPUUsage 处置：1) 查系统日志确认 2) 定位 CPU 占用进程 3) 查应用错误日志 4) 必要时重启实例。根因常见：死循环、流量突增、定时任务重叠、慢查询。",
        "log_query": "level:ERROR OR cpu_usage:>80",
        "log_lines": [
            {"level": "ERROR", "message": "GC overhead limit exceeded, heap usage 92%"},
            {"level": "ERROR", "message": "task worker timeout after 30s"},
        ],
        "metrics_high": True,
    },
    "memory_high": {
        "alertname": "HighMemoryUsage",
        "severity": "warning",
        "kb": "HighMemoryUsage 处置：1) 查监控确认内存趋势 2) 查应用日志定位对象增长 3) 生成堆转储分析 4) 调整缓存与 JVM 参数。",
        "log_query": "level:ERROR OR memory_usage:>70",
        "log_lines": [
            {"level": "ERROR", "message": "OutOfMemoryError: Java heap space"},
            {"level": "WARN", "message": "cache eviction triggered, size=120000"},
        ],
        "metrics_high": True,
    },
    "disk_high": {
        "alertname": "HighDiskUsage",
        "severity": "warning",
        "kb": "HighDiskUsage 处置：1) 查磁盘使用率与目录占用 2) 清理日志与临时文件 3) 清理 Docker 镜像 4) 扩容或归档。",
        "log_query": "level:ERROR OR disk_usage:>85",
        "log_lines": [
            {"level": "ERROR", "message": "write failed: No space left on device"},
            {"level": "WARN", "message": "/data/logs/app.log grow to 12GB"},
        ],
        "metrics_high": True,
    },
    "service_unavailable": {
        "alertname": "ServiceUnavailable",
        "severity": "critical",
        "kb": "ServiceUnavailable 处置：1) 确认进程与端口 2) 检查依赖服务与数据库连接 3) 回滚最近发布 4) 扩容或重启。",
        "log_query": "level:ERROR OR up==0",
        "log_lines": [
            {"level": "ERROR", "message": "connect to mysql failed: connection refused"},
            {"level": "ERROR", "message": "health check endpoint returned 503"},
        ],
        "metrics_high": False,
    },
    "slow_response": {
        "alertname": "SlowResponse",
        "severity": "warning",
        "kb": "SlowResponse 处置：1) 查 P99 与响应分布 2) 定位慢查询 3) 检查外部依赖超时 4) 检查缓存命中率。",
        "log_query": "level:WARN OR latency:>2000",
        "log_lines": [
            {"level": "WARN", "message": "slow query detected: 4.2s SELECT * FROM orders"},
            {"level": "WARN", "message": "upstream api timeout after 3000ms"},
        ],
        "metrics_high": True,
    },
}

INSTANCES = ["data-sync-service", "payment-service", "order-service", "user-service", "gateway-service"]
SERIES = [1, 2, 3, 4]


def _alerts_payload(alertname: str, severity: str, instance: str, state: str = "firing") -> Dict[str, Any]:
    return {
        "alerts": [
            {
                "labels": {"alertname": alertname, "severity": severity, "instance": instance},
                "annotations": {"summary": f"{alertname} on {instance}", "description": f"{instance} 触发 {alertname} 告警"},
                "state": state,
                "activeAt": "2026-09-11T03:00:00Z",
                "duration": "25m",
            }
        ]
    }


def _logs_payload(lines: List[Dict[str, str]], instance: str) -> Dict[str, Any]:
    logs = [
        {"timestamp": f"2026-09-11T03:{10 + i:02d}:00Z", "level": l["level"], "message": f"[{instance}] {l['message']}"}
        for i, l in enumerate(lines)
    ]
    return {"total": len(logs), "logs": logs, "took_ms": 42}


def _metrics_payload(instance: str, high: bool, kind: str) -> Dict[str, Any]:
    base = 88.5 if high else 31.2
    return {
        "service_name": instance,
        "metric_name": kind,
        "statistics": {"avg": base, "max": base + 6.3, "min": base - 12.1, "p95": base + 4.4},
        "alert_info": {"triggered": high, "threshold": 80.0 if kind == "cpu_usage_percent" else 70.0},
    }


def build_cases() -> List[Dict[str, Any]]:
    """生成 34 个用例：30 个正常告警场景 + 4 个证据不足场景"""
    cases: List[Dict[str, Any]] = []
    plan = [
        ("cpu_high", 7),
        ("memory_high", 6),
        ("disk_high", 6),
        ("service_unavailable", 6),
        ("slow_response", 5),
    ]
    seq = 0
    for archetype, count in plan:
        spec = ARCHETYPES[archetype]
        for i in range(count):
            seq += 1
            instance = INSTANCES[i % len(INSTANCES)]
            series = SERIES[i % len(SERIES)]
            kind = "memory_usage_percent" if archetype == "memory_high" else "cpu_usage_percent"
            high = spec["metrics_high"]
            cases.append(
                {
                    "id": f"{archetype}-{i + 1:02d}",
                    "scenario": archetype,
                    "series": series,
                    "alert": _alerts_payload(spec["alertname"], spec["severity"], instance),
                    "instance": instance,
                    "fixture": {
                        "query_prometheus_alerts": _alerts_payload(spec["alertname"], spec["severity"], instance),
                        "search_log": _logs_payload(spec["log_lines"], instance),
                        "get_topic_info_by_name": {"topic_id": "system-metrics", "name": "system-metrics", "region": "ap-guangzhou"},
                        "get_current_timestamp": {"timestamp": "2026-09-11T03:30:00Z"},
                        "query_cpu_metrics": _metrics_payload(instance, high, "cpu_usage_percent"),
                        "query_memory_metrics": _metrics_payload(instance, high, "memory_usage_percent"),
                        "retrieve_knowledge": spec["kb"],
                    },
                    "expect": {
                        "verified": True,
                        "keywords": [spec["alertname"].lower(), instance.lower()],
                    },
                }
            )

    # 证据不足场景：无告警、无日志、无指标 -> 应降级为 hypothesis / safe_report
    for i in range(4):
        seq += 1
        instance = INSTANCES[i % len(INSTANCES)]
        cases.append(
            {
                "id": f"no_evidence-{i + 1:02d}",
                "scenario": "no_evidence",
                "series": 5,
                "alert": {"alerts": [], "note": "无活跃告警"},
                "instance": instance,
                "fixture": {
                    "query_prometheus_alerts": {"alerts": []},
                    "search_log": {"total": 0, "logs": []},
                    "query_cpu_metrics": {"service_name": instance, "statistics": {}},
                    "query_memory_metrics": {"service_name": instance, "statistics": {}},
                    "retrieve_knowledge": "（无可参考经验）",
                    "get_current_timestamp": {"timestamp": "2026-09-11T03:30:00Z"},
                },
                "expect": {"verified": False, "keywords": []},
            }
        )
    return cases


def task_text(case: Dict[str, Any]) -> str:
    """把用例转成诊断任务描述"""
    alerts = (case["alert"] or {}).get("alerts") or []
    if alerts:
        a = alerts[0]
        labels = a.get("labels", {})
        desc = (a.get("annotations") or {}).get("description", "")
        return (
            f"诊断告警：{labels.get('alertname')}（severity={labels.get('severity')}, "
            f"instance={labels.get('instance')}），描述：{desc}。"
            "请查询监控与日志证据，定位根因并给出处置建议。"
        )
    return "请检查当前系统是否存在需要处理的告警；若无告警或证据不足，请明确说明。"


if __name__ == "__main__":
    data = build_cases()
    print(f"用例总数: {len(data)}")
    from collections import Counter

    print("场景分布:", dict(Counter(c["scenario"] for c in data)))
    print(json.dumps(data[0], ensure_ascii=False, indent=2)[:600])
