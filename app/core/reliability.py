"""可靠性约束与成本治理

提供三件事：
1. tool_call_fingerprint：工具名 + 参数 -> 稳定指纹（用于结果缓存）
2. ToolResultCache：进程级工具结果缓存（相同指纹直接复用，避免重复调用与重复上下文）
3. ReliabilityState：维护 Token 预算、缓存命中、上下文压缩统计

设计要点：上下文压缩只影响"喂给 LLM 的文本"，**证据链抽取始终使用工具的原始返回**，
因此压缩不会削弱证据校验能力。
"""

from __future__ import annotations

import hashlib
import json
import threading
from dataclasses import asdict, dataclass, field
from typing import Any, Dict, Optional

from loguru import logger


def tool_call_fingerprint(tool_name: str, args: Any) -> str:
    """稳定指纹：同一工具 + 同一参数视为同一次调用"""
    try:
        payload = json.dumps(args, ensure_ascii=False, sort_keys=True, default=str)
    except Exception:
        payload = str(args)
    return hashlib.sha1(f"{tool_name}::{payload}".encode("utf-8")).hexdigest()[:16]


@dataclass
class ReliabilityState:
    """一次运行内的可靠性/成本统计"""

    token_budget: int = 0
    estimated_tokens: int = 0
    tool_calls: int = 0
    tool_cache_hits: int = 0
    tool_cache_misses: int = 0
    compressed_chars_saved: int = 0
    budget_exceeded: bool = False
    notes: list = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @staticmethod
    def from_dict(data: Optional[Dict[str, Any]]) -> "ReliabilityState":
        data = data or {}
        return ReliabilityState(
            token_budget=int(data.get("token_budget", 0) or 0),
            estimated_tokens=int(data.get("estimated_tokens", 0) or 0),
            tool_calls=int(data.get("tool_calls", 0) or 0),
            tool_cache_hits=int(data.get("tool_cache_hits", 0) or 0),
            tool_cache_misses=int(data.get("tool_cache_misses", 0) or 0),
            compressed_chars_saved=int(data.get("compressed_chars_saved", 0) or 0),
            budget_exceeded=bool(data.get("budget_exceeded", False)),
            notes=list(data.get("notes", []) or []),
        )


class ToolResultCache:
    """进程级工具结果缓存（key = tool_call_fingerprint）"""

    def __init__(self, max_entries: int = 500) -> None:
        self._data: Dict[str, str] = {}
        self._lock = threading.Lock()
        self._max = max_entries
        self.hits = 0
        self.misses = 0

    def get(self, key: str) -> Optional[str]:
        with self._lock:
            if key in self._data:
                self.hits += 1
                return self._data[key]
            self.misses += 1
            return None

    def set(self, key: str, value: str) -> None:
        with self._lock:
            if len(self._data) >= self._max:
                self._data.clear()
            self._data[key] = value

    def clear(self) -> None:
        with self._lock:
            self._data.clear()

    def stats(self) -> Dict[str, int]:
        return {"hits": self.hits, "misses": self.misses, "size": len(self._data)}


# 全局缓存（进程内共享，评测脚本可 clear 以隔离用例）
tool_result_cache = ToolResultCache()


def estimate_tokens(text: str) -> int:
    """粗略 Token 估算（中文约 1 字 1 token，英文约 4 字符 1 token）"""
    text = text or ""
    if not text:
        return 0
    return int(len(text) * 0.7) + 1


def compress_text(text: str, max_chars: int) -> str:
    """上下文压缩：超长内容截断并标注，返回压缩后文本"""
    text = str(text or "")
    if max_chars <= 0 or len(text) <= max_chars:
        return text
    head = text[: int(max_chars * 0.7)]
    tail = text[-int(max_chars * 0.2) :]
    return f"{head}\n...[上下文压缩：省略 {len(text) - len(head) - len(tail)} 字符]...\n{tail}"
