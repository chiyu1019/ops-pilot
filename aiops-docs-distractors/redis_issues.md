# Redis 常见故障处理

## 内存告警
maxmemory 达到上限后触发淘汰策略。检查 `INFO memory` 的 used_memory_human 与 maxmemory_policy：
- noeviction：写入直接报错
- allkeys-lru：淘汰任意键，可能丢失热点数据

## 连接数打满
`INFO clients` 中 connected_clients 接近 maxclients 时，新连接被拒绝。常见原因是客户端未使用连接池或存在连接泄漏。

## 大 key 与热 key
用 `redis-cli --bigkeys` 扫描大 key；大 key 会造成单分片内存倾斜与阻塞。热 key 会导致单节点 QPS 打满，可通过本地缓存或多级缓存缓解。

## 慢命令
`SLOWLOG GET 10` 查看慢命令。避免在生产使用 KEYS、FLUSHALL、HGETALL 大 hash 等阻塞命令，改用 SCAN 渐进遍历。

## 持久化
RDB 快照频繁触发 fork 会造成延迟抖动；AOF everysec 在故障时最多丢失 1 秒数据。
