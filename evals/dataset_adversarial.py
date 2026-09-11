"""对抗场景数据集：故意制造冲突/失败/噪音证据，检验 Agent 可靠性边界

与主数据集（34 个常规场景）不同，这批场景**期望结果包含降级**，
因此通过率不会饱和在 100%：

- conflict   ：告警 firing 但指标正常（证据冲突）→ 期望识别矛盾或降级
- tool_fail  ：日志/指标工具返回错误 → 期望降级且不编造
- misleading ：知识库返回无关文档，真实证据指向另一根因 → 期望跟随真实证据
- multi_alert：多条告警并存 → 期望都覆盖
- sparse     ：只有指标证据、无日志 → 期望仍能给出根因
"""

from __future__ import annotations

from typing import Any, Dict, List

from evals.dataset import _alerts_payload, _logs_payload, _metrics_payload


def _alert(name: str, severity: str, instance: str, desc: str = "") -> Dict[str, Any]:
    return _alerts_payload(name, severity, instance)


def build_adversarial_cases() -> List[Dict[str, Any]]:
    cases: List[Dict[str, Any]] = []

    # A. 证据冲突：告警说 CPU 高，但指标是正常值
    for i, instance in enumerate(["data-sync-service", "payment-service", "gateway-service"]):
        cases.append({
            "id": f"conflict-{i + 1:02d}",
            "scenario": "conflict",
            "alert": _alert("HighCPUUsage", "critical", instance),
            "instance": instance,
            "fixture": {
                "query_prometheus_alerts": _alert("HighCPUUsage", "critical", instance),
                "query_cpu_metrics": {
                    "service_name": instance,
                    "statistics": {"avg": 12.4, "max": 18.7, "min": 6.2, "p95": 17.1},
                    "alert_info": {"triggered": False, "threshold": 80.0},
                },
                "query_memory_metrics": _metrics_payload(instance, False, "memory_usage_percent"),
                "search_log": {"total": 0, "logs": []},
                "retrieve_knowledge": "HighCPUUsage 处置：定位 CPU 占用进程、检查死循环与流量突增。",
                "get_current_timestamp": {"timestamp": "2026-09-11T03:30:00Z"},
            },
            "expect": {"verified": False,
                       "keywords": ["矛盾", "不一致", "指标正常", "无法确认", "需进一步"]},
        })

    # B. 工具失败：日志/指标后端不可用
    for i, instance in enumerate(["order-service", "user-service"]):
        cases.append({
            "id": f"tool_fail-{i + 1:02d}",
            "scenario": "tool_fail",
            "alert": _alert("ServiceUnavailable", "critical", instance),
            "instance": instance,
            "fixture": {
                "query_prometheus_alerts": _alert("ServiceUnavailable", "critical", instance),
                "search_log": {"error": "upstream timeout: CLS 查询超时", "total": 0, "logs": []},
                "query_cpu_metrics": {"error": "metrics backend unavailable"},
                "query_memory_metrics": {"error": "metrics backend unavailable"},
                "retrieve_knowledge": "ServiceUnavailable 处置：确认进程端口、检查依赖与数据库连接。",
                "get_current_timestamp": {"timestamp": "2026-09-11T03:30:00Z"},
            },
            "expect": {"verified": False,
                       "keywords": ["无法", "失败", "证据不足", "降级", "超时"]},
        })

    # C. 误导知识库：KB 返回无关文档，真实证据指向磁盘
    for i, instance in enumerate(["log-service", "backup-service"]):
        cases.append({
            "id": f"misleading-{i + 1:02d}",
            "scenario": "misleading",
            "alert": _alert("HighDiskUsage", "warning", instance),
            "instance": instance,
            "fixture": {
                "query_prometheus_alerts": _alert("HighDiskUsage", "warning", instance),
                "search_log": _logs_payload(
                    [{"level": "ERROR", "message": "write failed: No space left on device"}], instance
                ),
                "query_cpu_metrics": _metrics_payload(instance, False, "cpu_usage_percent"),
                "query_memory_metrics": _metrics_payload(instance, False, "memory_usage_percent"),
                "retrieve_knowledge": "MySQL 慢查询治理：开启慢查询日志、分析执行计划、补充索引、避免深分页。",
                "get_current_timestamp": {"timestamp": "2026-09-11T03:30:00Z"},
            },
            "expect": {"verified": True, "keywords": ["磁盘", "disk", "空间", "存储"]},
        })

    # D. 多告警并存：CPU + 内存同时 firing
    for i, instance in enumerate(["data-sync-service", "order-service"]):
        alerts = {"alerts": [
            {"labels": {"alertname": "HighCPUUsage", "severity": "critical", "instance": instance},
             "annotations": {"description": f"{instance} CPU 持续超过 80%"},
             "state": "firing", "activeAt": "2026-09-11T03:00:00Z", "duration": "20m"},
            {"labels": {"alertname": "HighMemoryUsage", "severity": "warning", "instance": instance},
             "annotations": {"description": f"{instance} 内存超过 70%"},
             "state": "firing", "activeAt": "2026-09-11T03:10:00Z", "duration": "10m"},
        ]}
        cases.append({
            "id": f"multi_alert-{i + 1:02d}",
            "scenario": "multi_alert",
            "alert": alerts,
            "instance": instance,
            "fixture": {
                "query_prometheus_alerts": alerts,
                "search_log": _logs_payload(
                    [{"level": "ERROR", "message": "GC pause 3.2s, heap 91%"}], instance
                ),
                "query_cpu_metrics": _metrics_payload(instance, True, "cpu_usage_percent"),
                "query_memory_metrics": _metrics_payload(instance, True, "memory_usage_percent"),
                "retrieve_knowledge": "CPU/内存告警处置：定位高消耗进程、检查 GC 与缓存配置。",
                "get_current_timestamp": {"timestamp": "2026-09-11T03:30:00Z"},
            },
            "expect": {"verified": True, "keywords": ["HighCPUUsage", "HighMemoryUsage", "内存"]},
        })

    # E. 稀疏证据：指标异常但日志为空
    for i, instance in enumerate(["cache-service"]):
        cases.append({
            "id": f"sparse-{i + 1:02d}",
            "scenario": "sparse",
            "alert": _alert("HighMemoryUsage", "warning", instance),
            "instance": instance,
            "fixture": {
                "query_prometheus_alerts": _alert("HighMemoryUsage", "warning", instance),
                "search_log": {"total": 0, "logs": []},
                "query_cpu_metrics": _metrics_payload(instance, True, "cpu_usage_percent"),
                "query_memory_metrics": _metrics_payload(instance, True, "memory_usage_percent"),
                "retrieve_knowledge": "内存告警处置：检查缓存配置与对象增长、必要时扩容。",
                "get_current_timestamp": {"timestamp": "2026-09-11T03:30:00Z"},
            },
            "expect": {"verified": True, "keywords": ["内存", "memory", "缓存"]},
        })

    return cases
