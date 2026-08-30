"""会话记忆后端管理：内存 / Redis / Postgres（LangGraph checkpointer）

通过 config.memory_backend 切换（memory | redis | postgres）：
- memory   : InMemorySaver（默认，进程内，重启丢失）
- redis    : AsyncRedisSaver（持久化，需要 Redis Stack / RediSearch）
- postgres : AsyncPostgresSaver（持久化 + 事务，适合生产）

注意：LangGraph 异步执行需要 checkpointer 的 aput/aget 等异步实现，
因此 Redis / Postgres 使用官方 Async 版本；MemorySaver 同时支持同步/异步。
"""

from __future__ import annotations

import asyncio
import inspect
from typing import Any

from loguru import logger

from app.config import config

# 注意：必须用 asyncio.Lock，threading.Lock 在 await 期间持锁会阻塞事件循环造成死锁
_lock = asyncio.Lock()
_checkpointer: Any = None
_postgres_cm: Any = None


async def _maybe_await(value: Any) -> Any:
    """兼容 setup() 可能返回协程的情况。"""
    if inspect.isawaitable(value):
        return await value
    return value


async def aget_checkpointer():
    """获取全局 checkpointer（异步惰性创建，线程安全，进程内单例）。"""
    global _checkpointer
    if _checkpointer is not None:
        return _checkpointer
    async with _lock:
        if _checkpointer is not None:
            return _checkpointer
        backend = config.memory_backend.strip().lower()
        if backend == "redis":
            _checkpointer = await _create_redis_checkpointer()
        elif backend == "postgres":
            _checkpointer = await _create_postgres_checkpointer()
        else:
            from langgraph.checkpoint.memory import InMemorySaver

            _checkpointer = InMemorySaver()
        logger.info(f"会话记忆后端: {backend} -> {type(_checkpointer).__name__}")
        return _checkpointer


async def _create_redis_checkpointer():
    """创建 Redis 持久化 checkpointer（AsyncRedisSaver）。"""
    from langgraph.checkpoint.redis.aio import AsyncRedisSaver

    saver = AsyncRedisSaver(redis_url=config.redis_url)
    await _maybe_await(saver.setup())
    logger.info(f"Redis checkpointer 就绪: {config.redis_url}")
    return saver


async def _create_postgres_checkpointer():
    """创建 Postgres 持久化 checkpointer（AsyncPostgresSaver）。"""
    global _postgres_cm
    from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver

    _postgres_cm = AsyncPostgresSaver.from_conn_string(config.postgres_dsn)
    saver = await _postgres_cm.__aenter__()
    await _maybe_await(saver.setup())  # 创建 checkpoint 数据表
    logger.info(f"Postgres checkpointer 就绪: {config.postgres_dsn}")
    return saver


async def aclose_checkpointer() -> None:
    """关闭持久化 checkpointer（应用退出时调用）。"""
    global _checkpointer, _postgres_cm
    async with _lock:
        if _checkpointer is None:
            return
        backend = config.memory_backend.strip().lower()
        try:
            if backend == "postgres" and _postgres_cm is not None:
                await _postgres_cm.__aexit__(None, None, None)
                _postgres_cm = None
        except Exception as e:  # noqa: BLE001
            logger.warning(f"关闭 checkpointer 失败: {e}")
        _checkpointer = None
        logger.info("会话记忆 checkpointer 已关闭")
