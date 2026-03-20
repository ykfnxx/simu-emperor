# Benchmark 评测报告

**生成时间**: 2026-03-20 23:38:45
**模型**: claude-3-5-sonnet-20241022
**Provider**: anthropic

## 1. 执行概要

| 模块 | 耗时 | 状态 |
|------|------|------|
| intent_accuracy | 0.00s | ✅ |
| response_perf | 0.06s | ✅ |
| multi_agent | 0.16s | ✅ |
| retrieval | 0.00s | ❌ |
| compression | 0.00s | ❌ |
| cross_session | 0.00s | ✅ |
| **总计** | **0.22s** | |

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
| latency_p50 | 12ms | ≤2000ms | ✅ |
| latency_p95 | 12ms | ≤5000ms | ✅ |
| latency_p99 | 12ms | ≤10000ms | ✅ |
| llm_call_count | 5.00 | 100.00 | ✅ |
| total_tokens | 0.00 | 100000.00 | ✅ |

### 2.3 多 Agent 并发

| 指标 | 值 | 目标 | 状态 |
|------|-----|------|------|
| latency_2_agents | 52ms | ≤83ms | ✅ |
| scaling_ratio_2 | 1.00 | 2.00 | ✅ |
| latency_5_agents | 52ms | ≤207ms | ✅ |
| scaling_ratio_5 | 1.01 | 5.00 | ✅ |
| latency_10_agents | 52ms | ≤415ms | ✅ |
| scaling_ratio_10 | 1.00 | 10.00 | ✅ |

## 3. 记忆系统评测

### 3.1 检索性能

| 指标 | 值 | 目标 | 状态 |
|------|-----|------|------|
| recall_at_5 | 0.0% | ≥80% | ❌ |
| mrr | 0.0% | ≥70% | ❌ |
| latency_p95 | 0ms | ≤500ms | ✅ |

### 3.2 压缩保真度

| 指标 | 值 | 目标 | 状态 |
|------|-----|------|------|
| keyword_retention_rate | 66.7% | ≥70% | ❌ |
| compression_ratio | 25.0% | ≥30% | ✅ |
| original_tokens | 8000.00 | 10000.00 | ✅ |
| compressed_tokens | 2000.00 | 3000.00 | ✅ |

### 3.3 跨会话一致性

| 指标 | 值 | 目标 | 状态 |
|------|-----|------|------|
| cross_session_consistency | 100.0% | ≥90% | ✅ |
| queries_tested | 3.00 | 10.00 | ✅ |

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
- **recall_at_5**: 严重低于目标 (0.0 < 64.0)，建议优先检查
- **mrr**: 严重低于目标 (0.0 < 56.0)，建议优先检查
- **latency_p95**: 达标，无需优化
- **keyword_retention_rate**: 略低于目标，建议优化
- **compression_ratio**: 达标，无需优化
- **original_tokens**: 达标，无需优化
- **compressed_tokens**: 达标，无需优化
- **cross_session_consistency**: 达标，无需优化
- **queries_tested**: 达标，无需优化