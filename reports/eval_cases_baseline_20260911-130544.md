# 可控场景评测报告（baseline · 20260911-130544）

- 用例数：**34**
- 严格证据校验通过率：**50.00%**（17/34）
- 证据覆盖率（全部用例）：**50.00%**
- 证据覆盖率（有结论的用例）：**100.00%**
- 证据不足场景正确降级率：0.00%（4 例）
- 平均 Token：31836.7（总 700407）
- 平均 LLM 调用：8.68　平均工具调用：4.88　平均节点数：0
- 平均耗时：106.25s

| 用例 | 场景 | 期望校验 | 实际通过 | 状态 | 覆盖率 | Token | 耗时(s) |
|---|---|---|---|---|---|---|---|
| cpu_high-01 | cpu_high | 通过 | ✅ | verified | 100.0% | 16740 | 94.08 |
| cpu_high-02 | cpu_high | 通过 | ✅ | verified | 100.0% | 51301 | 219.27 |
| cpu_high-03 | cpu_high | 通过 | ✅ | verified | 100.0% | 40870 | 205.72 |
| cpu_high-04 | cpu_high | 通过 | ✅ | verified | 100.0% | 35081 | 152.57 |
| cpu_high-05 | cpu_high | 通过 | ✅ | verified | 100.0% | 38863 | 264.02 |
| cpu_high-06 | cpu_high | 通过 | ✅ | verified | 100.0% | 34249 | 173.92 |
| cpu_high-07 | cpu_high | 通过 | ✅ | verified | 100.0% | 47330 | 257.19 |
| memory_high-01 | memory_high | 通过 | ✅ | verified | 100.0% | 41217 | 229.65 |
| memory_high-02 | memory_high | 通过 | ✅ | verified | 100.0% | 27053 | 129.16 |
| memory_high-03 | memory_high | 通过 | ✅ | verified | 100.0% | 42076 | 233.85 |
| memory_high-04 | memory_high | 通过 | ✅ | verified | 100.0% | 38018 | 176.42 |
| memory_high-05 | memory_high | 通过 | ✅ | verified | 100.0% | 51765 | 319.16 |
| memory_high-06 | memory_high | 通过 | ✅ | verified | 100.0% | 41536 | 210.12 |
| disk_high-01 | disk_high | 通过 | ✅ | verified | 100.0% | 41769 | 165.13 |
| disk_high-02 | disk_high | 通过 | ✅ | verified | 100.0% | 36726 | 195.7 |
| disk_high-03 | disk_high | 通过 | ✅ | verified | 100.0% | 41077 | 189.85 |
| disk_high-04 | disk_high | 通过 | ✅ | verified | 100.0% | 37767 | 204.21 |
| disk_high-05 | disk_high | 通过 | ❌ | error | 0.0% | 6352 | 22.26 |
| disk_high-06 | disk_high | 通过 | ❌ | error | 0.0% | 7259 | 22.19 |
| service_unavailable-01 | service_unavailable | 通过 | ❌ | error | 0.0% | 0 | 8.7 |
| service_unavailable-02 | service_unavailable | 通过 | ❌ | error | 0.0% | 0 | 8.7 |
| service_unavailable-03 | service_unavailable | 通过 | ❌ | error | 0.0% | 0 | 4.54 |
| service_unavailable-04 | service_unavailable | 通过 | ❌ | error | 0.0% | 0 | 4.54 |
| service_unavailable-05 | service_unavailable | 通过 | ❌ | error | 0.0% | 0 | 8.9 |
| service_unavailable-06 | service_unavailable | 通过 | ❌ | error | 0.0% | 0 | 8.89 |
| slow_response-01 | slow_response | 通过 | ❌ | error | 0.0% | 0 | 8.69 |
| slow_response-02 | slow_response | 通过 | ❌ | error | 0.0% | 7011 | 22.18 |
| slow_response-03 | slow_response | 通过 | ❌ | error | 0.0% | 0 | 8.65 |
| slow_response-04 | slow_response | 通过 | ❌ | error | 0.0% | 0 | 8.55 |
| slow_response-05 | slow_response | 通过 | ❌ | error | 0.0% | 0 | 7.03 |
| no_evidence-01 | no_evidence | 降级 | ❌ | error | 0.0% | 8310 | 20.43 |
| no_evidence-02 | no_evidence | 降级 | ❌ | error | 0.0% | 0 | 7.01 |
| no_evidence-03 | no_evidence | 降级 | ❌ | error | 0.0% | 8037 | 14.65 |
| no_evidence-04 | no_evidence | 降级 | ❌ | error | 0.0% | 0 | 6.53 |