# JVM CPU 占用优化参数

## 常用参数
- `-XX:ActiveProcessorCount`：限制 JVM 感知的 CPU 核数
- `-XX:+UseG1GC` / `-XX:MaxGCPauseMillis`：GC 策略与停顿目标
- `-XX:ParallelGCThreads`：并行 GC 线程数

## 诊断工具
jstat -gcutil、jstack、async-profiler 火焰图。

## 优化建议
减少对象分配、避免大对象、合理设置堆大小与 GC 线程数。

本文档面向 JVM 调优，不包含监控告警的处置流程。
