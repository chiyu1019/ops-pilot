# 服务健康检查配置规范

## 探针类型
- livenessProbe：判断是否需要重启
- readinessProbe：判断是否可接收流量

## 推荐参数
```yaml
initialDelaySeconds: 30
periodSeconds: 10
failureThreshold: 3
```

## 常见错误
探针路径配置错误、超时过短导致误判、依赖未就绪即通过检查。

本文档聚焦探针配置，不包含服务不可用故障的排查流程。
