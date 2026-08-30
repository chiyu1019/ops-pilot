"""自动响应 API：Webhook 接收、告警事件查询、SSE 实时推送"""

import json
from typing import Any, Dict, List

from fastapi import APIRouter
from fastapi.responses import JSONResponse
from loguru import logger
from sse_starlette.sse import EventSourceResponse

from app.services import auto_response_service as ars

router = APIRouter()


@router.post("/webhook/alerts")
async def webhook_alerts(payload: Dict[str, Any]):
    """接收 Prometheus Alertmanager / 云监控推送的告警（自动触发诊断）。

    支持两种格式：
    1. Alertmanager：{"status": "firing", "alerts": [{labels, annotations, ...}]}
    2. 单条告警：{"labels": {...}, "annotations": {...}}
    """
    raw_alerts: List[Any] = payload.get("alerts")
    group_status = str(payload.get("status", "")).lower()

    if not isinstance(raw_alerts, list):
        raw_alerts = [payload] if payload.get("labels") else []

    received = 0
    triggered = 0
    for alert in raw_alerts:
        if not isinstance(alert, dict):
            continue
        status = str(alert.get("status", "") or group_status).lower()
        if status in ("resolved", "inactive"):
            continue
        received += 1
        if await ars.consume_alert(alert):
            triggered += 1

    logger.info(f"Webhook 收到告警: {received} 条，触发诊断: {triggered} 条")
    return JSONResponse(
        {
            "code": 200,
            "message": "success",
            "data": {"received": received, "triggered": triggered},
        }
    )


@router.get("/alerts/events")
async def list_alert_events():
    """查询最近的告警事件列表（页面初始加载用）。"""
    return JSONResponse({"code": 200, "message": "success", "data": ars.get_events()})


@router.get("/alerts/stream")
async def stream_alert_events():
    """SSE 实时推送告警事件。"""

    async def event_generator():
        queue = ars.subscribe()
        try:
            # 先补发历史事件（时间正序）
            for event in reversed(ars.get_events()):
                yield {"event": "message", "data": json.dumps(event, ensure_ascii=False)}
            while True:
                data = await queue.get()
                yield {"event": "message", "data": data}
        finally:
            ars.unsubscribe(queue)

    return EventSourceResponse(event_generator())
