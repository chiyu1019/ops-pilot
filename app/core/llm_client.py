"""LLM 客户端封装：ChatQwen + 瞬时错误重试

背景：百炼专属实例（ws-xxx.maas.aliyuncs.com）会偶发返回
403 AccessDenied / 429 Throttling / 5xx，同一个请求稍后重试即可成功。
本模块在模型层做有限次重试，避免上层 Agent 流程因瞬时错误整体失败。

配置（.env）：
- LLM_MAX_RETRIES   最大尝试次数（含首次），默认 3；设为 1 表示关闭重试
- LLM_RETRY_DELAY   退避基数（秒），第 n 次失败后等待 delay * n
"""

from __future__ import annotations

import asyncio
from typing import Any, AsyncIterator, Iterator, List, Optional

from langchain_core.callbacks import (
    AsyncCallbackManagerForLLMRun,
    CallbackManagerForLLMRun,
)
from langchain_core.messages import BaseMessage
from langchain_core.outputs import ChatResult
from langchain_qwq import ChatQwen
from loguru import logger

from app.config import config

# 触发重试的错误关键字（大小写不敏感）
RETRYABLE_HINTS = (
    "accessdenied",
    "access denied",
    "unpurchased",
    "throttling",
    "rate limit",
    "429",
    "500",
    "502",
    "503",
    "504",
    "timeout",
    "timed out",
    "connection reset",
    # LLM SDK 偶发解析异常（例如流式响应缺少 description 字段），重试即可恢复
    "keyerror",
)


def _is_retryable(exc: BaseException) -> bool:
    """判断异常是否值得重试（瞬时错误而非参数/鉴权错误）"""
    text = f"{type(exc).__name__}: {exc}".lower()
    return any(hint in text for hint in RETRYABLE_HINTS)


class RetryingChatQwen(ChatQwen):
    """带有限次重试的 ChatQwen（覆盖同步/异步/流式三条路径）"""

    max_attempts: int = 3
    retry_delay: float = 1.0

    # ---------- 同步 ----------
    def _generate(
        self,
        messages: List[BaseMessage],
        stop: Optional[List[str]] = None,
        run_manager: Optional[CallbackManagerForLLMRun] = None,
        **kwargs: Any,
    ) -> ChatResult:
        last_exc: BaseException | None = None
        for attempt in range(1, self.max_attempts + 1):
            try:
                return super()._generate(messages, stop=stop, run_manager=run_manager, **kwargs)
            except Exception as e:  # noqa: BLE001
                last_exc = e
                if attempt >= self.max_attempts or not _is_retryable(e):
                    raise
                logger.warning(f"LLM 调用失败（第 {attempt} 次），{self.retry_delay * attempt:.1f}s 后重试: {str(e)[:120]}")
                import time

                time.sleep(self.retry_delay * attempt)
        raise last_exc  # pragma: no cover

    # ---------- 异步 ----------
    async def _agenerate(
        self,
        messages: List[BaseMessage],
        stop: Optional[List[str]] = None,
        run_manager: Optional[AsyncCallbackManagerForLLMRun] = None,
        **kwargs: Any,
    ) -> ChatResult:
        last_exc: BaseException | None = None
        for attempt in range(1, self.max_attempts + 1):
            try:
                return await super()._agenerate(messages, stop=stop, run_manager=run_manager, **kwargs)
            except Exception as e:  # noqa: BLE001
                last_exc = e
                if attempt >= self.max_attempts or not _is_retryable(e):
                    raise
                logger.warning(f"LLM 异步调用失败（第 {attempt} 次），{self.retry_delay * attempt:.1f}s 后重试: {str(e)[:120]}")
                await asyncio.sleep(self.retry_delay * attempt)
        raise last_exc  # pragma: no cover

    # ---------- 流式 ----------
    def _stream(
        self,
        messages: List[BaseMessage],
        stop: Optional[List[str]] = None,
        run_manager: Optional[CallbackManagerForLLMRun] = None,
        **kwargs: Any,
    ) -> Iterator[ChatResult]:
        import time

        for attempt in range(1, self.max_attempts + 1):
            emitted = False
            try:
                for chunk in super()._stream(messages, stop=stop, run_manager=run_manager, **kwargs):
                    emitted = True
                    yield chunk
                return
            except Exception as e:  # noqa: BLE001
                if emitted or attempt >= self.max_attempts or not _is_retryable(e):
                    raise
                logger.warning(f"LLM 流式调用失败（第 {attempt} 次），{self.retry_delay * attempt:.1f}s 后重试: {str(e)[:120]}")
                time.sleep(self.retry_delay * attempt)

    async def _astream(
        self,
        messages: List[BaseMessage],
        stop: Optional[List[str]] = None,
        run_manager: Optional[AsyncCallbackManagerForLLMRun] = None,
        **kwargs: Any,
    ) -> AsyncIterator[ChatResult]:
        for attempt in range(1, self.max_attempts + 1):
            emitted = False
            try:
                async for chunk in super()._astream(messages, stop=stop, run_manager=run_manager, **kwargs):
                    emitted = True
                    yield chunk
                return
            except Exception as e:  # noqa: BLE001
                if emitted or attempt >= self.max_attempts or not _is_retryable(e):
                    raise
                logger.warning(f"LLM 异步流式调用失败（第 {attempt} 次），{self.retry_delay * attempt:.1f}s 后重试: {str(e)[:120]}")
                await asyncio.sleep(self.retry_delay * attempt)


def create_chat_qwen(
    model: str | None = None,
    temperature: float = 0.0,
    streaming: bool = False,
    **kwargs: Any,
) -> RetryingChatQwen:
    """创建带重试的 ChatQwen（自动注入 api_key / api_base + 重试参数）"""
    return RetryingChatQwen(
        model=model or config.rag_model,
        api_key=config.dashscope_api_key,
        api_base=config.dashscope_api_base,
        temperature=temperature,
        streaming=streaming,
        max_attempts=max(1, config.llm_max_retries),
        retry_delay=config.llm_retry_delay,
        **kwargs,
    )
