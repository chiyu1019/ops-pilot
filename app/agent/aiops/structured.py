"""结构化诊断模型：DiagnosisClaim / StructuredDiagnosis

LLM 只能基于给定证据（EvidenceRecord / EvidenceFact）产出结论，
每条结论必须携带 evidence_ids，便于 Verifier 做确定性校验。
"""

from __future__ import annotations

from typing import List

from pydantic import BaseModel, Field


class DiagnosisClaim(BaseModel):
    """单条诊断结论（必须可追溯到证据）"""

    claim: str = Field(description="一条具体的、可验证的诊断结论")
    evidence_ids: List[str] = Field(
        default_factory=list,
        description="支撑该结论的证据 ID 列表，必须来自输入中给出的证据，不得编造",
    )
    confidence: float = Field(default=0.5, ge=0.0, le=1.0, description="结论置信度 0-1")


class StructuredDiagnosis(BaseModel):
    """结构化诊断结果"""

    root_cause: str = Field(description="根因结论（一句话）")
    claims: List[DiagnosisClaim] = Field(
        default_factory=list, description="支撑根因的关键结论列表（每条都要有证据引用）"
    )
    recommendations: List[str] = Field(default_factory=list, description="处置建议列表")
    status: str = Field(
        default="hypothesis",
        description="诊断状态：verified（证据充分）/ hypothesis（证据不足，属推测）/ safe_report（无法诊断）",
    )
