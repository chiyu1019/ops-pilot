# 网络问题排查手册

## 基础连通性
- ping 判断三层可达性
- telnet / nc 判断端口可达性
- traceroute / mtr 定位链路丢包节点

## DNS 问题
nslookup / dig 验证解析结果；注意 DNS 缓存与 TTL；容器环境需检查 resolv.conf 与 CoreDNS。

## 丢包与延迟
用 mtr 观察每跳丢包率；结合 tcpdump 抓包分析重传（tcp.analysis.retransmission）。

## 连接数耗尽
`ss -s`、`netstat -an | wc -l` 查看连接数；大量 TIME_WAIT 可开启 tcp_tw_reuse 缓解。

## 带宽打满
iftop / nload 观察实时带宽；定位大流量来源后限流或扩容。
