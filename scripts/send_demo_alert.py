"""发送一条演示告警（用于录制飞书通知演示）

自动使用当前时间作为 activeAt，保证每次都是"新事件"，不会被去重跳过。

用法：
    python scripts/send_demo_alert.py
    python scripts/send_demo_alert.py --alertname ServiceUnavailable --instance payment-service --severity critical
    python scripts/send_demo_alert.py --api http://localhost:9900/api/webhook/alerts
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone

import httpx


def main() -> int:
    parser = argparse.ArgumentParser(description="发送演示告警到 OpsPilot（触发自动诊断 + 飞书通知）")
    parser.add_argument("--alertname", default="ServiceUnavailable", help="告警名称")
    parser.add_argument("--instance", default="payment-service", help="受影响服务/实例")
    parser.add_argument("--severity", default="critical", choices=["critical", "warning", "info"], help="告警级别")
    parser.add_argument("--summary", default="", help="告警描述（留空则自动生成）")
    parser.add_argument("--api", default="http://localhost:9900/api/webhook/alerts", help="Webhook 地址")
    args = parser.parse_args()

    active_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")  # 每次都是新事件
    summary = args.summary or f"{args.instance} 触发 {args.alertname} 告警，请立即排查"

    payload = {
        "status": "firing",
        "alerts": [
            {
                "labels": {
                    "alertname": args.alertname,
                    "severity": args.severity,
                    "instance": args.instance,
                },
                "annotations": {"summary": args.alertname, "description": summary},
                "state": "firing",
                "activeAt": active_at,
            }
        ],
    }

    print(f"发送告警: {args.alertname} / {args.instance} / {args.severity}  activeAt={active_at}")
    try:
        resp = httpx.post(args.api, json=payload, timeout=30)
        data = resp.json()
    except Exception as e:
        print(f"发送失败: {type(e).__name__}: {e}")
        return 1

    result = (data.get("data") or {})
    print(f"HTTP {resp.status_code}  触发诊断={result.get('triggered')}  resolved={result.get('resolved')}")
    if not result.get("triggered"):
        print("提示：triggered=0 说明该告警已被去重（同 alertname + 同小时）。换个 alertname 或等下一小时再发。")
    else:
        print("诊断已在后台执行，约 1-2 分钟后飞书群会收到诊断卡片。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
