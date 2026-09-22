"""诊断正确率评测：LLM-as-Judge 对照 Ground Truth 打分

指标定义：
- 根因正确率(RCA)   ：诊断根因是否命中真值要点（LLM 判定）
- 关键证据覆盖      ：是否引用了真值中列出的关键证据（LLM 判定）
- 建议可用性        ：处置建议是否包含关键动作（LLM 判定）
- 过度断言率        ：在"应降级"场景（证据冲突/工具失败/无证据）仍给出确定性根因的比例
- 关键词命中率      ：规则兜底指标（真值关键词是否出现在根因+结论文本中）

用法：
    python evals/eval_diagnosis.py --limit 12 --concurrency 3 --label diag
    python evals/eval_diagnosis.py --dataset adversarial --label diag_adv
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
import time
from datetime import datetime
from pathlib import Path
from statistics import mean
from typing import Any, Dict, List

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from pydantic import BaseModel, Field  # noqa: E402

from app.core.llm_client import create_chat_qwen  # noqa: E402
from evals.dataset import build_cases  # noqa: E402
from evals.ground_truth import get_ground_truth  # noqa: E402
from evals.metrics import RunMetricsCollector, build_langfuse_handler  # noqa: E402
from evals.runner import run_case  # noqa: E402
from evals.fixtures import patch_tools  # noqa: E402
from app.core.reliability import tool_result_cache  # noqa: E402

REPORT_DIR = REPO_ROOT / "reports"


class JudgeVerdict(BaseModel):
    """LLM 裁判结论"""

    root_cause_correct: bool = Field(description="诊断根因是否与真值一致（含义相符即可，不要求字面相同）")
    evidence_covered: bool = Field(description="是否引用了真值中的关键证据")
    suggestion_usable: bool = Field(description="处置建议是否包含真值中的关键动作")
    overclaim: bool = Field(description="在证据不足/证据冲突场景下，是否仍给出确定性根因（过度断言）")
    reason: str = Field(default="", description="一句话理由")


JUDGE_PROMPT = """你是运维诊断质量评审专家。请对照【标准答案】评审【Agent 诊断结果】。

评判原则：
1. 根因是否**含义相符**（不要求字面相同），若 Agent 给出了与真值不同的根因，或方向明显错误，判 false
2. 关键证据：Agent 的结论中是否引用了真值列出的关键证据（允许表述差异）
3. 建议可用性：处置建议是否包含真值中的关键动作
4. 过度断言：如果真值标注"应降级"，而 Agent 仍给出确定性根因（没有说明证据不足/冲突），判 overclaim=true；否则 false

【场景】{scenario}
【标准答案】{ground_truth}
【Agent 诊断结果】
- 状态：{status}
- 证据引用合规：{strict_pass}（覆盖率 {coverage}）
- 根因：{root_cause}
- 结论：{claims}
- 处置建议：{suggestions}

