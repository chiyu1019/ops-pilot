"""会话记忆后端管理单元测试（memory / redis / postgres）"""

import socket

import pytest

import app.core.checkpointer as cp


@pytest.fixture(autouse=True)
async def reset_checkpointer():
    cp._checkpointer = None
    cp._postgres_cm = None
    yield
    await cp.aclose_checkpointer()


async def test_default_backend_is_memory(monkeypatch):
    monkeypatch.setattr(cp.config, "memory_backend", "memory")
    saver = await cp.aget_checkpointer()
    assert type(saver).__name__ in ("MemorySaver", "InMemorySaver")


async def test_unknown_backend_falls_back_to_memory(monkeypatch):
    monkeypatch.setattr(cp.config, "memory_backend", "unknown-xyz")
    saver = await cp.aget_checkpointer()
    assert type(saver).__name__ in ("MemorySaver", "InMemorySaver")


async def test_get_checkpointer_is_singleton(monkeypatch):
    monkeypatch.setattr(cp.config, "memory_backend", "memory")
    assert await cp.aget_checkpointer() is await cp.aget_checkpointer()


def _port_open(host: str, port: int) -> bool:
    try:
        with socket.create_connection((host, port), timeout=1):
            return True
    except OSError:
        return False


redis_available = pytest.mark.skipif(
    not _port_open("localhost", 6380), reason="Redis Stack 未启动（docker compose 中 opspilot-redis）"
)
postgres_available = pytest.mark.skipif(
    not _port_open("localhost", 5432), reason="Postgres 未启动（docker compose 中 opspilot-postgres）"
)


@redis_available
async def test_redis_checkpointer(monkeypatch):
    monkeypatch.setattr(cp.config, "memory_backend", "redis")
    monkeypatch.setattr(cp.config, "redis_url", "redis://localhost:6380/0")
    saver = await cp.aget_checkpointer()
    assert type(saver).__name__ == "AsyncRedisSaver"


@postgres_available
async def test_postgres_checkpointer(monkeypatch):
    monkeypatch.setattr(cp.config, "memory_backend", "postgres")
    monkeypatch.setattr(
        cp.config,
        "postgres_dsn",
        "postgresql://postgres:postgres@localhost:5432/langgraph",
    )
    saver = await cp.aget_checkpointer()
    assert type(saver).__name__ == "AsyncPostgresSaver"
