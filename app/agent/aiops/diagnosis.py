"""Diagnose 节点：基于证据链生成结构化诊断并做确定性校验

流程：
1. 从 state.evidence 中规则化抽取 EvidenceFact
2. LLM 基于【真实证据 + 事实 + 草稿报告】生成 StructuredDiagnosis（每条结论必须引用 evidence_id）
3. Verifier 严格校验证据链：
   - 通过        -> status=verified，输出带证据引用的最终报告
   - 不通过且未补证 -> 产出补证计划，回到 Executor 再执行一轮
   - 仍不通过     -> 降级为 hypothesis / 安全报告（明确标注证据不足）
"""

from __future__ import annotations

from textwrap import dedent
from typing import Any, Dict, List

from langchain_core.prompts import ChatPromptTemplate
from loguru import logger

from app.config import config
from app.core.llm_client import create_chat_qwen
from app.agent.aiops.evidence import build_index, extract_facts
from app.agent.aiops.structured import StructuredDiagnosis
from app.agent.aiops.verifier import verify

DIAGNOSIS_PROMPT = ChatPromptTemplate.from_messages(
    [
        (
            "system",
            dedent(
                """
                你是运维诊断校验专家。你只能基于【证据列表】中的真实证据得出结论，
                每条结论必须引用至少一个存在的证据 ID（形如 ev-xxxxxxxxxx），禁止编造证据 ID。

                输出要求：
                - root_cause：一句话根因
                - claims：3-5 条关键结论，每条包含 claim、evidence_ids、confidence
                - recommendations：处置建议（可不带证据）
                - status：evidence 充分填 verified，不足填 hypothesis
                """
            ).strip(),
        ),
        (
            "human",
            dedent(
                """
                ### 用户任务
                {task}

                ### 证据列表（evidence_id | 工具 | 摘要）
                {evidence_block}

                ### 结构化事实（key = value）
                {facts_block}

                ### 草稿报告
                {draft_report}

                请输出结构化诊断（JSON）。
                """
            ).strip(),
        ),
    ]
)


def _evidence_block(records: List[Dict[str, Any]], limit: int = 12, excerpt: int = 400) -> str:
    lines = []
    for r in records[:limit]:
        lines.append(
            f"- {r.get('evidence_id')} | {r.get('tool')} | {r.get('summary', '')}\n"
            f"    片段: {str(r.get('excerpt', ''))[:excerpt]}"
        )
    return "\n".join(lines) if lines else "（无）"


def _facts_block(facts: List[Dict[str, Any]], limit: int = 30) -> str:
    lines = [f"- {f['key']} = {f['value']}  (证据: {', '.join(f.get('evidence_ids', []))})" for f in facts[:limit]]
    return "\n".join(lines) if lines else "（无）"


def _render_report(draft: str, diagnosis: Dict[str, Any], verification: Dict[str, Any], status: str) -> str:
    """渲染最终报告：原报告 + 结构化诊断（含证据引用与校验结论）"""
    status_label = {
        "verified": "✅ 证据链校验通过",
        "hypothesis": "⚠️ 证据不足，以下结论为假设（hypothesis）",
        "safe_report": "🛟 无法完成证据校验，输出安全报告",
    }.get(status, status)

    lines: List[str] = []
    if draft.strip():
        lines.append(draft.strip())
    lines.append("\n---\n")
    lines.append("## 🔗 结构化诊断（证据链）")
    lines.append(f"\n**状态**：{status_label}")
    lines.append(f"\n**根因结论**：{diagnosis.get('root_cause', '未得出结论')}")
    lines.append("\n**关键结论与证据引用**")
    for c in diagnosis.get("claims", []):
        ids = "、".join(c.get("evidence_ids", [])) or "无"
        conf = c.get("confidence", 0.5)
        lines.append(f"- {c.get('claim', '')}")
        lines.append(f"  - 证据：`{ids}`　置信度：{conf}")
    recs = diagnosis.get("recommendations", [])
    if recs:
        lines.append("\n**处置建议**")
        for i, r in enumerate(recs, 1):
            lines.append(f"{i}. {r}")
    lines.append("\n**校验结果**")
    lines.append(
        f"- 严格校验：{'通过' if verification.get('strict_pass') else '未通过'}"
        f"　证据覆盖率：{float(verification.get('coverage', 0)) * 100:.2f}%"
        f"（{verification.get('supported_claims', 0)}/{verification.get('total_claims', 0)} 条结论有有效证据）"
    )
    invalid = verification.get("invalid_evidence_ids") or []
    if invalid:
        lines.append(f"- 检出无效证据引用：{invalid}")
    hints = verification.get("missing_hints") or []
    if hints:
        lines.append("- 证据缺口：" + "；".join(h[:120] for h in hints[:5]))
    return "\n".join(lines)


