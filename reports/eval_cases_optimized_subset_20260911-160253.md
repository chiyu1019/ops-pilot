# 可控场景评测报告（optimized_subset · 20260911-160253）

- 用例数：**12**
- 严格证据校验通过率：**91.67%**（11/12）
- 证据覆盖率（全部用例）：**97.92%**
- 证据覆盖率（有结论的用例）：**97.92%**
- 证据不足场景正确降级率：0.00%（0 例）
- 平均 Token：15170.9（总 182051）
- 平均 LLM 调用：5.08　平均工具调用：2.5　平均节点数：0
- 平均耗时：62.73s

| 用例 | 场景 | 期望校验 | 实际通过 | 状态 | 覆盖率 | Token | 耗时(s) |
|---|---|---|---|---|---|---|---|
| cpu_high-01 | cpu_high | 通过 | ✅ | verified | 100.0% | 14596 | 70.97 |
| cpu_high-02 | cpu_high | 通过 | ✅ | verified | 100.0% | 10823 | 59.24 |
| cpu_high-03 | cpu_high | 通过 | ✅ | verified | 100.0% | 14219 | 65.08 |
| memory_high-01 | memory_high | 通过 | ✅ | verified | 100.0% | 15160 | 57.32 |
| memory_high-02 | memory_high | 通过 | ✅ | verified | 100.0% | 20146 | 75.98 |
| memory_high-03 | memory_high | 通过 | ✅ | verified | 100.0% | 15495 | 64.7 |
| disk_high-01 | disk_high | 通过 | ✅ | verified | 100.0% | 13306 | 51.85 |
| disk_high-02 | disk_high | 通过 | ✅ | verified | 100.0% | 14438 | 55.1 |
| disk_high-03 | disk_high | 通过 | ✅ | verified | 100.0% | 14869 | 63.88 |
| service_unavailable-01 | service_unavailable | 通过 | ✅ | verified | 100.0% | 12075 | 41.76 |
| service_unavailable-02 | service_unavailable | 通过 | ✅ | verified | 100.0% | 14764 | 57.45 |
| service_unavailable-03 | service_unavailable | 通过 | ❌ | hypothesis | 75.0% | 22160 | 89.48 |