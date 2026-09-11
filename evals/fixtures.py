"""Fixture 运行时：为可控评测提供确定性的工具响应（并发安全）

用 ContextVar 保存"当前场景"，因此多个用例可以并发执行而互不干扰。
工具在**调用时**读取当前场景，因此 patch_tools() 只需安装一次。
"""

from __future__ import annotations

import json
from contextvars import ContextVar
from typing import Any, Dict, List

from langchain_core.tools import StructuredTool

_current: ContextVar[Dict[str, Any]] = ContextVar("fixture_responses", default={})

FIXTURE_TOOL_NAMES = [
    "query_prometheus_alerts",
    "search_log",
    "query_cpu_metrics",
    "query_memory_metrics",
    "get_current_timestamp",
    "get_topic_info_by_name",
]

_DEFAULT_RESPONSES: Dict[str, Any] = {
    "query_prometheus_alerts": {"alerts": []},
    "search_log": {"total": 0, "logs": []},
    "query_cpu_metrics": {"statistics": {}},
    "query_memory_metrics": {"statistics": {}},
    "get_current_timestamp": {"timestamp": "2026-09-11T03:00:00Z"},
    "get_topic_info_by_name": {"topic_id": "system-metrics"},
}


class FixtureRuntime:
    """激活/还原当前用例的场景响应"""

    def __init__(self) -> None:
        self._token = None
        self.scenario = ""

    def activate(self, scenario: str, responses: Dict[str, Any]) -> None:
        self.scenario = scenario
        self._token = _current.set(dict(responses))

    def deactivate(self) -> None:
        if self._token is not None:
            _current.reset(self._token)
            self._token = None

    @staticmethod
    def responses() -> Dict[str, Any]:
        return _current.get() or {}


def _serialize(payload: Any) -> str:
    if isinstance(payload, (dict, list)):
        return json.dumps(payload, ensure_ascii=False)
    return str(payload)


def _make_tool(name: str, description: str) -> StructuredTool:
    """构造读取当前场景的工具"""

    def _run(*args: Any, **kwargs: Any) -> str:
        responses = FixtureRuntime.responses()
        payload = responses.get(name, _DEFAULT_RESPONSES.get(name, {"message": "no fixture"}))
        return _serialize(payload)

    return StructuredTool.from_function(func=_run, name=name, description=description)


TOOL_DESCRIPTIONS = {
    "query_prometheus_alerts": "查询当前 Prometheus 活跃告警（返回 labels/annotations/state）",
    "search_log": "按主题与时间范围检索日志，支持 level 与关键词过滤",
    "query_cpu_metrics": "查询服务 CPU 使用率指标（含 avg/max/p95 统计）",
    "query_memory_metrics": "查询服务内存使用率指标（含 avg/max/p95 统计）",
    "get_current_timestamp": "获取当前时间戳",
    "get_topic_info_by_name": "按名称查询日志主题信息",
}


def build_fixture_tools() -> List[StructuredTool]:
    return [_make_tool(n, TOOL_DESCRIPTIONS.get(n, f"fixture tool {n}")) for n in FIXTURE_TOOL_NAMES]


def build_knowledge_tool() -> StructuredTool:
    """知识检索工具（读取当前场景提供的知识库文本）"""

    def _kb(query: str = "") -> str:
        responses = FixtureRuntime.responses()
        return str(responses.get("retrieve_knowledge", "（评测场景未提供知识库内容）"))

    return StructuredTool.from_function(
        func=_kb, name="retrieve_knowledge", description="检索内部知识库中的处置经验"
    )


class FixtureMCPClient:
    """替身 MCP 客户端"""

    async def get_tools(self) -> List[StructuredTool]:
        return build_fixture_tools()


def patch_tools() -> None:
    """把 executor/planner/replanner 的工具替换为 fixture 版本（只需调用一次）"""
    import app.agent.aiops.executor as executor_mod
    import app.agent.aiops.planner as planner_mod
    import app.agent.aiops.replanner as replanner_mod
    import app.agent.mcp_client as mcp_mod
    import app.tools as tools_mod

    kb_tool = build_knowledge_tool()
    mcp_tools = build_fixture_tools()

    executor_mod.DEFAULT_LOCAL_AGENT_TOOLS = (kb_tool,) + tuple(mcp_tools)
    planner_mod.DEFAULT_LOCAL_AGENT_TOOLS = (kb_tool,) + tuple(mcp_tools)
    replanner_mod.DEFAULT_LOCAL_AGENT_TOOLS = (kb_tool,) + tuple(mcp_tools)
    tools_mod.DEFAULT_LOCAL_AGENT_TOOLS = (kb_tool,)

    client = FixtureMCPClient()

    async def _fake_get_client(*args: Any, **kwargs: Any):
        return client

    def _fake_create(*args: Any, **kwargs: Any):
        return client

    mcp_mod.get_mcp_client_with_retry = _fake_get_client  # type: ignore[assignment]
    mcp_mod._create_mcp_client = _fake_create  # type: ignore[assignment]
