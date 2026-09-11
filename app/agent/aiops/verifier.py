"""Verifier：对 StructuredDiagnosis 做确定性证据链校验

校验规则（严格模式）：
1. 每条 claim 必须至少引用一个证据 ID
2. 引用的每个 evidence_id 必须真实存在于本次执行收集到的证据集合中
3. strict_pass = 所有 claim 均满足 1、2
覆盖率 = 有有效证据支撑的 claim 数 / claim 总数
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, Iterable, List, Set

from loguru import logger


@dataclass
class VerificationResult:
    """校验结果"""

    strict_pass: bool = False
    coverage: float = 0.0
    total_claims: int = 0
    supported_claims: int = 0
    invalid_evidence_ids: List[str] = field(default_factory=list)
    unsupported_claims: List[str] = field(default_factory=list)
    missing_hints: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "strict_pass": self.strict_pass,
            "coverage": round(self.coverage, 4),
            "total_claims": self.total_claims,
            "supported_claims": self.supported_claims,
            "invalid_evidence_ids": self.invalid_evidence_ids,
            "unsupported_claims": self.unsupported_claims,
            "missing_hints": self.missing_hints,
        }


def _as_dicts(diagnosis: Any) -> List[Dict[str, Any]]:
    """兼容 Pydantic 模型与 dict，统一成 dict 列表"""
    claims = getattr(diagnosis, "claims", None)
    if claims is None and isinstance(diagnosis, dict):
        claims = diagnosis.get("claims", [])
    out: List[Dict[str, Any]] = []
    for c in claims or []:
        if isinstance(c, dict):
            out.append(c)
        else:  # Pydantic 模型
            out.append(
                {
                    "claim": getattr(c, "claim", ""),
                    "evidence_ids": list(getattr(c, "evidence_ids", []) or []),
                    "confidence": getattr(c, "confidence", 0.5),
                }
            )
    return out


def verify(diagnosis: Any, valid_evidence_ids: Iterable[str]) -> VerificationResult:
    """对结构化诊断执行证据链校验"""
    valid: Set[str] = {str(e) for e in (valid_evidence_ids or [])}
    claims = _as_dicts(diagnosis)

    result = VerificationResult(total_claims=len(claims))
    if not claims:
        result.missing_hints.append("未产出任何诊断结论（claims 为空）")
        logger.warning("证据校验：claims 为空，判定为不通过")
        return result

    for c in claims:
        ids = [str(i) for i in (c.get("evidence_ids") or []) if str(i).strip()]
        bad = [i for i in ids if i not in valid]
        result.invalid_evidence_ids.extend(bad)

        if not ids:
            result.unsupported_claims.append(c.get("claim", ""))
            result.missing_hints.append(f"结论缺少证据引用：{c.get('claim', '')[:80]}")
        elif bad:
            result.unsupported_claims.append(c.get("claim", ""))
            result.missing_hints.append(
                f"结论引用了不存在的证据 {bad}：{c.get('claim', '')[:80]}"
            )
        else:
            result.supported_claims += 1

    result.coverage = result.supported_claims / result.total_claims
    result.strict_pass = result.supported_claims == result.total_claims

    logger.info(
        f"证据校验：strict_pass={result.strict_pass} 覆盖率={result.coverage:.2%} "
        f"({result.supported_claims}/{result.total_claims})"
    )
    return result
