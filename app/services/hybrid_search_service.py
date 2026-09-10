"""混合检索服务：向量检索 + BM25 关键词检索，融合排序

融合方式（config.hybrid_fusion）：
- rrf       ：倒数排名融合（Reciprocal Rank Fusion，推荐）
              score = Σ weight_i / (k + rank_i)
              优点：不需要跨检索器对齐分数尺度，对异常分数鲁棒
- normalize ：分数归一化加权融合
              向量距离转相似度 -> min-max 归一化 -> alpha * vector + (1-alpha) * bm25
              优点：可调权重，便于业务侧重某一路

对外接口：
- search(query, k)              返回融合后的 Document 列表
- search_with_details(query, k) 额外返回各路召回与融合明细（用于评测/调试）
"""

from __future__ import annotations

import hashlib
from typing import Any, Dict, List, Tuple

from langchain_core.documents import Document
from loguru import logger

from app.config import config
from app.services.bm25_search_service import bm25_search_service
from app.services.vector_store_manager import vector_store_manager

# 单路召回结果的统一结构
Hit = Dict[str, Any]


def doc_key(doc: Document) -> str:
    """跨检索器对齐文档的稳定键：来源 + 内容指纹"""
    meta = doc.metadata or {}
    raw = f"{meta.get('_source', '')}::{doc.page_content.strip()[:300]}"
    return hashlib.sha1(raw.encode("utf-8")).hexdigest()


def _to_doc(hit: Hit) -> Document:
    """把 BM25 命中转换为 LangChain Document"""
    return Document(page_content=hit["content"], metadata=dict(hit.get("metadata", {})))


def rrf_fuse(
    hit_lists: List[List[Hit]],
    rrf_k: int = 60,
    weights: List[float] | None = None,
) -> Dict[str, Dict[str, Any]]:
    """倒数排名融合（RRF）

    Args:
        hit_lists: 多路召回结果，每路内部已按相关性倒序排列
        rrf_k: RRF 常数（论文默认 60）
        weights: 每路权重，默认等权

    Returns:
        {doc_key: {"doc": Document, "score": float, "ranks": {来源: 排名}}}
    """
    if weights is None:
        weights = [1.0] * len(hit_lists)

    fused: Dict[str, Dict[str, Any]] = {}
    for path_idx, hits in enumerate(hit_lists):
        weight = weights[path_idx] if path_idx < len(weights) else 1.0
        for rank, hit in enumerate(hits, start=1):
            key = hit.get("key") or doc_key(_to_doc(hit))
            entry = fused.setdefault(
                key, {"doc": _to_doc(hit), "score": 0.0, "ranks": {}}
            )
            entry["score"] += weight / (rrf_k + rank)
            entry["ranks"][hit.get("source", f"path{path_idx}")] = rank
    return fused


def _min_max_normalize(scores: List[float]) -> List[float]:
    """min-max 归一化；所有分数相同时返回全 1（避免除零）"""
    if not scores:
        return []
    lo, hi = min(scores), max(scores)
    if hi - lo < 1e-12:
        return [1.0] * len(scores)
    return [(s - lo) / (hi - lo) for s in scores]


def normalize_fuse(
    vector_hits: List[Hit],
    bm25_hits: List[Hit],
    alpha: float = 0.5,
) -> Dict[str, Dict[str, Any]]:
    """分数归一化加权融合

    vector_hits 中的 score 需为"相似度"（越大越相关），
    bm25_hits 中的 score 为 BM25 原始分。
    """
    fused: Dict[str, Dict[str, Any]] = {}

    for source_name, hits, weight in (
        ("vector", vector_hits, alpha),
        ("bm25", bm25_hits, 1.0 - alpha),
    ):
        norm_scores = _min_max_normalize([float(h.get("score", 0.0)) for h in hits])
        for rank, (hit, norm) in enumerate(zip(hits, norm_scores), start=1):
            key = hit.get("key") or doc_key(_to_doc(hit))
            entry = fused.setdefault(
                key, {"doc": _to_doc(hit), "score": 0.0, "ranks": {}}
            )
            entry["score"] += weight * norm
            entry["ranks"][source_name] = rank
    return fused


