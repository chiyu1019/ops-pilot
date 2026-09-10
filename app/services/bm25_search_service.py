"""BM25 关键词检索服务（Elasticsearch 实现）

与向量检索互补：向量擅长语义相近但用词不同的查询，
BM25 擅长专有名词、告警名、错误码等精确关键词匹配。

对外接口：
- ensure_index()        创建索引（幂等）
- index_documents(docs) 批量写入分片
- delete_by_source(src) 删除某来源文件的全部分片
- search(query, k)      返回 [{id, content, metadata, score}]
- health()              ES 可用性检查
"""

from __future__ import annotations

import hashlib
from typing import Any, Dict, List

from langchain_core.documents import Document
from loguru import logger

from app.config import config


class BM25SearchService:
    """基于 Elasticsearch 的 BM25 关键词检索"""

    def __init__(self) -> None:
        self._client = None
        self._index_ready = False

    # ---------- 连接管理 ----------
    def _get_client(self):
        """惰性创建 ES 客户端（不可用时抛异常，由上层降级处理）"""
        if self._client is None:
            from elasticsearch import Elasticsearch

            self._client = Elasticsearch(
                config.es_url,
                request_timeout=10,
                retry_on_timeout=True,
                max_retries=2,
            )
        return self._client

    def health(self) -> bool:
        """ES 是否可用"""
        try:
            return bool(self._get_client().ping())
        except Exception as e:
            logger.warning(f"Elasticsearch 不可用: {e}")
            return False

    # ---------- 索引管理 ----------
    def ensure_index(self) -> None:
        """创建索引与 mapping（幂等）"""
        client = self._get_client()
        if client.indices.exists(index=config.es_index):
            self._index_ready = True
            return

        mapping = {
            "mappings": {
                "properties": {
                    "content": {"type": "text"},
                    "headers": {"type": "text"},
                    "file_name": {"type": "keyword"},
                    "source": {"type": "keyword"},
                    "chunk_index": {"type": "integer"},
                }
            }
        }
        client.indices.create(index=config.es_index, body=mapping)
        self._index_ready = True
        logger.info(f"Elasticsearch 索引已创建: {config.es_index}")

    @staticmethod
    def _doc_id(source: str, chunk_index: int) -> str:
        """确定性文档 ID：同一来源 + 分片序号 -> 稳定 ID（便于覆盖更新）"""
        raw = f"{source}::{chunk_index}".encode("utf-8")
        return hashlib.sha1(raw).hexdigest()

    # ---------- 写入 / 删除 ----------
    def index_documents(self, documents: List[Document]) -> int:
        """批量写入分片到 ES（自动 ensure_index）"""
        if not documents:
            return 0
        self.ensure_index()
        client = self._get_client()
        operations = []
        for idx, doc in enumerate(documents):
            meta = doc.metadata or {}
            source = str(meta.get("_source", ""))
            headers = " > ".join(
                str(meta[k]) for k in ("h1", "h2", "h3") if meta.get(k)
            )
            operations.append(
                {"index": {"_index": config.es_index, "_id": self._doc_id(source, idx)}}
            )
            operations.append(
                {
                    "content": doc.page_content,
                    "headers": headers,
                    "file_name": str(meta.get("_file_name", "")),
                    "source": source,
                    "chunk_index": idx,
                }
            )
        resp = client.bulk(operations=operations, refresh=False)
        if resp.get("errors"):
            logger.warning("部分文档写入 ES 失败（bulk errors=true）")
        logger.info(f"ES 索引写入完成: {len(documents)} 个分片 -> {config.es_index}")
        return len(documents)

    def delete_by_source(self, source: str) -> int:
        """删除某个来源文件的全部分片（文件重复上传时先删后写）"""
        try:
            client = self._get_client()
            if not client.indices.exists(index=config.es_index):
                return 0
            resp = client.delete_by_query(
                index=config.es_index,
                body={"query": {"term": {"source": source}}},
                refresh=True,
            )
            deleted = int(resp.get("deleted", 0))
            logger.info(f"ES 删除旧分片: source={source}, 数量={deleted}")
            return deleted
        except Exception as e:
            logger.warning(f"ES 删除分片失败（首次索引时属正常）: {e}")
            return 0

    def refresh(self) -> None:
        """刷新索引，保证刚写入的数据立即可被检索"""
        try:
            self._get_client().indices.refresh(index=config.es_index)
        except Exception as e:
            logger.warning(f"ES refresh 失败: {e}")

    # ---------- 检索 ----------
    def search(self, query: str, k: int = 10) -> List[Dict[str, Any]]:
        """BM25 检索，返回按相关性倒序的结果"""
        client = self._get_client()
        body = {
            "query": {
                "multi_match": {
                    "query": query,
                    "fields": ["content^2", "headers^1.5", "file_name"],
                    "type": "best_fields",
                }
            },
            "size": k,
        }
        resp = client.search(index=config.es_index, body=body)
        results: List[Dict[str, Any]] = []
        for hit in resp.get("hits", {}).get("hits", []):
            src = hit.get("_source", {})
            results.append(
                {
                    "id": hit.get("_id", ""),
                    "content": src.get("content", ""),
                    "score": float(hit.get("_score") or 0.0),
                    "metadata": {
                        "_source": src.get("source", ""),
                        "_file_name": src.get("file_name", ""),
                        "headers": src.get("headers", ""),
                        "_retrieval": "bm25",
                    },
                }
            )
        logger.debug(f"BM25 检索完成: query={query!r}, 命中={len(results)}")
        return results


# 全局单例
bm25_search_service = BM25SearchService()
