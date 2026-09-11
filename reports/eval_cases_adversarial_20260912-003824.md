# 可控场景评测报告（adversarial · 20260912-003824）

- 用例数：**10**
- 严格证据校验通过率：**0.00%**（0/10）
- 证据覆盖率（全部用例）：**0.00%**
- 证据覆盖率（有结论的用例）：**0.00%**
- 证据不足场景正确降级率：100.00%（5 例）
- 平均 Token：17717.1（总 177171）
- 平均 LLM 调用：9.4　平均工具调用：5　平均节点数：0
- 平均耗时：72.68s

| 用例 | 场景 | 期望校验 | 实际通过 | 状态 | 覆盖率 | Token | 耗时(s) |
|---|---|---|---|---|---|---|---|
| conflict-01 | conflict | 降级 | ❌ | safe_report | 0.0% | 16059 | 73.43 |
| conflict-02 | conflict | 降级 | ❌ | safe_report | 0.0% | 18192 | 92.49 |
| conflict-03 | conflict | 降级 | ❌ | safe_report | 0.0% | 18185 | 86.79 |
| tool_fail-01 | tool_fail | 降级 | ❌ | safe_report | 0.0% | 20317 | 78.45 |
| tool_fail-02 | tool_fail | 降级 | ❌ | safe_report | 0.0% | 16066 | 68.97 |
| misleading-01 | misleading | 通过 | ❌ | safe_report | 0.0% | 16908 | 69.97 |
| misleading-02 | misleading | 通过 | ❌ | safe_report | 0.0% | 20924 | 76.75 |
| multi_alert-01 | multi_alert | 通过 | ❌ | safe_report | 0.0% | 13091 | 53.84 |
| multi_alert-02 | multi_alert | 通过 | ❌ | safe_report | 0.0% | 13066 | 56.93 |
| sparse-01 | sparse | 通过 | ❌ | safe_report | 0.0% | 24363 | 69.17 |