"""知识检索工具 - 从向量数据库中检索相关信息"""

from typing import List, Tuple

from langchain_core.documents import Document
from langchain_core.tools import tool
from loguru import logger

from app.config import config
from app.services.hybrid_search_service import hybrid_search_service
from app.services.vector_store_manager import vector_store_manager


def _retrieve(query: str) -> List[Document]:
    """按配置选择混合检索（向量 + BM25）或纯向量检索

    混合检索失败（如 ES 不可用）时自动降级为纯向量检索，保证问答不中断。
    """
    if config.hybrid_enabled:
        try:
            return hybrid_search_service.search(query, k=config.rag_top_k)
        except Exception as e:
            logger.warning(f"混合检索失败，降级为纯向量检索: {e}")

    # 纯向量检索（降级路径）
    vector_store = vector_store_manager.get_vector_store()
    retriever = vector_store.as_retriever(search_kwargs={"k": config.rag_top_k})
    docs = retriever.invoke(query)
    for doc in docs:
        doc.metadata["_retrieval"] = "vector"
    return docs


@tool(response_format="content_and_artifact")
def retrieve_knowledge(query: str) -> Tuple[str, List[Document]]:
    """从知识库中检索相关信息来回答问题
    
    当用户的问题涉及专业知识、文档内容或需要参考资料时，使用此工具。
    
    Args:
        query: 用户的问题或查询
        
    Returns:
        Tuple[str, List[Document]]: (格式化的上下文文本, 原始文档列表)
    """
    try:
        logger.info(f"知识检索工具被调用: query='{query}'")
        
        # 检索相关文档（混合检索：向量 + BM25，RRF/归一化融合）
        docs = _retrieve(query)
        
        if not docs:
            logger.warning("未检索到相关文档")
            return "没有找到相关信息。", []
        
        # 格式化文档为上下文
        context = format_docs(docs)
        
        logger.info(f"检索到 {len(docs)} 个相关文档")
        return context, docs
        
    except Exception as e:
        logger.error(f"知识检索工具调用失败: {e}")
        return f"检索知识时发生错误: {str(e)}", []


def format_docs(docs: List[Document]) -> str:
    """
    格式化文档列表为上下文文本
    
    Args:
        docs: 文档列表
        
    Returns:
        str: 格式化的上下文文本
    """
    formatted_parts = []
    
    for i, doc in enumerate(docs, 1):
        # 提取元数据
        metadata = doc.metadata
        source = metadata.get("_file_name", "未知来源")
        
        # 提取标题信息 (如果有)
        headers = []
        for key in ["h1", "h2", "h3"]:
            if key in metadata and metadata[key]:
                headers.append(metadata[key])
        
        header_str = " > ".join(headers) if headers else ""
        
        # 构建格式化文本
        formatted = f"【参考资料 {i}】"
        if header_str:
            formatted += f"\n标题: {header_str}"
        formatted += f"\n来源: {source}"
        retrieval = metadata.get("_retrieval")
        if retrieval:
            formatted += f"\n检索方式: {retrieval}"
        formatted += f"\n内容:\n{doc.page_content}\n"
        
        formatted_parts.append(formatted)
    
    return "\n".join(formatted_parts)
