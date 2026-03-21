# Benchmark 评测系统

皇帝模拟器的 Agent 和 Memory 系统评测框架。

## 快速开始

```bash
# 运行所有评测
python -m benchmark

# 只评测 Agent 模块
python -m benchmark --module agent

# 只评测 Memory 模块
python -m benchmark --module memory

# 重复运行 3 次取平均值
python -m benchmark --repeat 3

# 指定输出报告路径
python -m benchmark --output reports/my-report.md
```

**输出：**
- JSON 原始数据：`benchmark/reports/raw/benchmark-YYYY-MM-DD-NNN.json`
- Markdown 报告：`benchmark/reports/benchmark-YYYY-MM-DD-HHMMSS.md`

## 配置 API Key

### 方式一：环境变量（推荐）

```bash
export BENCHMARK_LLM_API_KEY="sk-ant-xxx"
export BENCHMARK_LLM_PROVIDER="anthropic"      # 可选，默认 anthropic
export BENCHMARK_LLM_MODEL="claude-3-5-sonnet-20241022"  # 可选
export BENCHMARK_LLM_BASE_URL="https://..."    # 可选，自定义端点
```

### 方式二：配置文件

```bash
# 复制示例配置
cp config.benchmark.example.yaml config.benchmark.yaml

# 编辑配置文件
vim config.benchmark.yaml
```

```yaml
llm:
  provider: "anthropic"       # anthropic 或 openai
  model: "claude-3-5-sonnet-20241022"
  api_key: "sk-ant-xxx"       # 或留空，使用环境变量
  base_url: null              # 可选：自定义 API 端点
  timeout: 120
  max_retries: 3
```

**配置优先级：** 环境变量 > 配置文件 > 默认值

## 评测模块

### Agent 评测

| 评估器 | 说明 | 指标 | 目标 |
|--------|------|------|------|
| `intent_accuracy` | 意图识别准确率 | intent_accuracy | ≥90% |
| | | tool_success_rate | ≥95% |
| | | param_correctness | ≥85% |
| `response_perf` | 响应性能 | latency_p50 | ≤2000ms |
| | | latency_p95 | ≤5000ms |
| | | latency_p99 | ≤10000ms |
| `multi_agent` | 多 Agent 并发 | scaling_ratio | <Nx (sublinear) |

### Memory 评测

| 评估器 | 说明 | 指标 | 目标 |
|--------|------|------|------|
| `retrieval` | 记忆检索质量 | recall@5 | ≥80% |
| | | MRR | ≥70% |
| | | latency_p95 | ≤500ms |
| `compression` | 上下文压缩保真 | keyword_retention | ≥70% |
| | | compression_ratio | ≤30% |
| `cross_session` | 跨会话一致性 | consistency | ≥90% |

## 测试数据

测试用例位于 `benchmark/data/` 目录：

| 文件 | 说明 | 数量 |
|------|------|------|
| `intent_cases.json` | Agent 意图识别测试 | 55 cases |
| `memory_events.json` | Memory 检索测试 | 30 events, 20 queries |

### intent_cases.json 结构

```json
{
  "cases": [
    {
      "id": "query_001",
      "category": "query",           // query | action | dialog | edge
      "input": "直隶省今年的税收情况如何？",
      "must_have_tools": ["query_tax"],
      "nice_to_have_tools": [],
      "must_have_args": {},
      "expected_keywords": ["直隶", "税收"]
    }
  ]
}
```

### memory_events.json 结构

```json
{
  "inject_events": [/* 预注入的事件 */],
  "test_queries": [
    {
      "id": "q01",
      "query": "直隶省的税收有多少？",
      "relevant_event_ids": ["e001", "e021"],
      "difficulty": "easy"  // easy | medium | hard
    }
  ]
}
```

## 目录结构

