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

## 架构

Benchmark 模块直接调用 Application 层服务（`ApplicationServices`），**不依赖 Web 服务器**。

```
benchmark/
├── __main__.py          # CLI 入口
├── config.py            # 配置加载（BenchmarkConfig）
├── context.py           # BenchmarkContext — 服务容器（管理 ApplicationServices 生命周期）
├── base.py              # BaseEvaluator — 共享基类（懒加载 BenchmarkContext）
├── runner.py            # BenchmarkRunner — 评测运行器
├── models.py            # 数据模型（MetricResult, CaseDetail, ModuleResult）
├── report.py            # Markdown 报告生成
├── metrics_hook.py      # LLM 指标收集
│
├── agent/               # Agent 评测模块
│   ├── intent_accuracy.py   # 意图识别
│   └── response_perf.py     # 响应性能
│
├── memory/              # Memory 评测模块
│   ├── retrieval.py         # 检索质量（TwoLevelSearcher）
│   ├── compression.py       # 压缩保真（ContextManager.slide_window）
│   └── cross_session.py     # 跨会话一致性（Jaccard similarity）
│
├── data/                # 测试数据
│   ├── intent_cases.json
│   └── memory_events.json
│
└── reports/             # 评测报告
    └── *.md
```

### BenchmarkContext

`BenchmarkContext` 是核心服务容器：

1. 在临时目录中创建隔离的游戏环境
2. 使用 `ApplicationServices.create()` 初始化所有服务
3. 仅初始化 `governor_zhili` 作为测试 Agent
4. 数据库使用 `:memory:` 避免文件 I/O

主要方法：
- `send_message(message)` — 发送聊天消息给 Agent，收集响应和工具调用
- `inject_memory_events(session_id, events)` — 注入测试事件到 tape
- `retrieve_memory(query)` — 执行两级记忆检索
- `get_context_manager(session_id)` — 获取 ContextManager 用于压缩测试

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
cp config.benchmark.example.yaml config.benchmark.yaml
vim config.benchmark.yaml
```

```yaml
llm:
  provider: "anthropic"
  model: "claude-3-5-sonnet-20241022"
  api_key: "sk-ant-xxx"
  base_url: null
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

| 文件 | 说明 |
|------|------|
| `intent_cases.json` | Agent 意图识别测试用例 |
| `memory_events.json` | Memory 检索测试（注入事件 + 查询） |

## 扩展

添加新评估器：
1. 在 `agent/` 或 `memory/` 下创建新文件
2. 继承 `BaseEvaluator`
3. 实现 `evaluate() -> ModuleResult`
4. 在 `runner.py` 的对应方法中注册
