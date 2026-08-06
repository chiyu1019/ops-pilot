"""RAG 检索准确率评测脚本

用于量化"知识检索准确率"，为简历中的指标提供可复现的证据。

前提：
- Milvus 已启动（docker compose -f vector-database.yml up -d）
- 知识库文档已上传（start-windows.bat 或 make upload）

用法：
    python scripts/eval_rag.py                                  # 默认评测集 + top_k=3
    python scripts/eval_rag.py --top-k 5                        # 调整 TopK
    python scripts/eval_rag.py --sweep-topk 1,2,3,5,8           # 扫描 TopK 并输出对比表
    python scripts/eval_rag.py --min-accuracy 0.85              # 低于阈值时以非零码退出

输出：
    每道题的检索命中情况 + 汇总准确率（命中 = 正确答案所在文档出现在 top-k 结果中）
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path
from typing import Any

from app.config import config
from app.services.vector_store_manager import vector_store_manager

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_QUESTIONS = REPO_ROOT / "tests" / "data" / "rag_eval_questions.json"


def load_questions(path: Path) -> list[dict[str, Any]]:
    raw = json.loads(path.read_text(encoding="utf-8"))
    questions = raw["questions"] if isinstance(raw, dict) else raw
    if not questions:
        raise ValueError(f"评测集为空: {path}")
    return questions


def hit(question: dict[str, Any], docs: list) -> tuple[bool, list[str]]:
    """判断 top-k 结果中是否出现预期文档。"""
    expected = question.get("expected_files", [])
    retrieved = [d.metadata.get("_file_name", "") for d in docs]
    ok = any(any(exp in name for exp in expected) for name in retrieved)
    return ok, retrieved


def evaluate(questions: list[dict[str, Any]], top_k: int) -> dict[str, Any]:
    hits = 0
    latencies: list[float] = []
    details: list[dict[str, Any]] = []

    for q in questions:
        t0 = time.perf_counter()
        docs = vector_store_manager.similarity_search(q["question"], k=top_k)
        latencies.append(time.perf_counter() - t0)

        ok, retrieved = hit(q, docs)
        hits += int(ok)
        details.append(
            {
                "question": q["question"],
                "expected_files": q.get("expected_files", []),
                "retrieved_files": retrieved,
                "hit": ok,
            }
        )

    n = len(questions)
    avg_latency = sum(latencies) / n if n else 0.0
    return {
        "total": n,
        "hits": hits,
        "accuracy": hits / n if n else 0.0,
        "avg_latency_ms": round(avg_latency * 1000, 2),
        "top_k": top_k,
        "details": details,
    }


def print_report(report: dict[str, Any]) -> None:
    print("=" * 72)
    print(f"RAG 检索评测报告  top_k={report['top_k']}")
    print("=" * 72)
    for d in report["details"]:
        mark = "✔" if d["hit"] else "✘"
        print(f"[{mark}] {d['question']}")
        print(f"      期望: {', '.join(d['expected_files']) or '无'}")
        print(f"      召回: {', '.join(d['retrieved_files']) or '无'}")
    print("-" * 72)
    print(
        f"准确率: {report['hits']}/{report['total']} = "
        f"{report['accuracy'] * 100:.1f}%   平均检索耗时: {report['avg_latency_ms']}ms"
    )
    print("=" * 72)


def main() -> int:
    parser = argparse.ArgumentParser(description="RAG 检索准确率评测")
    parser.add_argument("--questions", type=Path, default=DEFAULT_QUESTIONS)
    parser.add_argument("--top-k", type=int, default=config.rag_top_k)
    parser.add_argument("--sweep-topk", type=str, default="", help="逗号分隔的 TopK 列表")
    parser.add_argument("--min-accuracy", type=float, default=0.0)
    args = parser.parse_args()

    questions = load_questions(args.questions)
    print(f"评测集: {args.questions}（{len(questions)} 题）")

    if args.sweep_topk:
        topk_values = [int(x) for x in args.sweep_topk.split(",") if x.strip()]
        print(f"\nTopK 参数扫描: {topk_values}\n")
        print(f"{'top_k':>6} {'hits':>5} {'accuracy':>10} {'avg_ms':>10}")
        print("-" * 36)
        for k in topk_values:
            report = evaluate(questions, k)
            print(
                f"{k:>6} {report['hits']:>5} {report['accuracy'] * 100:>9.1f}% "
                f"{report['avg_latency_ms']:>10.2f}"
            )
            if k == args.top_k:
                print_report(report)
        return 0

    report = evaluate(questions, args.top_k)
    print_report(report)

    if args.min_accuracy and report["accuracy"] < args.min_accuracy:
        print(f"准确率低于阈值 {args.min_accuracy:.2f}，评测未通过")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
