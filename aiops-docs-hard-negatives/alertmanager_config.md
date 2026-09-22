# Alertmanager 配置说明

## 核心概念
- route：告警路由树
- receiver：通知接收方（webhook/邮件/企业微信）
- inhibit_rules：抑制规则
- group_wait / group_interval / repeat_interval：分组与重复推送周期

## 配置片段
```yaml
route:
  receiver: 'ops-webhook'
  repeat_interval: 4h
  routes:
    - matchers: [ severity="critical" ]
      receiver: 'oncall-phone'
```

本文档说明告警推送配置，不涉及故障根因分析方法。
