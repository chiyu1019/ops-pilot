"""
通用 Plan-Execute-Replan 状态定义
基于 LangGraph 官方教程实现
"""

from typing import List, TypedDict, Annotated
import operator


class PlanExecuteState(TypedDict):
    """Plan-Execute-Replan 状态"""
    
    # 用户输入（任务描述）
    input: str
    
    # 执行计划（步骤列表）
    plan: List[str]
    
    # 已执行的步骤历史
    # 使用 operator.add 实现追加式更新（而非覆盖）
    past_steps: Annotated[List[tuple], operator.add]
    
    # 最终响应/报告
    response: str

    # 证据链（每次工具调用产出的 EvidenceRecord，追加式）
    evidence: Annotated[List[dict], operator.add]

    # 结构化诊断与校验结果
    diagnosis: dict
    verification: dict

    # 补证轮次（防止无限补证）
    repair_rounds: int