class HybridSearchService:
    """向量 + BM25 混合检索"""

    def _vector_hits(self, query: str, k: int) -> List[Hit]:
        """向量召回：Milvus L2 距离 -> 相似度（1/(1+distance)）"""
        store = vector_store_manager.get_vector_store()
        pairs = store.similarity_search_with_score(query, k=k)
        hits: List[Hit] = []
        for doc, distance in pairs:
            hits.append(
                {
                    "key": doc_key(doc),
                    "doc": doc,
                    "content": doc.page_content,
                    "metadata": dict(doc.metadata or {}),
                    "score": 1.0 / (1.0 + float(distance)),
                    "source": "vector",
                }
            )
        return hits

    def _bm25_hits(self, query: str, k: int) -> List[Hit]:
        """BM25 召回（ES 不可用时返回空列表，自动降级为纯向量）"""
        raw = bm25_search_service.search(query, k=k)
        hits: List[Hit] = []
        for item in raw:
            meta = dict(item.get("metadata", {}))
            doc = Document(page_content=item["content"], metadata=meta)
            hits.append(
                {
                    "key": doc_key(doc),
                    "doc": doc,
                    "content": item["content"],
                    "metadata": meta,
                    "score": float(item.get("score", 0.0)),
                    "source": "bm25",
                }
            )
        return hits

    def search_with_details(self, query: str, k: int | None = None) -> Tuple[List[Document], Dict[str, Any]]:
        """混合检索并返回融合明细（评测/调试用）"""
        k = k or config.rag_top_k
        recall_k = max(config.hybrid_recall_k, k)

        vector_hits: List[Hit] = []
        bm25_hits: List[Hit] = []
        bm25_error = None

        try:
            vector_hits = self._vector_hits(query, recall_k)
        except Exception as e:  # 向量库不可用属于致命错误，向上抛出
            logger.error(f"向量召回失败: {e}")
            raise

        try:
            bm25_hits = self._bm25_hits(query, recall_k)
        except Exception as e:
            bm25_error = str(e)
            logger.warning(f"BM25 召回失败，本次降级为纯向量检索: {e}")

        if not bm25_hits:
            docs = [hit["doc"] for hit in vector_hits[:k]]
            for doc in docs:
                doc.metadata["_retrieval"] = "vector_fallback"
            return docs, {
                "mode": "vector_fallback",
                "vector_count": len(vector_hits),
                "bm25_count": 0,
                "bm25_error": bm25_error,
            }

        if config.hybrid_fusion.strip().lower() == "normalize":
            fused = normalize_fuse(vector_hits, bm25_hits, alpha=config.hybrid_alpha)
            mode = "normalize"
        else:
            fused = rrf_fuse(
                [vector_hits, bm25_hits],
                rrf_k=config.hybrid_rrf_k,
                # 向量占 hybrid_vector_weight，BM25 占剩余权重
                weights=[config.hybrid_vector_weight, 1.0 - config.hybrid_vector_weight],
            )
            mode = "rrf"

        ranked = sorted(fused.values(), key=lambda x: x["score"], reverse=True)
        docs: List[Document] = []
        details: List[Dict[str, Any]] = []
        for entry in ranked[:k]:
            doc = entry["doc"]
            doc.metadata["_retrieval"] = f"hybrid_{mode}"
            doc.metadata["_fusion_score"] = round(float(entry["score"]), 6)
            doc.metadata["_ranks"] = entry["ranks"]
            docs.append(doc)
            details.append(
                {
                    "file_name": doc.metadata.get("_file_name", ""),
                    "score": round(float(entry["score"]), 6),
                    "ranks": entry["ranks"],
                }
            )

        logger.info(
            f"混合检索完成: mode={mode}, 向量召回={len(vector_hits)}, "
            f"BM25 召回={len(bm25_hits)}, 输出={len(docs)}"
        )
        return docs, {
            "mode": mode,
            "vector_count": len(vector_hits),
            "bm25_count": len(bm25_hits),
            "results": details,
        }

    def search(self, query: str, k: int | None = None) -> List[Document]:
        """混合检索，返回融合后的 Document 列表"""
        docs, _ = self.search_with_details(query, k)
        return docs


# 全局单例
hybrid_search_service = HybridSearchService()
