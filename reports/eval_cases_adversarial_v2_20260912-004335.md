# 可控场景评测报告（adversarial_v2 · 20260912-004335）

- 用例数：**10**
- 严格证据校验通过率：**90.00%**（9/10）
- 证据覆盖率（全部用例）：**90.00%**
- 证据覆盖率（有结论的用例）：**100.00%**
- 证据不足场景正确降级率：20.00%（5 例）
- 平均 Token：21015.2（总 210152）
- 平均 LLM 调用：9.5　平均工具调用：3.5　平均节点数：0
- 平均耗时：70.54s

| 用例 | 场景 | 期望校验 | 实际通过 | 状态 | 覆盖率 | Token | 耗时(s) |
|---|---|---|---|---|---|---|---|
| conflict-01 | conflict | 降级 | ✅ | verified | 100.0% | 24692 | 72.67 |
| conflict-02 | conflict | 降级 | ✅ | verified | 100.0% | 11849 | 54.15 |
| conflict-03 | conflict | 降级 | ✅ | verified | 100.0% | 13483 | 52.19 |
| tool_fail-01 | tool_fail | 降级 | ✅ | verified | 100.0% | 20292 | 69.28 |
| tool_fail-02 | tool_fail | 降级 | ❌ | safe_report | 0.0% | 28311 | 101.83 |
| misleading-01 | misleading | 通过 | ✅ | verified | 100.0% | 13098 | 47.01 |
| misleading-02 | misleading | 通过 | ✅ | verified | 100.0% | 14478 | 39.82 |
| multi_alert-01 | multi_alert | 通过 | ✅ | verified | 100.0% | 24526 | 87.18 |
| multi_alert-02 | multi_alert | 通过 | ✅ | verified | 100.0% | 35846 | 104.7 |
| sparse-01 | sparse | 通过 | ✅ | verified | 100.0% | 23577 | 76.54 |