请输出 JSON。"""


def _extract_json(text: str) -> dict | None:
    """从模型输出中容错提取 JSON"""
    import re

    text = (text or "").strip()
    if text.startswith("```"):
        text = re.sub(r"^```[a-zA-Z]*\s*", "", text)
        text = re.sub(r"```\s*$", "", text)
    try:
        return json.loads(text)
    except Exception:
        m = re.search(r"\{.*\}", text, re.S)
        if m:
            try:
                return json.loads(m.group(0))
            except Exception:
                return None
        return None


def _rule_fallback(case: Dict[str, Any], result: Dict[str, Any], gt: Dict[str, Any]) -> Dict[str, Any]:
    """裁判不可用时的规则兜底，保证指标不因模型异常而缺失"""
    rc_text = f"{result.get('root_cause', '')} {result.get('claims_text', '')}".lower()
    sug_text = str(result.get("suggestions", "")).lower()
    rc_kws = [k.lower() for k in gt.get("root_cause_contains", [])]
    act_kws = [k.lower() for k in gt.get("key_actions", [])]
    degrade = bool(gt.get("expect_no_firm_root_cause")) or not case.get("expect", {}).get("verified")

    hedge_words = ["证据不足", "不一致", "冲突", "无法确认", "假设", "需人工", "hypothesis", "safe"]
    hedged = any(w.lower() in rc_text for w in hedge_words)

    return {
        "root_cause_correct": any(k in rc_text for k in rc_kws) if rc_kws else False,
        "evidence_covered": bool(result.get("strict_pass")),
        "suggestion_usable": any(k in sug_text for k in act_kws) if act_kws else False,
        "overclaim": bool(degrade and not hedged),
        "reason": "rule_fallback（裁判不可用，使用规则判定）",
    }


async def judge_case(case: Dict[str, Any], result: Dict[str, Any]) -> Dict[str, Any]:
    """用 LLM 裁判对单个用例打分；失败时回退规则判定"""
    gt = get_ground_truth(case["scenario"])
    prompt = JUDGE_PROMPT.format(
        scenario=case["scenario"],
        ground_truth=json.dumps(gt, ensure_ascii=False),
        status=result.get("status", ""),
        strict_pass=result.get("strict_pass"),
        coverage=result.get("coverage"),
        root_cause=result.get("root_cause", ""),
        claims=result.get("claims_text", ""),
        suggestions=result.get("suggestions", "（未提取到建议）"),
    ) + '\n\n只输出 JSON，不要多余文字，例如：{"root_cause_correct": true, "evidence_covered": true, "suggestion_usable": false, "overclaim": false, "reason": "..."}'

    out: Dict[str, Any] = {}
    try:
        resp = await create_chat_qwen(temperature=0).ainvoke(prompt)
        text = resp.content if hasattr(resp, "content") else str(resp)
        if isinstance(text, list):
            text = " ".join(str(b.get("text", "")) if isinstance(b, dict) else str(b) for b in text)
        data = _extract_json(str(text))
        if data:
            out = {
                "root_cause_correct": bool(data.get("root_cause_correct")),
                "evidence_covered": bool(data.get("evidence_covered")),
                "suggestion_usable": bool(data.get("suggestion_usable")),
                "overclaim": bool(data.get("overclaim")),
                "reason": str(data.get("reason", ""))[:160],
            }
        else:
            out = {}
    except Exception as e:
        out = {}

    if not out:  # 裁判不可用 -> 规则兜底
        out = _rule_fallback(case, result, gt)

    out["id"] = case["id"]
    out["scenario"] = case["scenario"]
    out["expect_verified"] = bool(case.get("expect", {}).get("verified"))
    kws = [k.lower() for k in gt.get("root_cause_contains", [])]
    text_all = f"{result.get('root_cause', '')} {result.get('claims_text', '')}".lower()
    out["keyword_hit"] = any(k in text_all for k in kws) if kws else None
    out["tokens"] = result.get("tokens")
    return out


async def main() -> int:
    parser = argparse.ArgumentParser(description="诊断正确率评测（LLM-as-Judge）")
    parser.add_argument("--dataset", choices=["main", "adversarial"], default="main")
    parser.add_argument("--limit", type=int, default=12)
    parser.add_argument("--concurrency", type=int, default=3)
    parser.add_argument("--label", type=str, default="diag")
    parser.add_argument("--per-scenario", type=int, default=0, help="每个场景取样条数（0=不限制）")
    args = parser.parse_args()

    if args.dataset == "adversarial":
        from evals.dataset_adversarial import build_adversarial_cases

        cases = build_adversarial_cases()
    else:
        cases = build_cases()
    if args.per_scenario:
        from collections import defaultdict

        bucket = defaultdict(list)
        for c_ in cases:
            bucket[c_["scenario"]].append(c_)
        cases = [c_ for items in bucket.values() for c_ in items[: args.per_scenario]]
    if args.limit:
        cases = cases[: args.limit]

    patch_tools()
    tool_result_cache.clear()
    langfuse = build_langfuse_handler()
    sem = asyncio.Semaphore(max(1, args.concurrency))

    print("=" * 78)
    print(f"诊断正确率评测：{len(cases)} 个用例（{args.dataset}），并发 {args.concurrency}")
    print("=" * 78)

    started = time.perf_counter()
    results = await asyncio.gather(*(run_case(c, sem, langfuse) for c in cases))
    verdicts = []
    for case, res in zip(cases, results):
        v = await judge_case(case, res)
        verdicts.append(v)
        mark = {True: "✅", False: "❌", None: "—"}[v["root_cause_correct"]]
        print(f"  [{mark}] {v['id']:<22} RCA={v['root_cause_correct']} 证据={v['evidence_covered']} "
              f"建议={v['suggestion_usable']} 过度断言={v['overclaim']}")
    elapsed = time.perf_counter() - started

    def rate(key: str) -> float:
        vals = [v[key] for v in verdicts if v.get(key) is not None]
        return round(sum(1 for x in vals if x) / len(vals), 4) if vals else 0.0

    degrade_cases = [v for v in verdicts if not v["expect_verified"]]
    overclaim_rate = (
        round(sum(1 for v in degrade_cases if v["overclaim"]) / len(degrade_cases), 4) if degrade_cases else 0.0
    )
    kw_vals = [v["keyword_hit"] for v in verdicts if v.get("keyword_hit") is not None]
    summary = {
        "cases": len(verdicts),
        "rca_accuracy": rate("root_cause_correct"),
        "evidence_coverage_rate": rate("evidence_covered"),
        "suggestion_usability_rate": rate("suggestion_usable"),
        "overclaim_rate": overclaim_rate,
        "keyword_hit_rate": round(sum(1 for x in kw_vals if x) / len(kw_vals), 4) if kw_vals else 0.0,
        "avg_tokens": round(mean([v["tokens"] for v in verdicts if v.get("tokens")]), 1) if any(v.get("tokens") for v in verdicts) else 0,
        "elapsed_s": round(elapsed, 1),
    }

    print("\n" + "=" * 78)
    print(f"根因正确率(RCA)     : {summary['rca_accuracy'] * 100:.2f}%")
    print(f"关键证据覆盖率      : {summary['evidence_coverage_rate'] * 100:.2f}%")
    print(f"建议可用率          : {summary['suggestion_usability_rate'] * 100:.2f}%")
    print(f"关键词命中率(规则)  : {summary['keyword_hit_rate'] * 100:.2f}%")
    print(f"过度断言率(应降级场景): {summary['overclaim_rate'] * 100:.2f}%  ({len(degrade_cases)} 例)")
    print(f"平均 Token / 耗时   : {summary['avg_tokens']} / {summary['elapsed_s']}s")
    print("=" * 78)

    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    payload = {"generated_at": stamp, "dataset": args.dataset, "summary": summary, "verdicts": verdicts}
    (REPORT_DIR / f"eval_diagnosis_{args.label}_{stamp}.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    lines = [
        f"# 诊断正确率评测报告（{args.label} · {stamp}）",
        "",
        f"- 用例数：{summary['cases']}（数据集 {args.dataset}）",
        f"- **根因正确率(RCA)：{summary['rca_accuracy'] * 100:.2f}%**",
        f"- 关键证据覆盖率：{summary['evidence_coverage_rate'] * 100:.2f}%",
        f"- 建议可用率：{summary['suggestion_usability_rate'] * 100:.2f}%",
        f"- 关键词命中率（规则兜底）：{summary['keyword_hit_rate'] * 100:.2f}%",
        f"- **过度断言率（应降级场景）：{summary['overclaim_rate'] * 100:.2f}%**（{len(degrade_cases)} 例）",
        f"- 平均 Token：{summary['avg_tokens']}",
        "",
        "| 用例 | 场景 | RCA | 证据覆盖 | 建议可用 | 过度断言 | 理由 |",
        "|---|---|---|---|---|---|---|",
    ]
    for v in verdicts:
        lines.append(
            f"| {v['id']} | {v['scenario']} | {v['root_cause_correct']} | {v['evidence_covered']} | "
            f"{v['suggestion_usable']} | {v['overclaim']} | {str(v['reason'])[:80]} |"
        )
    (REPORT_DIR / f"eval_diagnosis_{args.label}_{stamp}.md").write_text("\n".join(lines), encoding="utf-8")
    print(f"\n报告已保存: reports/eval_diagnosis_{args.label}_{stamp}.md")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