async def diagnose(state: Dict[str, Any]) -> Dict[str, Any]:
    """诊断校验节点"""
    evidence: List[Dict[str, Any]] = list(state.get("evidence", []) or [])
    draft = state.get("response", "") or ""
    repair_rounds = int(state.get("repair_rounds", 0) or 0)
    task = state.get("input", "")

    logger.info(f"=== Diagnose：证据校验（证据 {len(evidence)} 条，补证轮次 {repair_rounds}）===")

    if not config.diagnosis_verify_enabled:
        return {}

    facts = extract_facts(evidence)
    index = build_index(evidence)

    # 没有证据：直接安全报告，不调用 LLM
    if not evidence:
        verification = verify({"claims": []}, index.keys()).to_dict()
        diagnosis = {
            "root_cause": "未收集到任何工具证据，无法诊断",
            "claims": [],
            "recommendations": ["检查监控/日志工具连通性后重试"],
            "status": "safe_report",
        }
        return {
            "diagnosis": diagnosis,
            "verification": verification,
            "response": _render_report(draft, diagnosis, verification, "safe_report"),
        }

    try:
        llm = create_chat_qwen(temperature=0)
        chain = DIAGNOSIS_PROMPT | llm.with_structured_output(StructuredDiagnosis)
        structured: StructuredDiagnosis = await chain.ainvoke(
            {
                "task": task,
                "evidence_block": _evidence_block(evidence),
                "facts_block": _facts_block(facts),
                "draft_report": draft[:4000],
            }
        )
        diagnosis = structured.model_dump()
    except Exception as e:  # LLM 失败也要能出安全报告
        logger.error(f"结构化诊断生成失败: {e}")
        diagnosis = {
            "root_cause": "结构化诊断生成失败",
            "claims": [],
            "recommendations": [],
            "status": "safe_report",
        }

    verification_result = verify(diagnosis, index.keys())
    verification = verification_result.to_dict()

    # ---------- 通过：输出正式报告 ----------
    if verification_result.strict_pass:
        diagnosis["status"] = "verified"
        return {
            "diagnosis": diagnosis,
            "verification": verification,
            "response": _render_report(draft, diagnosis, verification, "verified"),
        }

    # ---------- 不通过且还能补证：回到 Executor 补一轮 ----------
    if repair_rounds < config.diagnosis_max_repair_rounds:
        hints = verification_result.missing_hints[:3] or ["补充可支撑结论的原始证据"]
        repair_step = "补充证据以满足诊断结论校验：" + "；".join(h[:100] for h in hints)
        logger.warning(f"证据链校验未通过，触发补证一轮：{repair_step}")
        return {
            "diagnosis": diagnosis,
            "verification": verification,
            "plan": [repair_step],
            "past_steps": [("证据补采", f"校验缺口：{hints}")],
            "response": "",  # 清空草稿，回到执行流程
            "repair_rounds": repair_rounds + 1,
        }

    # ---------- 补证后仍不通过：降级 ----------
    status = "hypothesis" if diagnosis.get("claims") else "safe_report"
    diagnosis["status"] = status
    logger.warning(f"补证后仍未通过证据校验，降级为 {status}")
    return {
        "diagnosis": diagnosis,
        "verification": verification,
        "response": _render_report(draft, diagnosis, verification, status),
    }
