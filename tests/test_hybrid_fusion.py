"""混合检索融合算法单元测试（纯逻辑，不依赖 Milvus / ES）"""

from langchain_core.documents import Document

from app.services.hybrid_search_service import (
    _min_max_normalize,
    doc_key,
    normalize_fuse,
    rrf_fuse,
)


def _hit(content: str, source: str, score: float, origin: str):
    doc = Document(page_content=content, metadata={"_source": source, "_file_name": source})
    return {
        "key": doc_key(doc),
        "doc": doc,
        "content": content,
        "metadata": doc.metadata,
        "score": score,
        "source": origin,
    }


def test_min_max_normalize_basic():
    assert _min_max_normalize([0.0, 5.0, 10.0]) == [0.0, 0.5, 1.0]


def test_min_max_normalize_edge_cases():
    assert _min_max_normalize([]) == []
    # 所有分数相同：全 1，避免除零
    assert _min_max_normalize([3.0, 3.0]) == [1.0, 1.0]


def test_doc_key_stable_and_content_sensitive():
    d1 = Document(page_content="CPU 过高排查", metadata={"_source": "a.md"})
    d2 = Document(page_content="CPU 过高排查", metadata={"_source": "a.md"})
    d3 = Document(page_content="内存 过高排查", metadata={"_source": "a.md"})
    assert doc_key(d1) == doc_key(d2)
    assert doc_key(d1) != doc_key(d3)


def test_rrf_prefers_documents_hitting_both_paths():
    # doc A 在两路都排第一；doc B 仅向量第一；doc C 仅 BM25 第二
    a = _hit("A 内容", "A.md", 0.9, "vector")
    b = _hit("B 内容", "B.md", 0.95, "vector")
    c = _hit("C 内容", "C.md", 8.0, "bm25")
    vector_hits = [b, a]
    bm25_hits = [dict(a, source="bm25", score=9.0), c]

    fused = rrf_fuse([vector_hits, bm25_hits], rrf_k=60)
    ranked = sorted(fused.values(), key=lambda x: x["score"], reverse=True)

    assert ranked[0]["doc"].page_content == "A 内容"  # 两路都命中的排最前
    assert ranked[0]["ranks"] == {"vector": 2, "bm25": 1}
    assert ranked[-1]["doc"].page_content == "C 内容"


def test_rrf_scores_are_reciprocal_ranks():
    a = _hit("A", "A.md", 1.0, "vector")
    fused = rrf_fuse([[a]], rrf_k=60)
    assert abs(fused[doc_key(a["doc"])]["score"] - 1 / 61) < 1e-9


def test_normalize_fuse_respects_alpha():
    v = _hit("V", "V.md", 1.0, "vector")
    b = _hit("B", "B.md", 10.0, "bm25")

    # alpha=1.0 -> 完全由向量决定
    fused_v = normalize_fuse([v], [b], alpha=1.0)
    assert fused_v[doc_key(v["doc"])]["score"] == 1.0
    assert fused_v[doc_key(b["doc"])]["score"] == 0.0

    # alpha=0.5 -> 两路各占 0.5（单元素时归一化后都是 1.0）
    fused_half = normalize_fuse([v], [b], alpha=0.5)
    assert fused_half[doc_key(v["doc"])]["score"] == 0.5
    assert fused_half[doc_key(b["doc"])]["score"] == 0.5


def test_normalize_fuse_merges_same_document_from_both_paths():
    v = _hit("同一条", "same.md", 1.0, "vector")
    b = dict(v, source="bm25", score=5.0)
    fused = normalize_fuse([v], [b], alpha=0.5)
    assert len(fused) == 1
    assert fused[doc_key(v["doc"])]["score"] == 1.0
    assert fused[doc_key(v["doc"])]["ranks"] == {"vector": 1, "bm25": 1}
