# 慢查询与索引设计规范

## 索引设计原则
- 最左前缀原则
- 高选择性字段优先
- 避免在索引列上使用函数

## 联合索引示例
`ALTER TABLE orders ADD INDEX idx_user_status_created (user_id, status, created_at);`

## 覆盖索引
让查询字段全部包含在索引中，避免回表。

本文档聚焦索引设计，不包含响应时间告警的排查流程与优先级。
