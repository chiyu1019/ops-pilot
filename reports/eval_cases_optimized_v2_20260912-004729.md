# 可控场景评测报告（optimized_v2 · 20260912-004729）

- 用例数：**12**
- 严格证据校验通过率：**83.33%**（10/12）
- 证据覆盖率（全部用例）：**83.33%**
- 证据覆盖率（有结论的用例）：**100.00%**
- 证据不足场景正确降级率：0.00%（0 例）
- 平均 Token：18138.7（总 217664）
- 平均 LLM 调用：6.17　平均工具调用：2.83　平均节点数：0
- 平均耗时：67.13s

| 用例 | 场景 | 期望校验 | 实际通过 | 状态 | 覆盖率 | Token | 耗时(s) |
|---|---|---|---|---|---|---|---|
| cpu_high-01 | cpu_high | 通过 | ✅ | verified | 100.0% | 16483 | 61.11 |
| cpu_high-02 | cpu_high | 通过 | ✅ | verified | 100.0% | 12680 | 54.58 |
| cpu_high-03 | cpu_high | 通过 | ✅ | verified | 100.0% | 13210 | 63.33 |
| memory_high-01 | memory_high | 通过 | ✅ | verified | 100.0% | 16171 | 71.43 |
| memory_high-02 | memory_high | 通过 | ❌ | safe_report | 0.0% | 25223 | 91.31 |
| memory_high-03 | memory_high | 通过 | ✅ | verified | 100.0% | 14352 | 61.59 |
| disk_high-01 | disk_high | 通过 | ✅ | verified | 100.0% | 28081 | 120.49 |
| disk_high-02 | disk_high | 通过 | ✅ | verified | 100.0% | 16901 | 43.55 |
| disk_high-03 | disk_high | 通过 | ✅ | verified | 100.0% | 14393 | 56.5 |
| service_unavailable-01 | service_unavailable | 通过 | ❌ | safe_report | 0.0% | 29325 | 91.39 |
| service_unavailable-02 | service_unavailable | 通过 | ✅ | verified | 100.0% | 16328 | 46.67 |
| service_unavailable-03 | service_unavailable | 通过 | ✅ | verified | 100.0% | 14517 | 43.57 |