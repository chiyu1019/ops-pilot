"""运行指标采集：基于 LangChain Callback 统计 Token、工具调用、节点数

可选集成 Langfuse：设置 LANGFUSE_PUBLIC_KEY / LANGFUSE_SECRET_KEY / LANGFUSE_HOST
后自动挂载 Langfuse CallbackHandler；未配置时静默跳过。
"""

from __future__ import annotations

import os
from typing import Any, Dict, List

from langchain_core.callbacks import BaseCallbackHandler
from loguru import logger

NODE_NAMES = {"planner", "executor", "replanner", "diagnose"}


class RunMetricsCollector(BaseCallbackHandler):
    """汇总一次诊断运行的模型、工具、节点与 Token 指标"""

    def __init__(self) -> None:
        self.llm_calls = 0
        self.prompt_tokens = 0
        self.completion_tokens = 0
        self.total_tokens = 0
        self.tool_calls = 0
        self.tool_cache_hits = 0
        self.nodes: List[str] = []

    # ---------- LLM ----------
    def on_llm_end(self, response: Any, **kwargs: Any) -> None:
        self.llm_calls += 1
        usage: Dict[str, Any] | None = None

        llm_output = getattr(response, "llm_output", None) or {}
        usage = llm_output.get("token_usage") or llm_output.get("usage") or usage

        if not usage:
            for generations in getattr(response, "generations", []) or []:
                for gen in generations:
                    message = getattr(gen, "message", None)
                    meta = getattr(message, "usage_metadata", None) if message else None
                    if meta:
                        usage = {
                            "prompt_tokens": meta.get("input_tokens"),
                            "completion_tokens": meta.get("output_tokens"),
                            "total_tokens": meta.get("total_tokens"),
                        }
                        break
                if usage:
                    break

        if usage:
            self.prompt_tokens += int(usage.get("prompt_tokens") or 0)
            self.completion_tokens += int(usage.get("completion_tokens") or 0)
            total = usage.get("total_tokens")
            self.total_tokens += int(total) if total else int(usage.get("prompt_tokens") or 0) + int(
                usage.get("completion_tokens") or 0
            )

    # ---------- 工具 ----------
    def on_tool_start(self, serialized: Dict[str, Any], input_str: str, **kwargs: Any) -> None:
        self.tool_calls += 1

    # ---------- 节点 ----------
    def on_chain_start(self, serialized: Dict[str, Any], inputs: Any, **kwargs: Any) -> None:
        name = (serialized or {}).get("name") or ""
        if name in NODE_NAMES:
            self.nodes.append(name)

    def snapshot(self) -> Dict[str, Any]:
        return {
            "llm_calls": self.llm_calls,
            "prompt_tokens": self.prompt_tokens,
            "completion_tokens": self.completion_tokens,
            "total_tokens": self.total_tokens,
            "tool_calls": self.tool_calls,
            "node_count": len(self.nodes),
            "nodes": self.nodes,
        }


def build_langfuse_handler() -> Any | None:
    """配置了 Langfuse 环境变量时返回 CallbackHandler，否则返回 None"""
    if not (os.environ.get("LANGFUSE_PUBLIC_KEY") and os.environ.get("LANGFUSE_SECRET_KEY")):
        return None
    try:
        from langfuse.langchain import CallbackHandler  # type: ignore

        handler = CallbackHandler()
        logger.info("已启用 Langfuse 全链路观测")
        return handler
    except Exception as e:  # SDK 未安装或版本不匹配时静默跳过
        logger.warning(f"Langfuse 未启用: {e}")
        return None
