"""配置管理模块

使用 Pydantic Settings 实现类型安全的配置管理
"""

from typing import Dict, Any
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """应用配置"""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # 应用配置
    app_name: str = "OpsPilot"
    app_version: str = "1.0.0"
    debug: bool = False
    host: str = "0.0.0.0"
    port: int = 9900

    # DashScope 配置
    dashscope_api_key: str = ""  # 默认空字符串，实际使用需从环境变量加载
    # 支持百炼专属实例/自定义网关地址（如 ws-xxx.maas.aliyuncs.com）
    dashscope_api_base: str = "https://dashscope.aliyuncs.com/compatible-mode/v1"
    # 可靠性约束与成本治理
    reliability_tool_cache_enabled: bool = True      # 稳定工具结果缓存（按 tool_call_fingerprint）
    reliability_context_compress_enabled: bool = True  # 工具结果/上下文压缩
    reliability_context_max_chars: int = 600         # 单条工具结果进入上下文的字符上限
    reliability_token_budget: int = 60000            # 估算 Token 预算，超限输出部分报告

    # 结构化诊断 + 证据链校验（DiagnosisClaim / Verifier）
    diagnosis_verify_enabled: bool = True
    diagnosis_max_repair_rounds: int = 1

    # LLM 瞬时错误重试（专属实例偶发 403/429/5xx 时自动重试）
    llm_max_retries: int = 3
    llm_retry_delay: float = 1.0
    dashscope_model: str = "qwen-max"
    dashscope_embedding_model: str = "text-embedding-v4"  # v4 支持多种维度（默认 1024）

    # Milvus 配置
    milvus_host: str = "localhost"
    milvus_port: int = 19530
    milvus_timeout: int = 10000  # 毫秒

    # RAG 配置
    rag_top_k: int = 3
    rag_model: str = "qwen-max"  # 使用快速响应模型，不带扩展思考

    # 文档分块配置
    chunk_max_size: int = 800
    chunk_overlap: int = 100

    # MCP 服务配置（transport: stdio | sse | streamable-http）
    # 腾讯云托管 MCP 的 URL 通常含 /sse/，需使用 sse；本地 FastMCP 使用 streamable-http
    mcp_cls_transport: str = "streamable-http"
    mcp_cls_url: str = "http://localhost:8003/mcp"
    mcp_monitor_transport: str = "streamable-http"
    mcp_monitor_url: str = "http://localhost:8004/mcp"

    # Prometheus
    prometheus_base_url: str = "http://127.0.0.1:9090"
    prometheus_request_timeout: float = 10.0

    # ---------- 混合检索（向量 + BM25 关键词，RRF/归一化融合） ----------
    # 是否启用混合检索（关闭则退化为纯向量检索）
    hybrid_enabled: bool = True
    # Elasticsearch 地址与索引名
    es_url: str = "http://localhost:9200"
    es_index: str = "opspilot_knowledge"
    # 融合方式：rrf（倒数排名融合，推荐）| normalize（分数归一化加权）
    hybrid_fusion: str = "rrf"
    # RRF 常数 k（论文默认 60，越小越强调头部排名）
    hybrid_rrf_k: int = 60
    # 每一路召回的候选数量（融合前的候选池）
    hybrid_recall_k: int = 10
    # normalize 模式下向量得分权重（1-alpha 为 BM25 权重）
    hybrid_alpha: float = 0.5
    # RRF 模式下向量路权重（BM25 占剩余权重；0.5=等权，中文小知识库建议 0.7）
    hybrid_vector_weight: float = 0.7

    # 会话记忆后端：memory（进程内，重启丢失）| redis | postgres
    memory_backend: str = "memory"
    redis_url: str = "redis://localhost:6379/0"
    postgres_dsn: str = "postgresql://postgres:postgres@localhost:5432/langgraph"

    # 自动响应（实时告警接入）
    auto_response_enabled: bool = True
    alert_poll_interval: int = 30       # 轮询 Prometheus 告警间隔（秒）
    alert_cooldown_seconds: int = 900   # 冷却模式下的去重窗口（秒）
    # 告警去重模式：
    #   once_per_incident（默认）—— 同一次告警只诊断/通知一次，直到恢复(resolved)后才允许再次触发
    #   cooldown           —— 旧行为：冷却窗口过后，持续未恢复的告警会再次触发
    alert_dedup_mode: str = "once_per_incident"

    # 闭环沉淀（诊断结果回写知识库）
    knowledge_distill_enabled: bool = True

    # 通知（飞书机器人；只有 source=alert_auto 的自动告警诊断会推送）
    notification_enabled: bool = True
    feishu_webhook_url: str = ""          # 为空则跳过发送（打 warning，不影响 Agent）
    feishu_secret: str = ""               # 群机器人开启"签名校验"时填写，否则留空
    feishu_timeout: float = 5.0
    notification_idempotency_ttl: int = 900   # 幂等窗口（秒），同会话同告警同状态只发一次

    @property
    def mcp_servers(self) -> Dict[str, Dict[str, Any]]:
        """获取完整的 MCP 服务器配置"""
        return {
            "cls": {
                "transport": self.mcp_cls_transport,
                "url": self.mcp_cls_url,
            },
            "monitor": {
                "transport": self.mcp_monitor_transport,
                "url": self.mcp_monitor_url,
            }
        }


# 全局配置实例
config = Settings()
