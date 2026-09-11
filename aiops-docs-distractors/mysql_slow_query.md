# MySQL 慢查询治理方案

## 现象
数据库 CPU 使用率升高，业务接口 P99 延迟上涨，慢查询日志数量激增。

## 排查步骤
### 步骤1：开启并分析慢查询日志
设置 slow_query_log=ON、long_query_time=1，用 pt-query-digest 汇总 TOP SQL。

### 步骤2：分析执行计划
对 TOP SQL 执行 EXPLAIN，关注 type（ALL 表示全表扫描）、rows、Extra 中的 Using filesort / Using temporary。

### 步骤3：检查索引
确认 WHERE、ORDER BY、JOIN 字段是否命中索引，注意最左前缀原则与索引选择性。

### 步骤4：检查锁等待
查询 information_schema.innodb_trx 与 performance_schema.data_lock_waits 定位锁冲突。

## 常见原因
1. 缺少合适索引导致全表扫描
2. 深分页（LIMIT 100000, 20）性能极差
3. 大事务长时间持有行锁
4. 统计信息过期导致优化器选错执行计划

## 处理建议
补充联合索引、改写深分页为游标分页、拆分大事务、定期 ANALYZE TABLE。
