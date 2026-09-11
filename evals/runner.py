"""34 Case 可控评测 Runner

用法：
    python evals/runner.py                    # 全部 34 个用例
    python evals/runner.py --limit 4           # 只跑前 4 个（快速验证）
    python evals/runner.py --concurrency 3     # 并发度

输出：
    - 控制台汇总（严格校验通过率 / 证据覆盖率 / Token / 耗时）
    - reports/eval_cases_<时间戳>.json 与 .md
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
from typing import Any, Dict, List, Optional

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from app.config import config  # noqa: E402
from app.services.aiops_service import aiops_service  # noqa: E402
from evals.dataset import build_cases, task_text  # noqa: E402
from evals.fixtures import FixtureRuntime, patch_tools  # noqa: E402
from app.core.reliability import tool_result_cache  # noqa: E402
from evals.metrics import RunMetricsCollector, build_langfuse_handler  # noqa: E402

REPORT_DIR = REPO_ROOT / "reports"


async def run_case(case: Dict[str, Any], sem: asyncio.Semaphore, langfuse: Any) -> Dict[str, Any]:
    """在隔离的 fixture 场景下执行一次完整诊断"""
    async with sem:
        runtime = FixtureRuntime()
        runtime.activate(case["scenario"], case["fixture"])
        collector = RunMetricsCollector()
        callbacks: List[Any] = [collector] + ([langfuse] if langfuse else [])

        diag_event: Optional[Dict[str, Any]] = None
        error: Optional[str] = None
        node_events = 0
        started = time.perf_counter()

        try:
            async for ev in aiops_service.execute(
                task_text(case), session_id=f"eval-{case['id']}", callbacks=callbacks
            ):
                node_events += 1
                if ev.get("type") == "diagnosis":
                    diag_event = ev
                elif ev.get("type") == "error":
                    error = str(ev.get("message"))[:200]
        except Exception as e:  # noqa: BLE001
            error = f"{type(e).__name__}: {str(e)[:200]}"
        finally:
            runtime.deactivate()

        duration = time.perf_counter() - started
        verification = (diag_event or {}).get("verification") or {}
        diagnosis = (diag_event or {}).get("diagnosis") or {}
        status = diagnosis.get("status") or ("error" if error else "unknown")

        expect_verified = bool(case.get("expect", {}).get("verified"))
        strict_pass = bool(verification.get("strict_pass"))
        metrics = collector.snapshot()

        # 根因正确性：期望关键词是否出现在根因 + 结论中（大小写不敏感）
        expect_keywords = [str(k).lower() for k in (case.get("expect", {}).get("keywords") or [])]
        root_cause = str(diagnosis.get("root_cause", "") or "")
        claims_text = " ".join(str(cl.get("claim", "")) for cl in (diagnosis.get("claims") or []))
        answer_text = f"{root_cause} {claims_text}".lower()
        matched = [k for k in expect_keywords if k in answer_text]
        keywords_hit = bool(matched) if expect_keywords else True
        correctness = (len(matched) / len(expect_keywords)) if expect_keywords else 1.0

        return {
            "id": case["id"],
            "scenario": case["scenario"],
            "expect_verified": expect_verified,
            "strict_pass": strict_pass,
            "status": status,
            "coverage": float(verification.get("coverage", 0.0)),
            "claims": int(verification.get("total_claims", 0)),
            "supported_claims": int(verification.get("supported_claims", 0)),
            "invalid_evidence_ids": verification.get("invalid_evidence_ids", []),
            "matches_expectation": strict_pass == expect_verified,
            "correctness": round(correctness, 4),
            "keywords_matched": matched,
            "keywords_expected": expect_keywords,
            "root_cause": root_cause[:400],
            "claims_text": claims_text[:600],
            "tokens": metrics["total_tokens"],
            "prompt_tokens": metrics["prompt_tokens"],
            "completion_tokens": metrics["completion_tokens"],
            "llm_calls": metrics["llm_calls"],
            "tool_calls": metrics["tool_calls"],
            "node_count": metrics["node_count"],
            "duration_s": round(duration, 2),
            "error": error,
        }


def summarize(results: List[Dict[str, Any]]) -> Dict[str, Any]:
    n = len(results)
    strict = sum(1 for r in results if r["strict_pass"])
    with_claims = [r for r in results if r["claims"] > 0]
    degraded = [r for r in results if not r["expect_verified"]]
    degraded_ok = sum(1 for r in degraded if r["status"] in ("hypothesis", "safe_report"))
    tokens = [r["tokens"] for r in results if r["tokens"] > 0]

    return {
        "cases": n,
        "citation_compliance_rate": round(sum(1 for r in results if r["strict_pass"]) / n, 4) if n else 0.0,
        "root_cause_correctness_rate": round(sum(1 for r in results if r.get("correctness", 0) >= 0.5) / n, 4) if n else 0.0,
        "avg_keyword_recall": round(mean([r.get("correctness", 1.0) for r in results]), 4) if n else 0.0,
        "strict_pass_count": strict,
        "strict_pass_rate": round(strict / n, 4) if n else 0.0,
        "expectation_match_rate": round(sum(1 for r in results if r["matches_expectation"]) / n, 4) if n else 0.0,
        "evidence_coverage_all": round(mean([r["coverage"] for r in results]), 4) if n else 0.0,
        "evidence_coverage_with_claims": round(mean([r["coverage"] for r in with_claims]), 4) if with_claims else 0.0,
        "degradation_cases": len(degraded),
        "degradation_correct_rate": round(degraded_ok / len(degraded), 4) if degraded else 0.0,
        "avg_tokens": round(mean(tokens), 1) if tokens else 0.0,
        "total_tokens": sum(tokens),
        "avg_llm_calls": round(mean([r["llm_calls"] for r in results]), 2) if n else 0.0,
        "avg_tool_calls": round(mean([r["tool_calls"] for r in results]), 2) if n else 0.0,
        "avg_node_count": round(mean([r["node_count"] for r in results]), 2) if n else 0.0,
        "avg_duration_s": round(mean([r["duration_s"] for r in results]), 2) if n else 0.0,
        "errors": sum(1 for r in results if r["error"]),
    }


def write_report(results: List[Dict[str, Any]], summary: Dict[str, Any], label: str) -> Path:
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    payload = {"generated_at": stamp, "label": label, "summary": summary, "results": results}
    json_path = REPORT_DIR / f"eval_cases_{label}_{stamp}.json"
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    lines = [
        f"# 可控场景评测报告（{label} · {stamp}）",
        "",
        f"- 用例数：**{summary['cases']}**",
        f"- 严格证据校验通过率：**{summary['strict_pass_rate'] * 100:.2f}%**（{summary['strict_pass_count']}/{summary['cases']}）",
        f"- 证据覆盖率（全部用例）：**{summary['evidence_coverage_all'] * 100:.2f}%**",
        f"- 证据覆盖率（有结论的用例）：**{summary['evidence_coverage_with_claims'] * 100:.2f}%**",
        f"- 证据不足场景正确降级率：{summary['degradation_correct_rate'] * 100:.2f}%（{summary['degradation_cases']} 例）",
        f"- 平均 Token：{summary['avg_tokens']}（总 {summary['total_tokens']}）",
        f"- 平均 LLM 调用：{summary['avg_llm_calls']}　平均工具调用：{summary['avg_tool_calls']}　平均节点数：{summary['avg_node_count']}",
        f"- 平均耗时：{summary['avg_duration_s']}s",
        "",
        "| 用例 | 场景 | 期望校验 | 实际通过 | 状态 | 覆盖率 | Token | 耗时(s) |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for r in results:
        lines.append(
            f"| {r['id']} | {r['scenario']} | {'通过' if r['expect_verified'] else '降级'} | "
            f"{'✅' if r['strict_pass'] else '❌'} | {r['status']} | {r['coverage'] * 100:.1f}% | "
            f"{r['tokens']} | {r['duration_s']} |"
        )
    md_path = REPORT_DIR / f"eval_cases_{label}_{stamp}.md"
    md_path.write_text("\n".join(lines), encoding="utf-8")
    return md_path


async def main() -> int:
    parser = argparse.ArgumentParser(description="34 Case 可控场景评测")
    parser.add_argument("--limit", type=int, default=0, help="只跑前 N 个用例（0 = 全部）")
    parser.add_argument("--concurrency", type=int, default=3)
    parser.add_argument("--label", type=str, default="optimized")
    parser.add_argument("--only", type=str, default="", help="只跑指定用例 ID（逗号分隔）")
    parser.add_argument(
        "--dataset",
        type=str,
        default="main",
        choices=["main", "adversarial"],
        help="main=34 个常规场景；adversarial=10 个对抗场景（含期望降级）",
    )
    parser.add_argument(
        "--mode",
        type=str,
        default="optimized",
        choices=["baseline", "optimized"],
        help="baseline=关闭工具缓存与上下文压缩；optimized=开启（默认）",
    )
    args = parser.parse_args()

    # 成本治理开关：用于 baseline / optimized 对比
    if args.mode == "baseline":
        config.reliability_tool_cache_enabled = False
        config.reliability_context_compress_enabled = False
        config.reliability_token_budget = 0
        tool_result_cache.clear()
    else:
        config.reliability_tool_cache_enabled = True
        config.reliability_context_compress_enabled = True
        config.reliability_token_budget = config.reliability_token_budget or 60000
        tool_result_cache.clear()

    if args.dataset == "adversarial":
        from evals.dataset_adversarial import build_adversarial_cases

        cases = build_adversarial_cases()
    else:
        cases = build_cases()
    if args.only:
        wanted = {x.strip() for x in args.only.split(",") if x.strip()}
        cases = [c for c in cases if c["id"] in wanted]
    if args.limit:
        cases = cases[: args.limit]

    patch_tools()
    langfuse = build_langfuse_handler()
    sem = asyncio.Semaphore(max(1, args.concurrency))

    print("=" * 78)
    print(f"可控场景评测：{len(cases)} 个用例，并发 {args.concurrency}，标签 {args.label}")
    print(f"模型={config.rag_model}  证据校验={config.diagnosis_verify_enabled}  补证轮次上限={config.diagnosis_max_repair_rounds}")
    print("=" * 78)

    started = time.perf_counter()
    results = await asyncio.gather(*(run_case(c, sem, langfuse) for c in cases))
    results = list(results)

    # 失败用例重试一次（LLM/工具偶发错误）
    retry_targets = [c for c, r in zip(cases, results) if r["error"] and not r["strict_pass"]]
    if retry_targets:
        print(f"\n[retry] {len(retry_targets)} 个用例首次失败，重试一次")
        retried = await asyncio.gather(*(run_case(c, sem, langfuse) for c in retry_targets))
        retried_by_id = {r["id"]: r for r in retried}
        results = [retried_by_id.get(r["id"], r) if r["error"] and not r["strict_pass"] else r for r in results]

    elapsed = time.perf_counter() - started

    results = list(results)
    summary = summarize(results)
    md_path = write_report(results, summary, args.label)

    print(f"\n完成 {len(results)} 个用例，总耗时 {elapsed:.1f}s\n")
    print(f"证据引用合规率     : {summary['citation_compliance_rate'] * 100:.2f}%  ({summary['strict_pass_count']}/{summary['cases']})")
    print(f"根因正确率         : {summary['root_cause_correctness_rate'] * 100:.2f}%  (关键词命中)")
    print(f"平均关键词召回     : {summary['avg_keyword_recall'] * 100:.2f}%")
    print(f"与期望一致率       : {summary['expectation_match_rate'] * 100:.2f}%")
    print(f"证据覆盖率(全部)   : {summary['evidence_coverage_all'] * 100:.2f}%")
    print(f"证据覆盖率(有结论) : {summary['evidence_coverage_with_claims'] * 100:.2f}%")
    print(f"证据不足降级正确率 : {summary['degradation_correct_rate'] * 100:.2f}%  ({summary['degradation_cases']} 例)")
    print(f"平均 Token         : {summary['avg_tokens']}  (总 {summary['total_tokens']})")
    print(f"平均 LLM/工具/节点 : {summary['avg_llm_calls']} / {summary['avg_tool_calls']} / {summary['avg_node_count']}")
    print(f"平均耗时           : {summary['avg_duration_s']}s")
    print(f"失败用例           : {summary['errors']}")
    print(f"\n报告：{md_path}")

    failed = [r for r in results if not r["matches_expectation"]]
    if failed:
        print("\n与期望不一致的用例：")
        for r in failed[:10]:
            print(f"  - {r['id']}: 期望{'通过' if r['expect_verified'] else '降级'} 实际 {r['status']}"
                  f"（覆盖率 {r['coverage'] * 100:.1f}%, claims={r['claims']}）{('错误: ' + r['error']) if r['error'] else ''}")

    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
