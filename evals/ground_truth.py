"""诊断正确性评测的真值定义（Ground Truth）

每个场景给出"标准答案"三要素，供 LLM-as-Judge 逐项比对：
- root_cause_contains：根因结论应当覆盖的要点
- key_evidence：本次工具调用中真实存在的关键证据（诊断应引用其中至少若干条）
- key_actions：处置建议中应当出现的关键动作
"""

from __future__ import annotations

from typing import Any, Dict

GROUND_TRUTH: Dict[str, Dict[str, Any]] = {
    "cpu_high": {
        "root_cause_contains": ["CPU 使用率过高", "资源耗尽或进程占用"],
        "key_evidence": ["cpu 指标 avg 约 88.5%", "日志出现 GC/超时错误"],
        "key_actions": ["定位高占用进程", "重启或扩容实例"],
        "note": "告警与指标一致，应给出确定性的 CPU 根因",
    },
    "memory_high": {
        "root_cause_contains": ["内存使用率过高", "内存不足或泄漏"],
        "key_evidence": ["内存指标 avg 约 88.5%", "日志出现 OutOfMemoryError"],
        "key_actions": ["堆转储分析", "调整 JVM/缓存参数或扩容"],
        "note": "告警与指标一致",
    },
    "disk_high": {
        "root_cause_contains": ["磁盘空间不足"],
        "key_evidence": ["日志出现 No space left on device", "磁盘使用率超阈值"],
        "key_actions": ["清理日志/临时文件", "清理 Docker 或扩容"],
        "note": "告警与日志一致",
    },
    "service_unavailable": {
        "root_cause_contains": ["服务不可用", "依赖或连接失败"],
        "key_evidence": ["日志出现 connection refused / 依赖失败", "健康检查失败"],
        "key_actions": ["检查依赖服务与端口", "回滚或重启"],
        "note": "告警与日志一致",
    },
    "slow_response": {
        "root_cause_contains": ["响应时间过长", "慢查询或下游超时"],
        "key_evidence": ["日志出现慢查询 4.2s", "上游 API 超时"],
        "key_actions": ["优化慢查询", "调整超时/缓存策略"],
        "note": "告警与日志一致",
    },
    "no_evidence": {
        "root_cause_contains": [],
        "key_evidence": [],
        "key_actions": ["建议人工复核"],
        "note": "无告警无日志，正确行为是不给出确定性根因（降级为假设/安全报告）",
        "expect_no_firm_root_cause": True,
    },
    # ---------- 对抗场景 ----------
    "conflict": {
        "root_cause_contains": ["证据冲突", "指标正常与告警不一致", "无法确认"],
        "key_evidence": ["告警 state=firing", "指标 avg 仅 12.4%（正常）"],
        "key_actions": ["补充证据", "人工复核"],
        "note": "告警与指标矛盾，**不应**断言 CPU 使用率过高；正确行为是指出冲突或降级",
        "expect_no_firm_root_cause": True,
    },
    "tool_fail": {
        "root_cause_contains": ["工具失败", "证据不足"],
        "key_evidence": ["工具返回超时/不可用"],
        "key_actions": ["重试或人工介入"],
        "note": "关键证据不可得，不应编造根因",
        "expect_no_firm_root_cause": True,
    },
    "misleading": {
        "root_cause_contains": ["磁盘空间不足"],
        "key_evidence": ["日志出现 No space left on device"],
        "key_actions": ["清理磁盘或扩容"],
        "note": "知识库返回无关文档，但工具证据指向磁盘 → 结论应跟随证据",
    },
    "multi_alert": {
        "root_cause_contains": ["CPU 与内存同时异常"],
        "key_evidence": ["两条告警同时 firing", "GC 日志"],
        "key_actions": ["分别处置 CPU 与内存"],
        "note": "多条告警需同时覆盖",
    },
    "sparse": {
        "root_cause_contains": ["内存使用率过高"],
        "key_evidence": ["内存指标异常但无日志"],
        "key_actions": ["检查缓存与对象增长"],
        "note": "只有指标证据也应给出结论（指标足够）",
    },
}


def get_ground_truth(scenario: str) -> Dict[str, Any]:
    return GROUND_TRUTH.get(scenario, {"root_cause_contains": [], "key_evidence": [], "key_actions": []})
