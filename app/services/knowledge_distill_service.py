"""闭环沉淀：把每次 AIOps 诊断结果总结成知识库文档，让系统越用越聪明

触发时机：AIOps 诊断成功生成报告后（aiops_service.execute 内挂钩子）。
去重策略：按告警指纹生成确定性 _source 路径，先删旧条目再写入，避免重复累积。
"""

from __future__ import annotations

import hashlib
import json
import re
from typing import Any, Optional

from langchain_core.documents import Document
from langchain_core.prompts import ChatPromptTemplate
from app.core.llm_client import create_chat_qwen
from loguru import logger

from app.config import config
from app.services.bm25_search_service import bm25_search_service
from app.services.vector_store_manager import vector_store_manager


DISTILL_PROMPT = ChatPromptTemplate.from_messages(
    [
        (
            "system",
            "你是一名运维知识沉淀专家。请把一次告警诊断过程总结为结构化、可直接检索的 Markdown 知识条目，"
            "字段包括：告警名称、级别、受影响服务、症状描述、根因分析、处理步骤、处理建议。"
            "内容必须基于给定的执行记录和诊断报告，严禁编造；如果证据不足，如实说明。"
            "输出纯 Markdown，不要输出 JSON 或代码块包裹。",
        ),
        (
            "human",
            "告警信息：\n{alert_info}\n\n执行步骤与结果：\n{steps_info}\n\n诊断报告：\n{report}",
        ),
    ]
)


def fingerprint(alert: Optional[dict], task_input: str) -> str:
    """按告警 labels（无则用任务描述）生成稳定指纹。"""
    if alert and alert.get("labels"):
        raw = json.dumps(alert["labels"], sort_keys=True, ensure_ascii=False)
    else:
        raw = task_input
    return hashlib.sha1(raw.encode("utf-8")).hexdigest()[:12]


def extract_alertname(alert: Optional[dict], task_input: str) -> str:
    """从告警 labels 或任务描述中提取告警名。"""
    if alert and alert.get("labels", {}).get("alertname"):
        return str(alert["labels"]["alertname"])
    m = re.search(r"告警[：:]\s*([\w-]+)", task_input) or re.search(
        r"alertname[：: ]+([\w-]+)", task_input
    )
    return m.group(1) if m else "AIOps诊断经验"


def source_path(alert: Optional[dict], task_input: str, alertname: str) -> str:
    """确定性知识条目路径（用于去重：同指纹覆盖写入）。"""
    return f"generated/{alertname}-{fingerprint(alert, task_input)}.md"


def _format_steps(past_steps: list) -> str:
    lines = []
    for step, result in past_steps:
        preview = (str(result) or "")[:600]
        lines.append(f"### 步骤：{step}\n{preview}")
    return "\n\n".join(lines)


async def _summarize(alert_info: str, steps_info: str, report: str) -> str:
    """调用 LLM 生成知识条目 Markdown（独立函数便于测试替换）。"""
    llm = create_chat_qwen(
        model=config.rag_model,
        temperature=0,
    )
    result = await (DISTILL_PROMPT | llm).ainvoke(
        {
            "alert_info": alert_info,
            "steps_info": steps_info,
            "report": report[:8000],
        }
    )
    return result.content if hasattr(result, "content") else str(result)


async def distill(
    alert: Optional[dict],
    task_input: str,
    past_steps: list,
    response: str,
) -> bool:
    """总结一次诊断并写入向量知识库；返回是否成功。"""
    try:
        if not response or not response.strip():
            logger.info("诊断无有效响应，跳过闭环沉淀")
            return False

        alertname = extract_alertname(alert, task_input)
        alert_info = (
            json.dumps(alert, ensure_ascii=False)
            if alert
            else f"任务输入：{task_input[:500]}"
        )
        steps_info = _format_steps(past_steps) or "（无工具执行记录）"

        markdown = await _summarize(alert_info, steps_info, response)
        markdown = markdown.strip()
        if not markdown:
            logger.warning("LLM 沉淀内容为空，跳过")
            return False

        source = source_path(alert, task_input, alertname)
        # 去重：先删除同指纹旧条目，再写入新条目
        vector_store_manager.delete_by_source(source)
        if config.hybrid_enabled:
            bm25_search_service.delete_by_source(source)
        doc = Document(
            page_content=markdown,
            metadata={
                "_source": source,
                "_extension": ".md",
                "_file_name": f"{alertname}.md",
                "_generated": 1,
                "_alertname": alertname,
            },
        )
        vector_store_manager.add_documents([doc])
        # 同步写入 ES，使沉淀经验也能被 BM25/混合检索命中
        if config.hybrid_enabled:
            try:
                bm25_search_service.index_documents([doc])
                bm25_search_service.refresh()
                logger.info("沉淀知识已写入 BM25 索引")
            except Exception as e:
                logger.warning(f"沉淀知识写入 BM25 索引失败（不影响向量检索）: {e}")
        logger.info(f"知识库沉淀完成: {source}（{len(markdown)} 字符）")
        return True

    except Exception as e:
        logger.error(f"知识库沉淀失败: {e}", exc_info=True)
        return False
