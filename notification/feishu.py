"""飞书自定义机器人 Webhook 客户端

职责：把 DiagnosisNotification 渲染成飞书卡片（interactive）或文本（text）并发送。
- 不读业务状态，只做"消息渲染 + 发送"
- 任何异常都不向外抛，统一返回 NotificationResult
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import time
from typing import Any, Dict, Optional

import httpx
from loguru import logger

from app.config import config
from notification.schemas import DiagnosisNotification, NotificationResult

# 飞书 header 颜色
_TEMPLATE_BY_SEVERITY = {"critical": "red", "emergency": "purple", "warning": "orange", "info": "blue"}
_TEMPLATE_BY_STATUS = {"hypothesis": "grey", "safe_report": "grey"}


class FeishuClient:
    """飞书 Webhook 客户端"""

    def __init__(
        self,
        webhook_url: Optional[str] = None,
        secret: Optional[str] = None,
        timeout: Optional[float] = None,
    ) -> None:
        self.webhook_url = (webhook_url if webhook_url is not None else config.feishu_webhook_url) or ""
        self.secret = (secret if secret is not None else config.feishu_secret) or ""
        self.timeout = timeout if timeout is not None else config.feishu_timeout

    # ---------- 配置检查 ----------
    @property
    def configured(self) -> bool:
        return bool(self.webhook_url.strip())

    # ---------- 签名（群机器人开启"签名校验"时需要） ----------
    def _sign(self, timestamp: str) -> str:
        string_to_sign = f"{timestamp}\n{self.secret}"
        digest = hmac.new(string_to_sign.encode("utf-8"), digestmod=hashlib.sha256).digest()
        return base64.b64encode(digest).decode("utf-8")

    def _with_signature(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        if not self.secret:
            return payload
        ts = str(int(time.time()))
        payload = dict(payload)
        payload["timestamp"] = ts
        payload["sign"] = self._sign(ts)
        return payload

    # ---------- 渲染 ----------
    def _header_template(self, n: DiagnosisNotification) -> str:
        status_raw = n.status.split("（")[0]
        if "假设" in status_raw or "安全报告" in status_raw:
            return _TEMPLATE_BY_STATUS.get("hypothesis", "grey")
        return _TEMPLATE_BY_SEVERITY.get(n.severity, "blue")

    def build_card(self, n: DiagnosisNotification) -> Dict[str, Any]:
        """构造 interactive 卡片消息体"""
        evidence_text = "\n".join(f"{i}. {e}" for i, e in enumerate(n.evidence, 1)) or "（无工具证据）"
        return {
            "msg_type": "interactive",
            "card": {
                "config": {"wide_screen_mode": True},
                "header": {
                    "template": self._header_template(n),
                    "title": {"tag": "plain_text", "content": "🚨 OpsPilot故障诊断报告"},
                },
                "elements": [
                    {
                        "tag": "div",
                        "fields": [
                            {"is_short": True, "text": {"tag": "lark_md", "content": f"**告警名称**\n{n.alert_name}"}},
                            {
                                "is_short": True,
                                "text": {
                                    "tag": "lark_md",
                                    "content": f"**告警级别**\n{n.severity_emoji} {n.severity}",
                                },
                            },
                            {"is_short": True, "text": {"tag": "lark_md", "content": f"**影响服务**\n{n.service}"}},
                            {
                                "is_short": True,
                                "text": {"tag": "lark_md", "content": f"**Agent执行状态**\n{n.status}"},
                            },
                        ],
                    },
                    {"tag": "hr"},
                    {"tag": "div", "text": {"tag": "lark_md", "content": f"**📋 故障现象**\n{n.summary}"}},
                    {"tag": "div", "text": {"tag": "lark_md", "content": f"**🔍 分析结论**\n{n.diagnosis}"}},
                    {"tag": "div", "text": {"tag": "lark_md", "content": f"**🔗 关键证据**\n{evidence_text}"}},
                    {"tag": "div", "text": {"tag": "lark_md", "content": f"**🛠 处理建议**\n{n.suggestion}"}},
                    {
                        "tag": "note",
                        "elements": [
                            {
                                "tag": "plain_text",
                                "content": f"生成时间：{n.generated_at}　来源：{n.source}　会话：{n.session_id or '-'}",
                            }
                        ],
                    },
                ],
            },
        }

    def build_text(self, n: DiagnosisNotification) -> Dict[str, Any]:
        """构造 text 消息体（用于快速连通性验证）"""
        content = (
            f"🚨 OpsPilot故障诊断报告\n"
            f"告警：{n.alert_name}（{n.severity}）\n"
            f"服务：{n.service}\n"
            f"状态：{n.status}\n"
            f"结论：{n.diagnosis}\n"
            f"建议：{n.suggestion.replace(chr(10), ' ')}"
        )
        return {"msg_type": "text", "content": {"text": content}}

    # ---------- 发送 ----------
    async def _post(self, payload: Dict[str, Any]) -> NotificationResult:
        if not self.configured:
            logger.warning("feishu webhook not configured, skip notification")
            return NotificationResult(sent=False, skipped=True, reason="webhook_not_configured")

        body = self._with_signature(payload)
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                resp = await client.post(self.webhook_url, json=body)
                resp.raise_for_status()
                data = resp.json()
            if int(data.get("code", 0)) == 0:
                logger.info(
                    "feishu notification sent successfully "
                    f"(msg_type={payload.get('msg_type')}, code={data.get('code')})"
                )
                return NotificationResult(sent=True)
            # 飞书返回业务错误（如 19021 webhook 无效、9499 签名校验失败）
            err = f"feishu_code={data.get('code')} msg={data.get('msg')}"
            logger.error(f"feishu notification failed: {err}")
            return NotificationResult(sent=False, error=err)
        except Exception as e:  # 网络异常 / 超时 / JSON 解析失败
            logger.exception(f"feishu notification failed: {type(e).__name__}: {e}")
            return NotificationResult(sent=False, error=f"{type(e).__name__}: {e}")

    async def send_card(self, notification: DiagnosisNotification) -> NotificationResult:
        """发送 interactive 卡片（优先使用）"""
        return await self._post(self.build_card(notification))

    async def send_text(self, notification: DiagnosisNotification) -> NotificationResult:
        """发送纯文本消息"""
        return await self._post(self.build_text(notification))


# 全局单例
feishu_client = FeishuClient()
