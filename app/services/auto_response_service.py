"""自动响应：实时接收监控告警并自动触发 AIOps 诊断

两条接入路径：
- 主动轮询：后台任务定时查 Prometheus /api/v1/alerts，发现新 firing 告警自动诊断
- Webhook：接收 Prometheus Alertmanager / 云监控推送（POST /api/webhook/alerts）

核心机制：
- 指纹去重 + 冷却时间（同一告警在冷却期内不重复诊断）
- 事件存储 + SSE 推送，前端可实时看到"收到告警 -> 自动诊断 -> 报告完成"
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import time
from collections import deque
from datetime import datetime
from typing import Any, Deque, Dict, List, Optional

from loguru import logger

from app.config import config
from app.tools.query_metrics_alerts import query_prometheus_alerts_api

# ---------- SSE 订阅者管理 ----------
_subscribers: List[asyncio.Queue] = []


def subscribe() -> asyncio.Queue:
    q: asyncio.Queue = asyncio.Queue(maxsize=200)
    _subscribers.append(q)
    return q


def unsubscribe(q: asyncio.Queue) -> None:
    if q in _subscribers:
        _subscribers.remove(q)


def publish(event: dict) -> None:
    payload = json.dumps(event, ensure_ascii=False)
    for q in list(_subscribers):
        try:
            q.put_nowait(payload)
        except asyncio.QueueFull:
            pass


# ---------- 告警事件存储（进程内，重启清空；如需持久化可扩展 Redis） ----------
_events: Deque[dict] = deque(maxlen=200)
_handled: Dict[str, float] = {}


def get_events() -> List[dict]:
    return list(_events)


def _now() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def alert_fingerprint(alert: dict) -> str:
    """告警指纹 = labels 的规范化 JSON（与 Prometheus 语义一致）。"""
    labels = alert.get("labels") or {}
    return hashlib.sha1(
        json.dumps(labels, sort_keys=True, ensure_ascii=False).encode("utf-8")
    ).hexdigest()


def _in_cooldown(fingerprint: str) -> bool:
    last = _handled.get(fingerprint)
    return last is not None and (time.time() - last) < config.alert_cooldown_seconds


def _is_firing(alert: dict) -> bool:
    state = str(alert.get("state") or "").lower()
    return state in ("firing", "active", "")


def _record_event(event: dict) -> None:
    _events.appendleft(event)
    publish(event)


async def consume_alert(alert: dict) -> bool:
    """去重 + 触发自动诊断。返回是否触发。"""
    try:
        fp = alert_fingerprint(alert)
        if _in_cooldown(fp):
            logger.info(f"告警在冷却期内，跳过自动响应: {fp[:12]}")
            return False
        _handled[fp] = time.time()

        labels = alert.get("labels") or {}
        annotations = alert.get("annotations") or {}
        alertname = labels.get("alertname", "Unknown")
        _record_event(
            {
                "type": "alert_received",
                "alertname": alertname,
                "instance": labels.get("instance", ""),
                "severity": labels.get("severity", ""),
                "description": annotations.get("description", ""),
                "time": _now(),
            }
        )

        session_id = f"auto-{fp[:12]}"
        task_input = (
            f"收到新告警：{alertname}（级别 {labels.get('severity', '')}）"
            f"影响服务 {labels.get('instance', '')}，告警描述：{annotations.get('description', '')}。"
            f"请基于该告警自动进行根因分析并生成诊断报告。"
        )
        task = asyncio.create_task(_run_diagnosis(alert, task_input, session_id))
        _background_tasks.add(task)
        task.add_done_callback(_background_tasks.discard)
        return True

    except Exception as e:
        logger.error(f"消费告警失败: {e}", exc_info=True)
        return False


_background_tasks: set = set()


async def _run_diagnosis(alert: dict, task_input: str, session_id: str) -> None:
    """后台执行 AIOps 诊断（不阻塞告警接收）。"""
    from app.services.aiops_service import aiops_service

    _record_event(
        {"type": "diagnosis_started", "alertname": (alert.get("labels") or {}).get("alertname", ""), "session_id": session_id, "time": _now()}
    )
    final_report = ""
    try:
        async for event in aiops_service.execute(
            task_input, session_id=session_id, alert=alert
        ):
            if event.get("type") == "report":
                final_report = event.get("report", "") or final_report
            if event.get("type") == "complete":
                final_report = event.get("response", "") or final_report

        _record_event(
            {
                "type": "diagnosis_completed",
                "alertname": (alert.get("labels") or {}).get("alertname", ""),
                "session_id": session_id,
                "report": final_report[:300],
                "time": _now(),
            }
        )
        logger.info(f"[{session_id}] 自动诊断完成")
    except Exception as e:
        logger.error(f"[{session_id}] 自动诊断失败: {e}", exc_info=True)
        _record_event(
            {
                "type": "diagnosis_failed",
                "alertname": (alert.get("labels") or {}).get("alertname", ""),
                "session_id": session_id,
                "error": str(e),
                "time": _now(),
            }
        )


async def poll_prometheus_loop() -> None:
    """后台轮询 Prometheus 告警，新告警自动触发诊断。"""
    logger.info(
        f"自动响应轮询启动：每 {config.alert_poll_interval}s 查询一次 {config.prometheus_base_url}"
    )
    while True:
        try:
            body, err = query_prometheus_alerts_api()
            if err:
                logger.warning(f"轮询告警失败: {err}")
            else:
                alerts = (body.get("data") or {}).get("alerts") or []
                for alert in alerts:
                    if isinstance(alert, dict) and _is_firing(alert):
                        await consume_alert(alert)
        except Exception as e:
            logger.error(f"轮询告警异常: {e}", exc_info=True)
        await asyncio.sleep(config.alert_poll_interval)
