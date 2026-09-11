# 可控场景评测报告（optimized_v3 · 20260912-005127）

- 用例数：**12**
- 严格证据校验通过率：**91.67%**（11/12）
- 证据覆盖率（全部用例）：**91.67%**
- 证据覆盖率（有结论的用例）：**100.00%**
- 证据不足场景正确降级率：0.00%（0 例）
- 平均 Token：17471（总 209652）
- 平均 LLM 调用：5.67　平均工具调用：2.67　平均节点数：0
- 平均耗时：63.84s

| 用例 | 场景 | 期望校验 | 实际通过 | 状态 | 覆盖率 | Token | 耗时(s) |
|---|---|---|---|---|---|---|---|
| cpu_high-01 | cpu_high | 通过 | ✅ | verified | 100.0% | 17299 | 64.43 |
| cpu_high-02 | cpu_high | 通过 | ✅ | verified | 100.0% | 13330 | 62.42 |
| cpu_high-03 | cpu_high | 通过 | ✅ | verified | 100.0% | 14280 | 72.36 |
| memory_high-01 | memory_high | 通过 | ✅ | verified | 100.0% | 12184 | 56.63 |
| memory_high-02 | memory_high | 通过 | ✅ | verified | 100.0% | 28091 | 100.83 |
| memory_high-03 | memory_high | 通过 | ✅ | verified | 100.0% | 15809 | 64.15 |
| disk_high-01 | disk_high | 通过 | ✅ | verified | 100.0% | 16424 | 55.72 |
| disk_high-02 | disk_high | 通过 | ❌ | safe_report | 0.0% | 28673 | 98.16 |
| disk_high-03 | disk_high | 通过 | ✅ | verified | 100.0% | 16488 | 57.32 |
| service_unavailable-01 | service_unavailable | 通过 | ✅ | verified | 100.0% | 17032 | 45.1 |
| service_unavailable-02 | service_unavailable | 通过 | ✅ | verified | 100.0% | 14540 | 44.33 |
| service_unavailable-03 | service_unavailable | 通过 | ✅ | verified | 100.0% | 15502 | 44.68 |