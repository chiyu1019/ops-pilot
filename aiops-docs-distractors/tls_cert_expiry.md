# 证书过期告警处理

## 现象
HTTPS 访问报证书错误，客户端提示 certificate has expired。

## 排查步骤
1. 用 `openssl s_client -connect host:443 -servername host` 查看证书有效期与链完整性
2. 确认是服务端证书还是中间 CA 证书过期
3. 检查证书与域名是否匹配、是否缺少中间证书
4. 确认自动续期任务（certbot / ACME）是否执行成功

## 处理建议
紧急替换证书并 reload；修复自动续期（定时任务、DNS 校验、权限）；增加到期前 30 天的监控告警。
