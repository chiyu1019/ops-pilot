"""通知数据结构（Pydantic）

DiagnosisNotification：一次诊断要推送给 IM 的结构化消息（9 个展示字段 + 来源）
NotificationResult：发送结果（统一给调用方，不抛异常）
"""

from __future__ import annotations

import hashlib
import re
from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

# 来源标记：只有 alert_auto 会推送飞书
SOURCE_ALERT_AUTO = "alert_auto"
SOURCE_USER_CHAT = "user_chat"

# 状态语义
STATUS_LABELS = {
    "verified": "✅ 已验证（证据链校验通过）",
    "hypothesis": "⚠️ 假设（证据不足，需人工确认）",
    "safe_report": "🛟 安全报告（无法完成证据校验）",
    "success": "✅ 已完成",
}

SEVERITY_EMOJI = {
    "critical": "🔴",
    "warning": "🟠",
    "info": "🔵",
    "emergency": "🟣",
}


def _clip(text: Any, limit: int) -> str:
    """截断长文本（飞书单字段长度有限，避免整条消息被拒）"""
    s = str(text or "").strip()
    return s if len(s) <= limit else s[: limit - 1] + "…"


class DiagnosisNotification(BaseModel):
    """诊断通知消息（字段顺序即卡片展示顺序）"""

    # ---- 9 个展示字段 ----
    alert_name: str = Field(default="AIOps诊断", description="1 告警名称")
    severity: str = Field(default="unknown", description="2 告警级别")
    service: str = Field(default="未知服务", description="3 影响服务")
    summary: str = Field(default="（无描述）", description="4 故障现象")
    diagnosis: str = Field(default="（未得出结论）", description="5 分析结论")
    evidence: List[str] = Field(default_factory=list, description="6 关键证据")
    suggestion: str = Field(default="建议人工复核", description="7 处理建议")
    status: str = Field(default="success", description="8 Agent 执行状态")
    generated_at: str = Field(
        default_factory=lambda: datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        description="9 生成时间",
    )

    # ---- 元信息（不占用展示字段）----
    source: str = Field(default=SOURCE_USER_CHAT, description="来源：alert_auto / user_chat")
    session_id: str = Field(default="", description="会话 ID")

    # ---------- 映射：LangGraph state -> 通知消息 ----------
    @classmethod
    def from_agent_state(
        cls,
        state: Dict[str, Any],
        alert: Optional[Dict[str, Any]] = None,
        task_input: str = "",
        source: str = SOURCE_USER_CHAT,
        session_id: str = "",
        max_evidence: int = 5,
    ) -> "DiagnosisNotification":
        """从工作流最终状态映射出通知消息（纯数据转换，不依赖 Agent 内部实现）"""
        state = state or {}
        diagnosis = state.get("diagnosis") or {}
        verification = state.get("verification") or {}
        labels = (alert or {}).get("labels") or {}
        annotations = (alert or {}).get("annotations") or {}

        # 1) 告警名称：labels -> 任务描述 -> 兜底
        alert_name = str(labels.get("alertname") or "").strip()
        if not alert_name:
            m = re.search(r"告警[：:]\s*([\w\-.]+)", task_input or "") or re.search(
                r"alertname[：: ]+([\w\-.]+)", task_input or ""
            )
            alert_name = m.group(1) if m else "AIOps诊断"

        # 2) 级别 / 3) 影响服务 / 4) 故障现象
        severity = str(labels.get("severity") or "unknown").lower()
        service = str(labels.get("instance") or labels.get("pod") or "未知服务")
        summary = str(annotations.get("description") or annotations.get("summary") or "").strip()
        if not summary:
            summary = _clip(task_input, 200) if task_input else "（无描述）"

        # 5) 分析结论
        diagnosis_text = str(diagnosis.get("root_cause") or "").strip() or "（未得出结论）"

        # 6) 关键证据：claim 引用的 evidence_id -> EvidenceRecord.summary
        evidence_index = {
            str(r.get("evidence_id")): r for r in (state.get("evidence") or []) if r.get("evidence_id")
        }
        evidence_items: List[str] = []
        for claim in diagnosis.get("claims") or []:
            for eid in claim.get("evidence_ids") or []:
                rec = evidence_index.get(str(eid))
                if rec:
                    item = f"{rec.get('summary', '')}（{rec.get('tool', '')}）".strip()
                    if item and item not in evidence_items:
                        evidence_items.append(item)
        if not evidence_items:  # 兜底：用结论本身充当前几条证据说明
            evidence_items = [
                _clip(c.get("claim", ""), 120) for c in (diagnosis.get("claims") or [])[:3] if c.get("claim")
            ]

        # 7) 处理建议
        recs = [str(r).strip() for r in (diagnosis.get("recommendations") or []) if str(r).strip()]
        suggestion = "\n".join(f"{i}. {_clip(r, 100)}" for i, r in enumerate(recs[:3], 1)) or "建议人工复核"

        # 8) Agent 执行状态（保留 verified / hypothesis / safe_report）
        status = str(diagnosis.get("status") or ("verified" if verification.get("strict_pass") else "hypothesis"))
        repair_rounds = int(state.get("repair_rounds") or 0)
        if status == "verified" and repair_rounds > 0:
            status_label = f"{STATUS_LABELS['verified']}（经 {repair_rounds} 轮补证）"
        else:
            status_label = STATUS_LABELS.get(status, status)

        return cls(
            alert_name=alert_name,
            severity=severity,
            service=service,
            summary=_clip(summary, 300),
            diagnosis=_clip(diagnosis_text, 800),
            evidence=[_clip(e, 120) for e in evidence_items[:max_evidence]],
            suggestion=suggestion,
            status=status_label,
            source=source,
            session_id=session_id,
        )

    # ---------- 幂等键 ----------
    def idempotency_key(self) -> str:
        """同一来源 + 同一会话 + 同一告警 + 同一状态 -> 视为同一条通知"""
        raw = f"{self.source}|{self.session_id}|{self.alert_name}|{self.service}|{self.status}"
        return hashlib.sha1(raw.encode("utf-8")).hexdigest()[:16]

    @property
    def severity_emoji(self) -> str:
        return SEVERITY_EMOJI.get(self.severity, "⚪")


class NotificationResult(BaseModel):
    """通知发送结果（统一返回，便于观测与测试断言）"""

    sent: bool = False
    channel: str = "feishu"
    skipped: bool = False
    reason: str = ""
    error: Optional[str] = None
