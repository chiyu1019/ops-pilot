"""通知模块：对外只暴露 notification_service 与数据结构

用法（Agent 侧）：
    from notification import notification_service
    await notification_service.notify_diagnosis(state=..., alert=..., session_id=..., source="alert_auto")
"""

from notification.schemas import (
    SOURCE_ALERT_AUTO,
    SOURCE_USER_CHAT,
    DiagnosisNotification,
    NotificationResult,
)
from notification.service import NotificationService, notification_service

__all__ = [
    "notification_service",
    "NotificationService",
    "DiagnosisNotification",
    "NotificationResult",
    "SOURCE_ALERT_AUTO",
    "SOURCE_USER_CHAT",
]
