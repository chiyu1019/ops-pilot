"""混合检索对比评测：纯向量 vs 纯 BM25 vs 混合(RRF) vs 混合(归一化)

用途：量化混合检索带来的召回提升，为答辩提供可复现数据。

用法：
    python scripts/eval_hybrid.py                     # 默认 top_k=3
    python scripts/eval_hybrid.py --top-k 5
    python scripts/eval_hybrid.py --recall-k 10       # 融合前每路候选数量
    python scripts/eval_hybrid.py --min-accuracy 0.9  # 未达标则退出码非 0

前提：
    - Milvus 已启动且知识库文档已索引（向量索引）
    - Elasticsearch 已启动且同一批文档已索引（BM25 索引）
    - DASHSCOPE_API_KEY 有效（向量化查询）
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path
from typing import Any, Callable, Dict, List

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from app.config import config
from app.services.bm25_search_service import bm25_search_service
from app.services.hybrid_search_service import hybrid_search_service
from app.services.vector_store_manager import vector_store_manager

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_QUESTIONS = REPO_ROOT / "tests" / "data" / "rag_eval_questions.json"


def load_questions(path: Path) -> List[Dict[str, Any]]:
    raw = json.loads(path.read_text(encoding="utf-8"))
    questions = raw["questions"] if isinstance(raw, dict) else raw
    if not questions:
        raise ValueError(f"评测集为空: {path}")
    return questions


def _files_from_docs(docs) -> List[str]:
    return [d.metadata.get("_file_name", "") for d in docs]


def _hit(question: Dict[str, Any], docs) -> bool:
    expected = question.get("expected_files", [])
    return any(
        any(exp in name for exp in expected) for name in _files_from_docs(docs)
    )


# ---------- 四种检索模式 ----------
def search_vector(query: str, k: int):
    return vector_store_manager.similarity_search(query, k=k)


def search_bm25(query: str, k: int):
    from langchain_core.documents import Document

    return [
        Document(page_content=hit["content"], metadata=dict(hit["metadata"]))
        for hit in bm25_search_service.search(query, k=k)
    ]


def search_hybrid_rrf(query: str, k: int):
    config.hybrid_fusion = "rrf"
    return hybrid_search_service.search(query, k=k)


def search_hybrid_normalize(query: str, k: int):
    config.hybrid_fusion = "normalize"
    return hybrid_search_service.search(query, k=k)


MODES: List[tuple] = [
    ("vector", search_vector),
    ("bm25", search_bm25),
    ("hybrid-rrf", search_hybrid_rrf),
    ("hybrid-normalize", search_hybrid_normalize),
]


def evaluate(questions: List[Dict[str, Any]], search_fn: Callable, top_k: int) -> Dict[str, Any]:
    hits = 0
    latencies: List[float] = []
    failures: List[Dict[str, Any]] = []

    for q in questions:
        t0 = time.perf_counter()
        try:
            docs = search_fn(q["question"], top_k)
            error = None
        except Exception as e:  # 单条失败不影响整体评测
            docs, error = [], str(e)
        latencies.append(time.perf_counter() - t0)

        ok = _hit(q, docs)
        hits += int(ok)
        if not ok:
            failures.append(
                {
                    "question": q["question"],
                    "expected": q.get("expected_files", []),
                    "retrieved": _files_from_docs(docs),
                    "error": error,
                }
            )

    n = len(questions)
    return {
        "total": n,
        "hits": hits,
        "accuracy": hits / n if n else 0.0,
        "avg_ms": round(sum(latencies) / n * 1000, 1) if n else 0.0,
        "failures": failures,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="混合检索对比评测")
    parser.add_argument("--questions", type=Path, default=DEFAULT_QUESTIONS)
    parser.add_argument("--top-k", type=int, default=config.rag_top_k)
    parser.add_argument("--recall-k", type=int, default=config.hybrid_recall_k)
    parser.add_argument("--min-accuracy", type=float, default=0.0)
    args = parser.parse_args()

    config.hybrid_recall_k = args.recall_k
    questions = load_questions(args.questions)

    print("=" * 78)
    print(f"混合检索对比评测  评测集={args.questions.name}  题数={len(questions)}")
    print(f"TopK={args.top_k}  每路召回={args.recall_k}  RRF_k={config.hybrid_rrf_k}  alpha={config.hybrid_alpha}")
    print("=" * 78)

    # 连通性预检
    try:
        vector_store_manager.similarity_search("连通性检查", k=1)
        vector_ok = True
    except Exception as e:
        vector_ok = False
        print(f"[警告] 向量库不可用: {e}")
    if not bm25_search_service.health():
        print("[警告] Elasticsearch 不可用，BM25/混合模式将失败")

    results: Dict[str, Dict[str, Any]] = {}
    print(f"\n{'模式':<18}{'命中':>8}{'准确率':>10}{'平均耗时(ms)':>14}")
    print("-" * 78)
    for name, fn in MODES:
        r = evaluate(questions, fn, args.top_k)
        results[name] = r
        print(f"{name:<18}{r['hits']:>5}/{r['total']:<3}{r['accuracy'] * 100:>9.1f}%{r['avg_ms']:>13.1f}")

    # 提升对比
    if vector_ok and "vector" in results:
        base = results["vector"]["accuracy"]
        print("\n相对纯向量检索的提升：")
        for name in ("bm25", "hybrid-rrf", "hybrid-normalize"):
            if name in results:
                delta = (results[name]["accuracy"] - base) * 100
                print(f"  {name:<18}{delta:+.1f} 个百分点")

    # 失败样例（以 hybrid-rrf 为主）
    for name in ("hybrid-rrf", "vector"):
        if name in results and results[name]["failures"]:
            print(f"\n[{name}] 未命中样例：")
            for f in results[name]["failures"][:5]:
                print(f"  - {f['question']}")
                print(f"    期望: {', '.join(f['expected'])}  实际: {', '.join(f['retrieved']) or '无'}")
                if f["error"]:
                    print(f"    错误: {f['error']}")
            break

    best = max(results.values(), key=lambda r: (r["accuracy"], -r["avg_ms"]))
    print(
        f"\n结论：最佳模式准确率 {best['accuracy'] * 100:.1f}%"
        f"（{best['hits']}/{best['total']}），平均耗时 {best['avg_ms']}ms"
    )

    if args.min_accuracy and results["hybrid-rrf"]["accuracy"] < args.min_accuracy:
        print(f"hybrid-rrf 准确率低于阈值 {args.min_accuracy:.2f}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
