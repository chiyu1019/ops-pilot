# Kubernetes Pod 频繁重启排查方案

## 现象
Pod 在数分钟内反复 Restart，`kubectl get pod` 显示 RESTARTS 计数持续增长，业务出现间歇性不可用。

## 排查步骤
### 步骤1：查看 Pod 状态与重启原因
`kubectl describe pod <pod> -n <ns>` 关注 Last State: Terminated 的 Reason 与 Exit Code。

### 步骤2：区分退出码语义
- Exit Code 137：OOMKilled 或 SIGKILL，多为内存超限
- Exit Code 1：应用内部异常退出，需看应用日志
- Exit Code 143：SIGTERM，多为探针失败或被驱逐

### 步骤3：检查探针配置
livenessProbe 的 initialDelaySeconds 过小会导致应用未就绪即被重启。

### 步骤4：检查资源限制
CPU/内存 limits 设置过低会触发 OOMKilled 或 CPU 节流。

## 常见原因
1. 内存 limit 过低触发 OOMKilled
2. 存活探针路径或端口配置错误
3. 应用启动依赖外部服务超时
4. 节点资源不足导致 Pod 被驱逐

## 处理建议
调整 limits/requests、放宽探针阈值、修复启动依赖，必要时用 `kubectl logs --previous` 查看崩溃前日志。
