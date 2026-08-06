"""MCP 客户端辅助函数单元测试"""

from app.agent.mcp_client import format_exception_chain, suggest_mcp_transport


def test_format_exception_chain_flat():
    text = format_exception_chain(ValueError("simple"))
    assert "ValueError: simple" in text


def test_format_exception_chain_nested_cause():
    cause = RuntimeError("root cause")
    err = ValueError("outer")
    err.__cause__ = cause
    text = format_exception_chain(err)
    assert "outer" in text
    assert "root cause" in text


def test_suggest_mcp_transport_sse_hint():
    hint = suggest_mcp_transport("https://mcp.example.com/sse/xxx", "streamable-http")
    assert hint is not None
    assert "sse" in hint


def test_suggest_mcp_transport_streamable_hint():
    hint = suggest_mcp_transport("http://localhost:8003/mcp", "sse")
    assert hint is not None
    assert "streamable-http" in hint


def test_suggest_mcp_transport_no_hint():
    assert suggest_mcp_transport("http://localhost:8003/mcp", "streamable-http") is None