```
benchmark/
├── __main__.py          # CLI 入口
├── config.py            # 配置加载
├── runner.py            # 评测运行器
├── models.py            # 数据模型
├── report.py            # Markdown 报告生成
├── metrics_hook.py      # LLM 指标收集
│
├── agent/               # Agent 评测模块
│   ├── intent_accuracy.py   # 意图识别
│   ├── response_perf.py     # 响应性能
│   └── multi_agent.py       # 并发性能
│
├── memory/              # Memory 评测模块
│   ├── retrieval.py         # 检索质量
│   ├── compression.py       # 压缩保真
│   └── cross_session.py     # 跨会话一致性
│
├── data/                # 测试数据
│   ├── intent_cases.json
│   └── memory_events.json
│
└── reports/             # 评测报告
    ├── raw/             # JSON 原始数据
    └── *.md             # Markdown 报告
```

## 指标解读

### 意图识别 (Intent Accuracy)

- **intent_accuracy**: Agent 正确识别用户意图并调用正确工具的比例
- **tool_success_rate**: 工具调用执行成功率
- **param_correctness**: 工具参数提取准确率

### 响应性能 (Response Performance)

- **latency_p50/p95/p99**: 响应延迟的百分位数
- **llm_call_count**: 单次请求的 LLM 调用次数
- **total_tokens**: Token 消耗总量

### 检索质量 (Retrieval)

- **Recall@5**: 前 5 个结果中相关事件的召回率
- **MRR (Mean Reciprocal Rank)**: 第一个相关结果的排名倒数的平均值

### 压缩保真 (Compression)

- **keyword_retention**: 压缩后关键词保留率
- **compression_ratio**: 压缩后 token 数 / 原始 token 数

## 待完善功能

> ⚠️ **Agent 评测已完成集成**，Memory 评测仍为占位符。

| 模块 | 状态 | 说明 |
|------|------|--------|
| `intent_accuracy` | ✅ 已集成 | 调用 `/api/benchmark/agent/chat` 验证 tool 调用 |
| `response_perf` | ✅ 已集成 | 真实 API 调用测量延迟 |
| `multi_agent` | ✅ 已集成 | 并发调用多个 Agent 测量扩展性 |
| `retrieval` | 🟡 占位符 | 调用实际 MemoryRetriever |
| `compression` | 🟡 占位符 | 调用实际压缩逻辑 |
| `cross_session` | 🟡 占位符 | 真实跨会话查询 |

### 环境要求

运行 Agent 评测前，确保后端服务已启动：

```bash
# 启动后端（默认端口 8000）
uv run simu-emperor --port 8000

# 或指定评测 API 地址
export BENCHMARK_API_URL="http://localhost:8000"
```

### 未来计划

1. **Phase 1** (Agent): ✅ 完成 - 集成真实 Agent 系统
2. **Phase 1** (Memory): 待实现 - 集成真实 Memory 系统
3. **Phase 2**: 添加角色扮演评测（基于 `soul.md`）
4. **Phase 3**: 添加行为偏差评测（隐瞒、推诿检测）
5. **Phase 4**: 添加多 Agent 协作场景评测

## 扩展测试用例

### 添加意图测试

编辑 `benchmark/data/intent_cases.json`：

```json
{
  "id": "custom_001",
  "category": "action",
  "input": "把江南的税率提高两成",
  "must_have_tools": ["adjust_tax_rate"],
  "must_have_args": {"rate": 0.2},
  "expected_keywords": ["江南", "税率"]
}
```

### 添加 Memory 测试

编辑 `benchmark/data/memory_events.json`，添加 `inject_events` 和 `test_queries`。

## 常见问题

**Q: 报告中指标全是 100% 或 0%？**
A: 当前评测器使用占位符实现，返回固定值。需要集成真实系统后才能获得准确数据。

**Q: 如何添加新的评测维度？**
A: 在 `agent/` 或 `memory/` 目录下创建新的评估器，继承相同模式，然后在 `runner.py` 中注册。

**Q: 评测报告保存在哪里？**
A: JSON 原始数据保存在 `benchmark/reports/raw/`，Markdown 报告保存在 `benchmark/reports/`。
