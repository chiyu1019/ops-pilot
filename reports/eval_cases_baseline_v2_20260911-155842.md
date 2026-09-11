# 可控场景评测报告（baseline_v2 · 20260911-155842）

- 用例数：**34**
- 严格证据校验通过率：**100.00%**（34/34）
- 证据覆盖率（全部用例）：**100.00%**
- 证据覆盖率（有结论的用例）：**100.00%**
- 证据不足场景正确降级率：0.00%（4 例）
- 平均 Token：23728.9（总 806782）
- 平均 LLM 调用：9.65　平均工具调用：3.41　平均节点数：0
- 平均耗时：82.79s

| 用例 | 场景 | 期望校验 | 实际通过 | 状态 | 覆盖率 | Token | 耗时(s) |
|---|---|---|---|---|---|---|---|
| cpu_high-01 | cpu_high | 通过 | ✅ | verified | 100.0% | 19801 | 78.56 |
| cpu_high-02 | cpu_high | 通过 | ✅ | verified | 100.0% | 15560 | 72.75 |
| cpu_high-03 | cpu_high | 通过 | ✅ | verified | 100.0% | 32196 | 144.0 |
| cpu_high-04 | cpu_high | 通过 | ✅ | verified | 100.0% | 13121 | 74.71 |
| cpu_high-05 | cpu_high | 通过 | ✅ | verified | 100.0% | 18904 | 47.87 |
| cpu_high-06 | cpu_high | 通过 | ✅ | verified | 100.0% | 17717 | 61.65 |
| cpu_high-07 | cpu_high | 通过 | ✅ | verified | 100.0% | 17777 | 52.19 |
| memory_high-01 | memory_high | 通过 | ✅ | verified | 100.0% | 18879 | 57.12 |
| memory_high-02 | memory_high | 通过 | ✅ | verified | 100.0% | 24422 | 72.92 |
| memory_high-03 | memory_high | 通过 | ✅ | verified | 100.0% | 18510 | 48.35 |
| memory_high-04 | memory_high | 通过 | ✅ | verified | 100.0% | 25003 | 87.01 |
| memory_high-05 | memory_high | 通过 | ✅ | verified | 100.0% | 19898 | 56.91 |
| memory_high-06 | memory_high | 通过 | ✅ | verified | 100.0% | 18342 | 57.3 |
| disk_high-01 | disk_high | 通过 | ✅ | verified | 100.0% | 24555 | 69.62 |
| disk_high-02 | disk_high | 通过 | ✅ | verified | 100.0% | 18719 | 61.45 |
| disk_high-03 | disk_high | 通过 | ✅ | verified | 100.0% | 17580 | 61.39 |
| disk_high-04 | disk_high | 通过 | ✅ | verified | 100.0% | 17002 | 43.57 |
| disk_high-05 | disk_high | 通过 | ✅ | verified | 100.0% | 16934 | 52.92 |
| disk_high-06 | disk_high | 通过 | ✅ | verified | 100.0% | 16345 | 64.27 |
| service_unavailable-01 | service_unavailable | 通过 | ✅ | verified | 100.0% | 36080 | 129.52 |
| service_unavailable-02 | service_unavailable | 通过 | ✅ | verified | 100.0% | 38988 | 137.8 |
| service_unavailable-03 | service_unavailable | 通过 | ✅ | verified | 100.0% | 38858 | 134.15 |
| service_unavailable-04 | service_unavailable | 通过 | ✅ | verified | 100.0% | 43496 | 174.73 |
| service_unavailable-05 | service_unavailable | 通过 | ✅ | verified | 100.0% | 28310 | 98.72 |
| service_unavailable-06 | service_unavailable | 通过 | ✅ | verified | 100.0% | 25322 | 99.42 |
| slow_response-01 | slow_response | 通过 | ✅ | verified | 100.0% | 32470 | 119.36 |
| slow_response-02 | slow_response | 通过 | ✅ | verified | 100.0% | 39949 | 148.86 |
| slow_response-03 | slow_response | 通过 | ✅ | verified | 100.0% | 38969 | 127.53 |
| slow_response-04 | slow_response | 通过 | ✅ | verified | 100.0% | 35197 | 126.92 |
| slow_response-05 | slow_response | 通过 | ✅ | verified | 100.0% | 38132 | 122.84 |
| no_evidence-01 | no_evidence | 降级 | ✅ | verified | 100.0% | 9836 | 33.19 |
| no_evidence-02 | no_evidence | 降级 | ✅ | verified | 100.0% | 10090 | 35.48 |
| no_evidence-03 | no_evidence | 降级 | ✅ | verified | 100.0% | 9892 | 33.49 |
| no_evidence-04 | no_evidence | 降级 | ✅ | verified | 100.0% | 9928 | 28.34 |