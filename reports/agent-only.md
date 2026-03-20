# Benchmark 评测报告

**生成时间**: 2026-03-20 23:39:34
**模型**: claude-3-5-sonnet-20241022
**Provider**: anthropic

## 1. 执行概要

| 模块 | 耗时 | 状态 |
|------|------|------|
| intent_accuracy | 0.00s | ✅ |
| response_perf | 0.06s | ✅ |
| multi_agent | 0.15s | ✅ |
| **总计** | **0.21s** | |

## 2. Agent 评测

### 2.1 意图识别准确率

| 指标 | 值 | 目标 | 状态 |
|------|-----|------|------|
| intent_accuracy | 100.0% | ≥90% | ✅ |
| tool_success_rate | 95.0% | ≥95% | ✅ |
| param_correctness | 90.0% | ≥85% | ✅ |

### 2.2 响应性能

| 指标 | 值 | 目标 | 状态 |
|------|-----|------|------|
| latency_p50 | 11ms | ≤2000ms | ✅ |
| latency_p95 | 11ms | ≤5000ms | ✅ |
| latency_p99 | 11ms | ≤10000ms | ✅ |
| llm_call_count | 5.00 | 100.00 | ✅ |
| total_tokens | 0.00 | 100000.00 | ✅ |

### 2.3 多 Agent 并发

| 指标 | 值 | 目标 | 状态 |
|------|-----|------|------|
| latency_2_agents | 51ms | ≤82ms | ✅ |
| scaling_ratio_2 | 1.00 | 2.00 | ✅ |
| latency_5_agents | 51ms | ≤205ms | ✅ |
| scaling_ratio_5 | 1.00 | 5.00 | ✅ |
| latency_10_agents | 51ms | ≤410ms | ✅ |
| scaling_ratio_10 | 1.00 | 10.00 | ✅ |

## 3. 记忆系统评测

暂无记忆系统评测结果

## 4. 优化建议

- **intent_accuracy**: 达标，无需优化
- **tool_success_rate**: 达标，无需优化
- **param_correctness**: 达标，无需优化
- **latency_p50**: 达标，无需优化
- **latency_p95**: 达标，无需优化
- **latency_p99**: 达标，无需优化
- **llm_call_count**: 达标，无需优化
- **total_tokens**: 达标，无需优化
- **latency_2_agents**: 达标，无需优化
- **scaling_ratio_2**: 达标，无需优化
- **latency_5_agents**: 达标，无需优化
- **scaling_ratio_5**: 达标，无需优化
- **latency_10_agents**: 达标，无需优化
- **scaling_ratio_10**: 达标，无需优化