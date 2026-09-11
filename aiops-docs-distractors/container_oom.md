# 容器 OOM 处理方案

## 现象
容器被 kill，dmesg 或事件中出现 OOMKilled。

## 排查步骤
1. `docker inspect` 查看 OOMKilled 标记与内存限制
2. 查看 cgroup 内存统计 memory.max_usage_in_bytes
3. 分析应用内存分布：堆内存、直接内存、线程栈、native 内存
4. 检查是否存在内存泄漏或一次性加载大数据

## 处理建议
合理设置容器内存 limit 与 JVM 堆比例（如堆占 limit 的 60%-70%）、优化批处理大小、修复泄漏、必要时扩容。
