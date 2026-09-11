# Nginx 5xx 错误排查

## 现象
网关返回 502 / 504，用户请求失败。

## 区分错误码
- 502 Bad Gateway：上游返回非法响应或连接被拒绝
- 504 Gateway Timeout：上游响应超时
- 499：客户端主动断开

## 排查步骤
1. 查看 error.log 中的 upstream 相关记录
2. 确认后端服务是否存活、端口是否监听
3. 检查 proxy_connect_timeout / proxy_read_timeout 是否过短
4. 检查 upstream 的 keepalive 配置与连接复用
5. 查看后端应用日志定位真实异常

## 常见原因
后端进程崩溃、后端处理超时、连接池耗尽、DNS 解析失败、健康检查未及时摘除故障节点。

## 处理建议
调整超时与重试策略、增加 upstream keepalive、完善健康检查与熔断降级。
