"""RAG Recall@K 评测：向量 / BM25 / 混合检索三模式对比

指标口径：
- Recall@K = 期望文档出现在 Top-K 结果中的题目比例（文档级召回）
- 语义题 / 关键词题分别统计，便于说明混合检索的价值

用法：
    python scripts/eval_recall.py                          # 默认 K 上限 8
    python scripts/eval_recall.py --modes vector,hybrid-rrf
    python scripts/eval_recall.py --save                   # 额外输出 JSON/Markdown 报告
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Dict, List

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from app.config import config
from app.services.bm25_search_service import bm25_search_service
from app.services.hybrid_search_service import hybrid_search_service
from app.services.vector_store_manager import vector_store_manager

REPO_ROOT = Path(__file__).resolve().parent.parent
GOLDEN_SET = REPO_ROOT / "tests" / "data" / "golden_set_45.json"
REPORT_DIR = REPO_ROOT / "reports"
RECALL_KS = (1, 3, 5, 8)


def load_questions(path: Path) -> List[Dict[str, Any]]:
    raw = json.loads(path.read_text(encoding="utf-8"))
    questions = raw["questions"] if isinstance(raw, dict) else raw
    if not questions:
        raise ValueError(f"评测集为空: {path}")
    return questions


def _files(docs) -> List[str]:
    return [d.metadata.get("_file_name", "") for d in docs]


def search_vector(query: str, k: int):
    return vector_store_manager.similarity_search(query, k=k)


def search_bm25(query: str, k: int):
    from langchain_core.documents import Document

    return [
        Document(page_content=h["content"], metadata=dict(h["metadata"]))
        for h in bm25_search_service.search(query, k=k)
    ]


def search_hybrid_rrf(query: str, k: int):
    config.hybrid_fusion = "rrf"
    return hybrid_search_service.search(query, k=k)


def search_hybrid_normalize(query: str, k: int):
    config.hybrid_fusion = "normalize"
    return hybrid_search_service.search(query, k=k)


MODES: Dict[str, Callable] = {
    "vector": search_vector,
    "bm25": search_bm25,
    "hybrid-rrf": search_hybrid_rrf,
    "hybrid-normalize": search_hybrid_normalize,
}


def evaluate(questions: List[Dict[str, Any]], fn: Callable, max_k: int) -> Dict[str, Any]:
    hits = {k: 0 for k in RECALL_KS if k <= max_k}
    latencies: List[float] = []
    details: List[Dict[str, Any]] = []
    per_category: Dict[str, Dict[str, int]] = {}

    for q in questions:
        t0 = time.perf_counter()
        try:
            docs = fn(q["question"], max_k)
            err = None
        except Exception as e:  # 单条失败不影响整体
            docs, err = [], str(e)
        latencies.append(time.perf_counter() - t0)

        names = _files(docs)
        expected = q.get("expected_files", [])
        category = q.get("category", "unknown")
        per_category.setdefault(category, {k: 0 for k in hits})
        per_category[category]["total"] = per_category[category].get("total", 0) + 1

        hit_at = {}
        for k in hits:
            ok = any(any(exp in n for exp in expected) for n in names[:k])
            hit_at[k] = ok
            if ok:
                hits[k] += 1
                per_category[category][k] += 1

        details.append(
            {
                "id": q.get("id", ""),
                "category": category,
                "question": q["question"],
                "expected": expected,
                "retrieved_top5": names[:5],
                "hit_at": hit_at,
                "error": err,
            }
        )

    n = len(questions)
    return {
        "total": n,
        "hits": hits,
        "recall": {k: (hits[k] / n if n else 0.0) for k in hits},
        "avg_ms": round(sum(latencies) / n * 1000, 2) if n else 0.0,
        "per_category": per_category,
        "details": details,
    }


def print_table(results: Dict[str, Dict[str, Any]], max_k: int) -> None:
    header = f"{'模式':<17}" + "".join(f"{'Recall@' + str(k):>11}" for k in RECALL_KS if k <= max_k) + f"{'平均耗时':>12}"
    print(header)
    print("-" * len(header))
    for mode, r in results.items():
        row = f"{mode:<17}"
        for k in RECALL_KS:
            if k <= max_k:
                row += f"{r['recall'][k] * 100:>10.2f}%"
        row += f"{r['avg_ms']:>10.2f}ms"
        print(row)


def main() -> int:
    parser = argparse.ArgumentParser(description="RAG Recall@K 评测")
    parser.add_argument("--questions", type=Path, default=GOLDEN_SET)
    parser.add_argument("--max-k", type=int, default=8)
    parser.add_argument("--modes", type=str, default="vector,bm25,hybrid-rrf")
    parser.add_argument("--save", action="store_true", help="输出 JSON/Markdown 报告到 reports/")
    args = parser.parse_args()

    questions = load_questions(args.questions)
    modes = [m.strip() for m in args.modes.split(",") if m.strip() in MODES]

    print("=" * 78)
    print(f"RAG Recall@K 评测  |  评测集={args.questions.name}  题量={len(questions)}")
    print(f"融合方式={config.hybrid_fusion}  向量权重={config.hybrid_vector_weight}  RRF_k={config.hybrid_rrf_k}")
    print("=" * 78 + "\n")

    results: Dict[str, Dict[str, Any]] = {}
    for mode in modes:
        results[mode] = evaluate(questions, MODES[mode], args.max_k)

    print_table(results, args.max_k)

    # 分类明细（语义 / 关键词）
    print("\n按题目类型拆分（Recall@3 / Recall@5）：")
    for mode, r in results.items():
        parts = []
        for cat, counts in r["per_category"].items():
            total = counts.get("total", 0)
            if not total:
                continue
            parts.append(
                f"{cat}: R@3={counts.get(3, 0)}/{total}({counts.get(3, 0) / total * 100:.1f}%) "
                f"R@5={counts.get(5, 0)}/{total}({counts.get(5, 0) / total * 100:.1f}%)"
            )
        print(f"  {mode:<17} " + " | ".join(parts))

    # 未命中样例
    for mode, r in results.items():
        misses = [d for d in r["details"] if not d["hit_at"].get(3)]
        if misses:
            print(f"\n[{mode}] Recall@3 未命中 {len(misses)} 条：")
            for d in misses[:6]:
                print(f"  - [{d['id']}/{d['category']}] {d['question']}")
                print(f"      期望: {', '.join(d['expected'])}  实际 Top5: {', '.join(d['retrieved_top5']) or '无'}")

    if args.save:
        REPORT_DIR.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        payload = {
            "generated_at": stamp,
            "golden_set": args.questions.name,
            "total": len(questions),
            "max_k": args.max_k,
            "config": {
                "hybrid_fusion": config.hybrid_fusion,
                "hybrid_vector_weight": config.hybrid_vector_weight,
                "hybrid_rrf_k": config.hybrid_rrf_k,
                "hybrid_recall_k": config.hybrid_recall_k,
            },
            "results": {
                mode: {
                    "recall": r["recall"],
                    "avg_ms": r["avg_ms"],
                    "per_category": r["per_category"],
                }
                for mode, r in results.items()
            },
        }
        (REPORT_DIR / f"eval_recall_{stamp}.json").write_text(
            json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        lines = [
            f"# RAG Recall@K 评测报告（{stamp}）",
            "",
            f"- 评测集：`{args.questions.name}`，题量 **{len(questions)}**",
            f"- 融合方式：{config.hybrid_fusion}，向量权重 {config.hybrid_vector_weight}，RRF_k {config.hybrid_rrf_k}",
            "",
            "| 模式 | " + " | ".join(f"Recall@{k}" for k in RECALL_KS if k <= args.max_k) + " | 平均耗时 |",
            "|" + "---|" * (len([k for k in RECALL_KS if k <= args.max_k]) + 2),
        ]
        for mode, r in results.items():
            cells = " | ".join(f"{r['recall'][k] * 100:.2f}%" for k in RECALL_KS if k <= args.max_k)
            lines.append(f"| {mode} | {cells} | {r['avg_ms']}ms |")
        (REPORT_DIR / f"eval_recall_{stamp}.md").write_text("\n".join(lines), encoding="utf-8")
        print(f"\n报告已保存到 reports/eval_recall_{stamp}.json / .md")

    return 0


if __name__ == "__main__":
    sys.exit(main())
