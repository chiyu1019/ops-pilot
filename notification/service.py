"""通知服务：统一分发入口（当前支持飞书，后续可扩展企业微信 / 邮件）

设计要点：
1. 只有 source == alert_auto 才推送（用户对话入口生成报告不推）
2. 幂等保护：同一 (来源, 会话, 告警, 状态) 在 TTL 窗口内只发送一次
3. 任何异常都不外抛，绝不影响 Agent 主流程
"""

from __future__ import annotations

import asyncio
import time
from typing import Any, Callable, Dict, Optional

from loguru import logger

from app.config import config
from notification.feishu import FeishuClient, feishu_client
from notification.schemas import (
    SOURCE_ALERT_AUTO,
    DiagnosisNotification,
    NotificationResult,
)

# 渠道注册表：名字 -> 异步发送函数（未来加 wecom/email 只需注册）
NotifierFn = Callable[[DiagnosisNotification], Any]


class NotificationService:
    """通知分发服务（带来源过滤与幂等保护）"""

    def __init__(self, client: Optional[FeishuClient] = None) -> None:
        self._channels: Dict[str, NotifierFn] = {}
        self._client = client or feishu_client
        self.register("feishu", self._client.send_card)
        # 幂等缓存：key -> 上次发送时间戳
        self._sent: Dict[str, float] = {}
        self._lock = asyncio.Lock()

    # ---------- 渠道管理 ----------
    def register(self, name: str, sender: NotifierFn) -> None:
        """注册通知渠道（sender 需为 async 可调用对象）"""
        self._channels[name] = sender

    @property
    def channels(self) -> list[str]:
        return list(self._channels.keys())

    # ---------- 幂等 ----------
    def _is_duplicate(self, key: str) -> bool:
        last = self._sent.get(key)
        ttl = config.notification_idempotency_ttl
        return last is not None and (time.time() - last) < ttl

    def _mark_sent(self, key: str) -> None:
        self._sent[key] = time.time()

    def reset_idempotency_cache(self) -> None:
        """清空幂等缓存（供测试与手工重放使用）"""
        self._sent.clear()

    # ---------- 主入口 ----------
    async def notify_diagnosis(
        self,
        state: Dict[str, Any],
        alert: Optional[dict] = None,
        task_input: str = "",
        session_id: str = "",
        source: str = SOURCE_ALERT_AUTO,
        force: bool = False,
        channel: str = "feishu",
    ) -> NotificationResult:
        """诊断完成后推送通知。

        Args:
            state: LangGraph 最终状态（含 diagnosis / verification / evidence）
            alert: 原始告警（labels / annotations）
            task_input: 任务描述（无 alert 时用于兜底提取字段）
            session_id: 会话 ID
            source: 来源标记，只有 alert_auto 会真正推送
            force: 跳过幂等检查（手工重放 / 测试用）
            channel: 目标渠道
        """
        try:
            # 1) 总开关
            if not config.notification_enabled:
                logger.info("notification disabled, skip feishu notification")
                return NotificationResult(sent=False, skipped=True, reason="notification_disabled")

            # 2) 来源过滤：仅自动告警入口推送
            if source != SOURCE_ALERT_AUTO:
                logger.info(
                    f"notification skipped: source={source} "
                    f"(only {SOURCE_ALERT_AUTO} triggers feishu notification)"
                )
                return NotificationResult(sent=False, skipped=True, reason="source_not_allowed")

            # 3) 渲染消息
            notification = DiagnosisNotification.from_agent_state(
                state=state,
                alert=alert,
                task_input=task_input,
                source=source,
                session_id=session_id,
            )

            # 4) 幂等保护（并发下用锁保证 check-then-set 原子性）
            key = notification.idempotency_key()
            async with self._lock:
                if not force and self._is_duplicate(key):
                    logger.info(
                        f"notification skipped: duplicate within "
                        f"{config.notification_idempotency_ttl}s window (key={key})"
                    )
                    return NotificationResult(sent=False, skipped=True, reason="duplicate")
                self._mark_sent(key)

            # 5) 分发
            sender = self._channels.get(channel)
            if sender is None:
                logger.warning(f"notification channel not registered: {channel}")
                return NotificationResult(sent=False, skipped=True, reason="channel_not_registered")

            result: NotificationResult = await sender(notification)
            return result

        except Exception as e:  # noqa: BLE001 —— 通知失败绝不影响 Agent
            logger.exception(f"feishu notification failed: {type(e).__name__}: {e}")
            return NotificationResult(sent=False, error=f"{type(e).__name__}: {e}")


# 全局单例
notification_service = NotificationService()
