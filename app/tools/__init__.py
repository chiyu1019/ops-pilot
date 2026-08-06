"""工具模块 - 供 Agent 调用的各种工具

采用惰性导入：避免在导入 app.tools 时立即拉起知识库 / 向量栈，
使纯工具（时间、告警查询等）可独立测试，也便于缺少 API Key / Milvus 时应用仍可启动。
"""

from typing import Any

_LAZY_MODULES = {
    "retrieve_knowledge": "app.tools.knowledge_tool",
    "query_prometheus_alerts": "app.tools.query_metrics_alerts",
    "get_current_time": "app.tools.time_tool",
}

__all__ = [
    "DEFAULT_LOCAL_AGENT_TOOLS",
    "retrieve_knowledge",
    "get_current_time",
    "query_prometheus_alerts",
]


def __getattr__(name: str) -> Any:
    """PEP 562 惰性导入：仅在真正访问工具时才加载对应模块。"""
    if name in _LAZY_MODULES:
        import importlib

        module = importlib.import_module(_LAZY_MODULES[name])
        return getattr(module, name)
    if name == "DEFAULT_LOCAL_AGENT_TOOLS":
        from app.tools.knowledge_tool import retrieve_knowledge
        from app.tools.query_metrics_alerts import query_prometheus_alerts
        from app.tools.time_tool import get_current_time

        return (retrieve_knowledge, get_current_time, query_prometheus_alerts)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
