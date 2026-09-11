"""全链路观测：Langfuse Callback 集成

配置了 LANGFUSE_PUBLIC_KEY / LANGFUSE_SECRET_KEY / LANGFUSE_HOST 时启用，
未配置或 SDK 不可用时静默降级（返回空列表），不影响主流程。
"""

from __future__ import annotations

import os
from typing import List

from loguru import logger

_cached: List[object] | None = None


def get_observability_callbacks() -> List[object]:
    """返回观测相关的 CallbackHandler 列表（进程内单例）"""
    global _cached
    if _cached is not None:
        return _cached

    callbacks: List[object] = []
    if os.environ.get("LANGFUSE_PUBLIC_KEY") and os.environ.get("LANGFUSE_SECRET_KEY"):
        try:
            from langfuse.langchain import CallbackHandler  # type: ignore

            callbacks.append(CallbackHandler())
            logger.info("Langfuse 观测已启用")
        except Exception as e:  # noqa: BLE001
            logger.warning(f"Langfuse 未启用（SDK 缺失或版本不匹配）: {e}")
    _cached = callbacks
    return callbacks
