"""确定性证据链：把 MCP 工具结果抽取为 EvidenceRecord / EvidenceFact

设计要点：
- 抽取完全基于规则（不依赖 LLM），保证证据可追溯、可复现
- EvidenceRecord 记录"证据来自哪次工具调用"；EvidenceFact 是结构化事实（key/value）
- state 中以 dict 形式存储（可被 LangGraph checkpointer 序列化）
"""

from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime, timezone
from typing import Any, Dict, Iterable, List, Optional, Sequence

from loguru import logger

MAX_EXCERPT = 1200


def _short_hash(text: str, length: int = 10) -> str:
    return hashlib.sha1(text.encode("utf-8")).hexdigest()[:length]


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _truncate(text: str, limit: int = MAX_EXCERPT) -> str:
    text = str(text or "")
    return text if len(text) <= limit else text[:limit] + f"...[truncated {len(text) - limit} chars]"


def _try_json(text: str) -> Any:
    """尝试从工具输出中解析 JSON（部分工具返回 JSON 字符串）"""
    text = (text or "").strip()
    if not text:
        return None
    try:
        return json.loads(text)
    except Exception:
        # 尝试截取第一个 { 到最后一个 }
        start, end = text.find("{"), text.rfind("}")
        if 0 <= start < end:
            try:
                return json.loads(text[start : end + 1])
            except Exception:
                return None
    return None


def build_record(tool: str, args: Dict[str, Any], result: Any, tool_call_id: str = "") -> Dict[str, Any]:
    """构造一条证据记录（确定性）"""
    result_text = result if isinstance(result, str) else json.dumps(result, ensure_ascii=False, default=str)
    signature = f"{tool}:{json.dumps(args, ensure_ascii=False, sort_keys=True, default=str)}:{_short_hash(result_text)}"
    return {
        "evidence_id": f"ev-{_short_hash(signature)}",
        "tool": tool,
        "tool_call_id": tool_call_id,
        "args": args or {},
        "summary": _summarize(tool, result_text),
        "excerpt": _truncate(result_text),
        "collected_at": _now(),
    }


def _summarize(tool: str, text: str) -> str:
    """一句话摘要（规则化）"""
    data = _try_json(text)
    if tool == "query_prometheus_alerts":
        alerts = _alerts_from(data)
        firing = [a for a in alerts if str(a.get("state", "")).lower() == "firing"]
        return f"Prometheus 告警查询：命中 {len(alerts)} 条，其中 firing {len(firing)} 条"
    if tool in ("query_cpu_metrics", "query_memory_metrics"):
        stats = (data or {}).get("statistics", {}) if isinstance(data, dict) else {}
        if stats:
            return (
                f"{tool}：avg={stats.get('avg')} max={stats.get('max')} "
                f"min={stats.get('min')} p95={stats.get('p95')}"
            )
        return f"{tool}：返回 {len(text)} 字符数据"
    if tool in ("search_log", "search_service_logs"):
        total = (data or {}).get("total") if isinstance(data, dict) else None
        error_like = len(re.findall(r"\b(error|exception|timeout|refused|failed)\b", text, re.I))
        return f"{tool}：返回 {total if total is not None else '未知'} 条日志，疑似错误关键字 {error_like} 次"
    if tool == "retrieve_knowledge":
        files = re.findall(r"来源[:：]\s*(\S+)", text)
        return f"知识库检索：命中 {len(files)} 篇文档 {files[:3]}"
    return f"{tool}：输出 {len(text)} 字符"


def _alerts_from(data: Any) -> List[Dict[str, Any]]:
    """从工具返回结构中提取告警列表（兼容 mock 与实际格式）"""
    if isinstance(data, dict):
        if isinstance(data.get("alerts"), list):
            return [a for a in data["alerts"] if isinstance(a, dict)]
        inner = data.get("data")
        if isinstance(inner, dict) and isinstance(inner.get("alerts"), list):
            return [a for a in inner["alerts"] if isinstance(a, dict)]
    return []


def extract_records_from_tool_messages(tool_messages: Sequence[Any]) -> List[Dict[str, Any]]:
    """从 LangChain ToolMessage 列表抽取证据（executor 中调用）"""
    records: List[Dict[str, Any]] = []
    for msg in tool_messages or []:
        name = getattr(msg, "name", None) or getattr(msg, "tool_name", "") or "unknown_tool"
        content = getattr(msg, "content", "")
        if isinstance(content, list):  # 多模态/分块内容
            content = json.dumps(content, ensure_ascii=False, default=str)
        args = {}
        tool_call_id = getattr(msg, "tool_call_id", "") or ""
        records.append(build_record(str(name), args, content, str(tool_call_id)))
    if records:
        logger.info(f"证据抽取：新增 {len(records)} 条 EvidenceRecord")
    return records


def extract_facts(records: Iterable[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """规则化抽取 EvidenceFact（key/value + 来源证据 id）"""
    facts: List[Dict[str, Any]] = []
    seen: set[tuple] = set()

    def add(evidence_id: str, key: str, value: Any) -> None:
        sig = (key, str(value))
        if sig in seen:
            return
        seen.add(sig)
        facts.append(
            {
                "fact_id": f"fact-{_short_hash(key + str(value))}",
                "evidence_ids": [evidence_id],
                "key": key,
                "value": str(value),
            }
        )

    for rec in records:
        ev_id = rec.get("evidence_id", "")
        tool = rec.get("tool", "")
        text = rec.get("excerpt", "")
        data = _try_json(text)

        if tool == "query_prometheus_alerts":
            for alert in _alerts_from(data):
                labels = alert.get("labels", {}) or {}
                name = labels.get("alertname", "unknown")
                state = alert.get("state", "unknown")
                instance = labels.get("instance") or labels.get("pod") or ""
                add(ev_id, f"alert.{name}.state", state)
                if instance:
                    add(ev_id, f"alert.{name}.instance", instance)
                dur = alert.get("duration")
                if dur:
                    add(ev_id, f"alert.{name}.duration", dur)

        elif tool in ("query_cpu_metrics", "query_memory_metrics"):
            stats = (data or {}).get("statistics", {}) if isinstance(data, dict) else {}
            for k in ("avg", "max", "min", "p95"):
                if stats.get(k) is not None:
                    add(ev_id, f"{tool}.{k}", stats.get(k))

        elif tool in ("search_log", "search_service_logs"):
            if isinstance(data, dict):
                if data.get("total") is not None:
                    add(ev_id, f"{tool}.total", data.get("total"))
                logs = data.get("logs")
                if isinstance(logs, list):
                    errs = [l for l in logs if str(l.get("level", "")).upper() in ("ERROR", "WARN", "CRITICAL")]
                    add(ev_id, f"{tool}.error_like_count", len(errs))
                    if errs:
                        add(ev_id, f"{tool}.first_error", str(errs[0].get("message", ""))[:200])

        elif tool == "retrieve_knowledge":
            for f in re.findall(r"来源[:：]\s*(\S+)", text)[:5]:
                add(ev_id, "knowledge.source", f)

        else:
            add(ev_id, f"{tool}.output_length", len(text))

    logger.info(f"事实抽取：共 {len(facts)} 条 EvidenceFact")
    return facts


def build_index(records: Iterable[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    """evidence_id -> record 索引"""
    return {r.get("evidence_id", ""): r for r in records if r.get("evidence_id")}
