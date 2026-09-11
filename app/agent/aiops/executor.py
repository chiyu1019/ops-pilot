"""
Executor 节点：执行单个步骤
基于 LangGraph 官方教程实现
"""

from typing import Dict, Any
from langchain_core.messages import HumanMessage, SystemMessage
from app.core.llm_client import create_chat_qwen
from langgraph.prebuilt import ToolNode
from loguru import logger

from app.config import config
from app.agent.aiops.evidence import extract_records_from_tool_messages
from app.core.reliability import (
    ReliabilityState,
    compress_text,
    estimate_tokens,
    tool_call_fingerprint,
    tool_result_cache,
)
from app.tools import DEFAULT_LOCAL_AGENT_TOOLS
from app.agent.mcp_client import get_mcp_client_with_retry
from .state import PlanExecuteState


def _with_cache(tool):
    """为工具增加结果缓存（保留原 args_schema，仅拦截执行）"""
    import copy

    clone = copy.copy(tool)
    original_run = tool._run

    def _cached_run(*args, **kwargs):
        key = tool_call_fingerprint(getattr(tool, "name", "tool"), kwargs or {"args": args})
        hit = tool_result_cache.get(key)
        if hit is not None:
            logger.info(f"工具缓存命中: {tool.name} (fingerprint={key})")
            return hit
        result = original_run(*args, **kwargs)
        tool_result_cache.set(key, str(result))
        return result

    clone._run = _cached_run
    return clone


async def executor(state: PlanExecuteState) -> Dict[str, Any]:
    """
    执行节点：执行计划中的下一个步骤
    
    使用 LangGraph 的 ToolNode 自动处理工具调用
    """
    logger.info("=== Executor：执行步骤 ===")

    plan = state.get("plan", [])

    # 如果计划为空，不执行
    if not plan:
        logger.info("计划为空，跳过执行")
        return {}

    # 取出第一个步骤
    task = plan[0]
    logger.info(f"当前任务: {task}")

    try:
        # 获取本地工具
        local_tools = list(DEFAULT_LOCAL_AGENT_TOOLS)

        # 获取 MCP 工具
        mcp_client = await get_mcp_client_with_retry()
        mcp_tools = await mcp_client.get_tools()
        logger.info(f"可用工具数量: 本地 {len(local_tools)} + MCP {len(mcp_tools)}")

        # 合并所有工具（按配置启用结果缓存，减少重复调用与重复上下文）
        all_tools = local_tools + mcp_tools
        if config.reliability_tool_cache_enabled:
            all_tools = [_with_cache(t) for t in all_tools]

        # 创建 LLM（绑定工具）
        llm = create_chat_qwen(
            model=config.rag_model,
            temperature=0
        )
        llm_with_tools = llm.bind_tools(all_tools)

        # 创建工具节点（自动执行工具调用）
        tool_node = ToolNode(all_tools)

        # 构建消息（只包含当前步骤，避免原始任务干扰）
        messages = [
            SystemMessage(content="""你是一个能力强大的助手，负责执行具体的任务步骤。

你可以使用各种工具来完成任务。对于每个步骤：
1. 理解步骤的目标
2. 选择合适的工具，如果已经指定了工具，则使用指定的工具
3. 调用工具获取信息
4. 返回执行结果

注意：
- 如果工具调用失败，请说明失败原因
- 不要编造数据，只返回实际获取的信息
- 执行结果要清晰、准确
- 专注于当前步骤，不要考虑其他任务"""),
            HumanMessage(content=f"请执行以下任务: {task}")
        ]

        # 第一步：LLM 决定是否调用工具
        llm_response = await llm_with_tools.ainvoke(messages)
        logger.info(f"LLM 响应类型: {type(llm_response)}")

        # 第二步：如果有工具调用，执行工具
        evidence_records = []
        if hasattr(llm_response, "tool_calls") and llm_response.tool_calls:
            logger.info(f"检测到 {len(llm_response.tool_calls)} 个工具调用")
            
            # 使用 ToolNode 自动执行工具
            messages.append(llm_response)
            tool_messages = await tool_node.ainvoke({"messages": messages})
            
            # 第三步：将工具结果返回给 LLM 生成最终答案
            # 确定性抽取证据（必须在压缩之前，保证证据来自原始返回）
            evidence_records = extract_records_from_tool_messages(tool_messages["messages"])

            # 上下文压缩：只截断喂给 LLM 的文本，不影响证据链
            compressed_saved = 0
            if config.reliability_context_compress_enabled:
                for _msg in tool_messages["messages"]:
                    content = getattr(_msg, "content", None)
                    if isinstance(content, str) and len(content) > config.reliability_context_max_chars:
                        _msg.content = compress_text(content, config.reliability_context_max_chars)
                        compressed_saved += len(content) - len(_msg.content)

            messages.extend(tool_messages["messages"])
            final_response = await llm_with_tools.ainvoke(messages)
            result = final_response.content if hasattr(final_response, 'content') else str(final_response)
        else:
            # 没有工具调用，直接使用 LLM 的输出
            logger.info("LLM 未调用工具，直接返回结果")
            result = llm_response.content if hasattr(llm_response, 'content') else str(llm_response)

        logger.info(f"步骤执行完成，结果长度: {len(result)}")

        # 返回更新：移除已执行的步骤，添加执行历史与证据链
        # 可靠性统计：缓存命中、压缩收益、估算 Token
        prev = ReliabilityState.from_dict(state.get("reliability"))
        prev.tool_calls += 1
        prev.compressed_chars_saved += compressed_saved
        if config.reliability_tool_cache_enabled:
            stats = tool_result_cache.stats()
            prev.tool_cache_hits = stats["hits"]
            prev.tool_cache_misses = stats["misses"]
        prev.estimated_tokens += estimate_tokens(result) + estimate_tokens(task)
        if config.reliability_token_budget and prev.estimated_tokens > config.reliability_token_budget:
            prev.budget_exceeded = True

        return {
            "plan": plan[1:],  # 移除第一个步骤
            "past_steps": [(task, result)],  # 使用 operator.add 追加
            "evidence": evidence_records,  # 确定性抽取的证据（operator.add 追加）
            "reliability": prev.to_dict(),
        }

    except Exception as e:
        logger.error(f"执行步骤失败: {e}", exc_info=True)
        prev = ReliabilityState.from_dict(state.get("reliability"))
        return {
            "plan": plan[1:],
            "past_steps": [(task, f"执行失败: {str(e)}")],
            "reliability": prev.to_dict(),
        }
