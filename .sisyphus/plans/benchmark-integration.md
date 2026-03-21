# Benchmark 真实模块集成计划

## TL;DR

> **Quick Summary**: 将 benchmark 评估器从占位符替换为真实 Agent 集成，新增 Benchmark API 端点，实现意图识别、响应性能、多 Agent 并发三项评测。
> 
> **Deliverables**:
> - 新增 `/api/benchmark/*` REST API 端点
> - 修改 `intent_cases.json` 适配现有 Agent 工具
> - 实现真实 `intent_accuracy` 评估器
> - 实现真实 `response_perf` 评估器
> - 实现真实 `multi_agent` 评估器
> - 新增隔离测试环境配置
> - TDD 测试用例
> 
> **Estimated Effort**: Medium
> **Parallel Execution**: YES - 3 waves
> **Critical Path**: 隔离环境 → Benchmark API → 评估器实现

---

## Context

### Original Request
用户要求将 benchmark 系统从占位符实现替换为真实 Agent/Memory 集成，实现真正的评测功能。

### Interview Summary
**Key Discussions**:
- **优先级**: Agent 评测优先，Memory 评测后续（Phase 2）
- **集成方式**: 服务接口，新增 `/api/benchmark/*` 端点
- **工具对齐**: 修改 benchmark 测试用例适配现有工具，不扩展 Agent 工具集
- **测试环境**: 需要隔离（独立测试数据库 `test_benchmark.db`）
- **开发模式**: TDD（先写测试，再实现）
- **LLM 成本**: 完整运行，不做采样

**Research Findings**:
- Agent 工具: `query_province_data`, `query_incidents`, `send_message` 等
- Memory 入口: `StructuredRetriever`, `ContextManager`
- intent_cases.json 有 55 个测试用例需要修改工具名称
- 现有 Web API 是异步的，benchmark 需要同步调用

### 工具映射方案

| Benchmark 旧工具 | 替换为 | 说明 |
|------------------|--------|------|
| `query_tax` | `query_province_data` | 查询税收数据 |
| `query_population` | `query_province_data` | 查询人口数据 |
| `query_incident` | `query_incidents` | 查询灾害事件 |
| `allocate_funds` | 移除 | 暂不支持，从 action 测试用例中移除 |
| `adjust_tax` | 移除 | 暂不支持，从 action 测试用例中移除 |
| `adjust_tax_rate` | 移除 | 暂不支持，从 action 测试用例中移除 |

---

## Work Objectives

### Core Objective
将 benchmark 评估器从占位符实现替换为真实 Agent 集成，实现可信赖的评测系统。

### Concrete Deliverables
- `config.benchmark.test.yaml` - 隔离测试环境配置
- `src/simu_emperor/adapters/web/benchmark_api.py` - Benchmark API 端点
- `benchmark/data/intent_cases.json` - 更新后的测试用例（工具名称映射）
- `benchmark/agent/intent_accuracy.py` - 真实意图识别评估器
- `benchmark/agent/response_perf.py` - 真实响应性能评估器
- `benchmark/agent/multi_agent.py` - 真实多 Agent 并发评估器
- `tests/benchmark/` - TDD 测试用例

### Definition of Done
- [ ] `python -m benchmark --module agent` 运行成功
- [ ] 所有 3 个 Agent 评估器返回真实数据（非占位符）
- [ ] 测试用例 100% 通过
- [ ] 隔离环境自动清理

### Must Have
- 新增 Benchmark API 端点 `/api/benchmark/agent/chat`
- 修改 intent_cases.json 适配现有工具
- 实现真实意图识别评测（调用 LLM，验证工具调用）
- 隔离测试环境（不污染生产数据）

### Must NOT Have (Guardrails)
- ❌ 不要修改 Agent 工具定义（不添加 allocate_funds 等）
- ❌ 不要修改核心 Agent 逻辑
- ❌ 不要影响现有 Web API 行为
- ❌ 不要在评测中使用生产数据库
- ❌ 不要在测试用例中保留不存在的工具名称

---

## Verification Strategy (MANDATORY)

### Test Decision
- **Infrastructure exists**: YES (pytest)
- **Automated tests**: YES (TDD)
- **Framework**: pytest + pytest-asyncio
- **TDD workflow**: RED (failing test) → GREEN (minimal impl) → REFACTOR

### QA Policy
Every task MUST include agent-executed QA scenarios.

- **API Testing**: Use Bash (curl) — Send HTTP requests, assert status + response fields
- **Benchmark Runner**: Use Bash (python -m benchmark) — Run benchmark, check exit code + output
- **Integration Testing**: Use Bash (pytest) — Run test suite, verify pass/fail

---

## Execution Strategy

### Parallel Execution Waves

```
Wave 1 (Foundation - 隔离环境 + 测试用例):
├── Task 1: 创建隔离测试环境配置 [quick]
├── Task 2: 修改 intent_cases.json 工具映射 [quick]
└── Task 3: 编写 API 测试用例 (TDD RED) [quick]

Wave 2 (Core - Benchmark API):
├── Task 4: 实现 /api/benchmark/agent/chat 端点 [unspecified-high]
├── Task 5: 实现 /api/benchmark/health 端点 [quick]
└── Task 6: 编写评估器测试用例 (TDD RED) [quick]

Wave 3 (Evaluators - 评估器实现):
├── Task 7: 实现 intent_accuracy 评估器 [deep]
├── Task 8: 实现 response_perf 评估器 [quick]
└── Task 9: 实现 multi_agent 评估器 [unspecified-high]

Wave FINAL (Verification):
├── Task F1: 运行完整 benchmark 验证
├── Task F2: 代码质量检查 (ruff + mypy)
└── Task F3: 文档更新 (README)
```

### Dependency Matrix

- **1-3**: — — 4-9, F1
- **4**: 1, 3 — 7, 8, 9
- **5**: 1 — F1
- **6**: 3, 4 — 7, 8, 9
- **7-9**: 4, 6 — F1

### Agent Dispatch Summary

- **Wave 1**: 3 tasks → `quick` x3
- **Wave 2**: 3 tasks → `unspecified-high` x1, `quick` x2
- **Wave 3**: 3 tasks → `deep` x1, `quick` x1, `unspecified-high` x1
- **FINAL**: 3 tasks → `quick` x2, `unspecified-low` x1

---

## TODOs

### Wave 1: Foundation（基础设施）

- [x] 1. 创建隔离测试环境配置

  **What to do**:
  - 创建 `config.benchmark.test.yaml`，配置独立测试数据库 `test_benchmark.db`
  - 配置独立数据目录 `data/benchmark_test/`
  - 添加环境变量支持 `BENCHMARK_TEST_MODE=true`

  **Must NOT do**:
  - 不要修改现有 `config.yaml` 或 `config.benchmark.yaml`
  - 不要在生产目录下创建测试数据

  **Recommended Agent Profile**:
  - **Category**: `quick`
    - Reason: 单文件配置创建，简单直接
  - **Skills**: []
    - 无特殊技能需求

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 1 (with Tasks 2, 3)
  - **Blocks**: Task 4, Task 5
  - **Blocked By**: None

  **References**:
  - `config.benchmark.example.yaml` - 配置文件格式参考
  - `config.yaml` - 现有配置结构

  **Acceptance Criteria**:
  - [ ] `config.benchmark.test.yaml` 文件存在
  - [ ] 包含 `database: test_benchmark.db` 配置
  - [ ] 包含 `data_dir: data/benchmark_test/` 配置

  **QA Scenarios**:
  ```
  Scenario: 配置文件验证
    Tool: Bash (cat)
    Steps:
      1. cat config.benchmark.test.yaml
      2. 验证包含 "test_benchmark.db"
      3. 验证包含 "benchmark_test"
    Expected Result: 文件存在且包含正确配置
    Evidence: .sisyphus/evidence/task-1-config-check.txt
  ```

  **Commit**: YES
  - Message: `feat(benchmark): add isolated test environment config`
  - Files: `config.benchmark.test.yaml`

- [x] 2. 修改 intent_cases.json 工具映射

  **What to do**:
  - 将 `query_tax` → `query_province_data`
  - 将 `query_population` → `query_province_data`
  - 将 `query_incident` → `query_incidents`
  - 移除 `allocate_funds`, `adjust_tax`, `adjust_tax_rate` 相关测试用例（标记为暂不支持）
  - 更新 `must_have_args` 适配新工具参数结构

  **Must NOT do**:
  - 不要保留不存在的工具名称
  - 不要添加新的测试用例（仅修改现有）

  **Recommended Agent Profile**:
  - **Category**: `quick`
    - Reason: JSON 文件修改，简单直接
  - **Skills**: []
    - 无特殊技能需求

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 1 (with Tasks 1, 3)
  - **Blocks**: Task 7
  - **Blocked By**: None

  **References**:
  - `benchmark/data/intent_cases.json` - 需要修改的文件
  - `src/simu_emperor/agents/tools/query_tools.py` - 查询工具定义（query_province_data 参数结构）
  - `src/simu_emperor/agents/tools/action_tools.py` - 动作工具定义

  **Acceptance Criteria**:
  - [ ] 所有 `must_have_tools` 中的工具名称已更新
  - [ ] action 类测试用例已移除或标记为 `skip`
  - [ ] `must_have_args` 参数结构适配新工具

  **QA Scenarios**:
  ```
  Scenario: 工具名称验证
    Tool: Bash (grep)
    Steps:
      1. grep -c "query_tax" benchmark/data/intent_cases.json
      2. grep -c "allocate_funds" benchmark/data/intent_cases.json
      3. grep -c "query_province_data" benchmark/data/intent_cases.json
    Expected Result: query_tax=0, allocate_funds=0, query_province_data>0
    Evidence: .sisyphus/evidence/task-2-tool-names.txt
  ```

  **Commit**: YES
  - Message: `feat(benchmark): update intent cases for real agent tools`
  - Files: `benchmark/data/intent_cases.json`

- [x] 3. 编写 API 测试用例 (TDD RED)

  **What to do**:
  - 创建 `tests/benchmark/test_benchmark_api.py`
  - 编写 `POST /api/benchmark/agent/chat` 的失败测试
  - 编写 `POST /api/benchmark/agent/chat` 的成功测试
  - 编写 `GET /api/benchmark/health` 的测试
  - 所有测试应为 RED 状态（API 尚未实现）

  **Must NOT do**:
  - 不要实现 API（仅编写测试）
  - 不要跳过测试用例

  **Recommended Agent Profile**:
  - **Category**: `quick`
    - Reason: 测试用例编写，结构清晰
  - **Skills**: []
    - 无特殊技能需求

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 1 (with Tasks 1, 2)
  - **Blocks**: Task 4, Task 6
  - **Blocked By**: None

  **References**:
  - `src/simu_emperor/adapters/web/server.py` - 现有 API 结构参考
  - `tests/` - 现有测试模式参考

  **Acceptance Criteria**:
  - [ ] `tests/benchmark/test_benchmark_api.py` 文件存在
  - [ ] `uv run pytest tests/benchmark/test_benchmark_api.py` 运行失败（RED 状态）
  - [ ] 包含至少 3 个测试用例

  **QA Scenarios**:
  ```
  Scenario: TDD RED 状态验证
    Tool: Bash (pytest)
    Steps:
      1. uv run pytest tests/benchmark/test_benchmark_api.py -v
      2. 检查输出包含 "FAILED" 或 "ERROR"
    Expected Result: 测试运行但失败（RED 状态）
    Evidence: .sisyphus/evidence/task-3-tdd-red.txt
  ```

  **Commit**: YES
  - Message: `test(benchmark): add API test cases (TDD RED)`
  - Files: `tests/benchmark/test_benchmark_api.py`

### Wave 2: Benchmark API

- [x] 4. 实现 /api/benchmark/agent/chat 端点

  **What to do**:
  - 创建 `src/simu_emperor/adapters/web/benchmark_api.py`
  - 实现 `POST /api/benchmark/agent/chat` 端点
  - 输入: `{ agent_id, message, session_id? }`
  - 输出: `{ response, tool_calls: [{name, args, result}], latency_ms, success }`
  - 同步调用 Agent，等待响应后返回
  - 收集 LLM 调用过程中的工具调用信息

  **Must NOT do**:
  - 不要修改现有 `/api/command` 或 `/api/chat` 端点
  - 不要使用 WebSocket（需要同步响应）
  - 不要绕过 AgentManager 直接实例化 Agent

  **Recommended Agent Profile**:
  - **Category**: `unspecified-high`
    - Reason: 需要深入理解 Agent 调用流程，涉及异步同步转换
  - **Skills**: []
    - 无特殊技能需求

  **Parallelization**:
  - **Can Run In Parallel**: NO (核心任务)
  - **Blocks**: Task 7, 8, 9
  - **Blocked By**: Task 1, Task 3

  **References**:
  - `src/simu_emperor/adapters/web/server.py` - FastAPI 端点结构
  - `src/simu_emperor/agents/agent.py:Agent._on_event()` - Agent 事件处理流程
  - `src/simu_emperor/agents/agent.py:Agent._process_event_with_llm()` - LLM 调用逻辑
  - `src/simu_emperor/agents/tools/tool_registry.py` - 工具调用机制

  **Acceptance Criteria**:
  - [ ] `POST /api/benchmark/agent/chat` 返回 200
  - [ ] 响应包含 `tool_calls` 数组
  - [ ] 响应包含 `latency_ms`
  - [ ] TDD 测试从 RED 变为 GREEN

  **QA Scenarios**:
  ```
  Scenario: API 端点调用成功
    Tool: Bash (curl)
    Steps:
      1. 启动服务器: uv run simu-emperor --config config.benchmark.test.yaml &
      2. curl -X POST http://localhost:8000/api/benchmark/agent/chat \
           -H "Content-Type: application/json" \
           -d '{"agent_id":"governor_zhili","message":"直隶省税收如何？"}'
      3. 验证响应包含 tool_calls 和 latency_ms
    Expected Result: HTTP 200, JSON 响应包含所需字段
    Evidence: .sisyphus/evidence/task-4-api-success.json
  ```

  **Commit**: YES
  - Message: `feat(api): add benchmark agent chat endpoint`
  - Files: `src/simu_emperor/adapters/web/benchmark_api.py`, `src/simu_emperor/adapters/web/server.py`

- [x] 5. 实现 /api/benchmark/health 端点

  **What to do**:
  - 实现 `GET /api/benchmark/health` 端点
  - 返回 benchmark 服务状态信息
  - 返回测试环境配置摘要

  **Recommended Agent Profile**:
  - **Category**: `quick`
    - Reason: 简单的健康检查端点
  - **Skills**: []

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 2 (with Task 4)
  - **Blocks**: Task F1
  - **Blocked By**: Task 1

  **References**:
  - `src/simu_emperor/adapters/web/server.py:health_check()` - 现有健康检查模式

  **Acceptance Criteria**:
  - [ ] `GET /api/benchmark/health` 返回 200
  - [ ] 响应包含 `status: "ok"` 和配置信息

  **QA Scenarios**:
  ```
  Scenario: 健康检查端点
    Tool: Bash (curl)
    Steps:
      1. curl http://localhost:8000/api/benchmark/health
      2. 验证 JSON 响应包含 status: "ok"
    Expected Result: HTTP 200, {"status": "ok", ...}
    Evidence: .sisyphus/evidence/task-5-health.json
  ```

  **Commit**: NO (groups with Task 4)

- [ ] 6. 编写评估器测试用例 (TDD RED)

  **What to do**:
  - 创建 `tests/benchmark/test_evaluators.py`
  - 编写 `test_intent_accuracy_real_evaluation()` 测试
  - 编写 `test_response_perf_real_latency()` 测试
  - 编写 `test_multi_agent_real_concurrency()` 测试
  - 所有测试应为 RED 状态（评估器尚未实现）

  **Recommended Agent Profile**:
  - **Category**: `quick`
    - Reason: 标准测试用例编写
  - **Skills**: []

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 2 (after Task 4)
  - **Blocks**: Task 7, 8, 9
  - **Blocked By**: Task 3, Task 4

  **References**:
  - `benchmark/agent/intent_accuracy.py` - 需要测试的评估器接口
  - `benchmark/agent/response_perf.py` - 需要测试的评估器接口

  **Acceptance Criteria**:
  - [ ] 测试文件存在
  - [ ] 运行测试失败（RED 状态）
  - [ ] 至少 3 个测试用例

  **QA Scenarios**:
  ```
  Scenario: TDD RED 状态验证
    Tool: Bash (pytest)
    Steps:
      1. uv run pytest tests/benchmark/test_evaluators.py -v
      2. 验证输出包含 "FAILED"
    Expected Result: 测试失败（RED）
    Evidence: .sisyphus/evidence/task-6-tdd-red.txt
  ```

  **Commit**: YES
  - Message: `test(benchmark): add evaluator test cases (TDD RED)`
  - Files: `tests/benchmark/test_evaluators.py`

### Wave 3: Evaluators（评估器实现）

- [ ] 7. 实现 intent_accuracy 评估器

  **What to do**:
  - 重写 `benchmark/agent/intent_accuracy.py` 的 `_evaluate_case()` 方法
  - 调用 `/api/benchmark/agent/chat` 端点
  - 验证返回的 `tool_calls` 是否匹配 `must_have_tools`
  - 验证 `tool_calls` 参数是否匹配 `must_have_args`
  - 计算真实的 intent_accuracy, tool_success_rate, param_correctness

  **Must NOT do**:
  - 不要返回硬编码的占位符值
  - 不要跳过 `must_have_tools` 验证

  **Recommended Agent Profile**:
  - **Category**: `deep`
    - Reason: 核心评估逻辑，需要处理工具调用匹配、参数验证等复杂逻辑
  - **Skills**: []

  **Parallelization**:
  - **Can Run In Parallel**: NO (核心评估器)
  - **Blocks**: Task F1
  - **Blocked By**: Task 2, Task 4, Task 6

  **References**:
  - `benchmark/data/intent_cases.json` - 测试用例数据
  - `benchmark/agent/intent_accuracy.py` - 现有评估器骨架
  - `benchmark/config.py` - 配置加载（API 端点地址）

  **Acceptance Criteria**:
  - [ ] `_evaluate_case()` 调用真实 API
  - [ ] 返回基于真实工具调用的 pass/fail 判断
  - [ ] TDD 测试从 RED 变为 GREEN

  **QA Scenarios**:
  ```
  Scenario: 真实意图识别评测
    Tool: Bash (python)
    Steps:
      1. 启动测试服务器
      2. python -m benchmark --module agent 2>&1 | grep intent_accuracy
      3. 验证输出不包含 "placeholder" 或 "skeleton"
    Expected Result: 显示真实准确率数值
    Evidence: .sisyphus/evidence/task-7-intent-accuracy.txt
  ```

  **Commit**: YES
  - Message: `feat(benchmark): implement real intent_accuracy evaluator`
  - Files: `benchmark/agent/intent_accuracy.py`

- [ ] 8. 实现 response_perf 评估器

  **What to do**:
  - 重写 `benchmark/agent/response_perf.py` 的 `_simulate_agent_call()` 方法
  - 调用 `/api/benchmark/agent/chat` 端点
  - 收集真实的延迟数据
  - 计算 p50, p95, p99 延迟

  **Recommended Agent Profile**:
  - **Category**: `quick`
    - Reason: 简单的延迟统计
  - **Skills**: []

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 3 (with Tasks 7, 9)
  - **Blocks**: Task F1
  - **Blocked By**: Task 4, Task 6

  **References**:
  - `benchmark/agent/response_perf.py` - 现有评估器骨架

  **Acceptance Criteria**:
  - [ ] 使用真实 API 调用测量延迟
  - [ ] 返回真实延迟数值（非硬编码 11ms）

  **QA Scenarios**:
  ```
  Scenario: 真实延迟测量
    Tool: Bash (python)
    Steps:
      1. python -m benchmark --module agent 2>&1 | grep latency_p50
      2. 验证 latency 值不是 11ms（硬编码值）
    Expected Result: 显示真实延迟（通常 >100ms）
    Evidence: .sisyphus/evidence/task-8-response-perf.txt
  ```

  **Commit**: NO (groups with Task 7)

- [ ] 9. 实现 multi_agent 评估器

  **What to do**:
  - 重写 `benchmark/agent/multi_agent.py` 的 `_simulate_agent_call()` 方法
  - 使用 `asyncio.gather()` 并发调用多个 Agent
  - 测量真实并发延迟
  - 计算 scaling_ratio

  **Recommended Agent Profile**:
  - **Category**: `unspecified-high`
    - Reason: 需要理解并发性能测试，asyncio 并发控制
  - **Skills**: []

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 3 (with Tasks 7, 8)
  - **Blocks**: Task F1
  - **Blocked By**: Task 4, Task 6

  **References**:
  - `benchmark/agent/multi_agent.py` - 现有评估器骨架
  - `src/simu_emperor/adapters/web/benchmark_api.py` - API 端点

  **Acceptance Criteria**:
  - [ ] 使用真实并发 API 调用
  - [ ] 返回真实 scaling_ratio（非硬编码 1.0）

  **QA Scenarios**:
  ```
  Scenario: 真实并发测试
    Tool: Bash (python)
    Steps:
      1. python -m benchmark --module agent 2>&1 | grep scaling_ratio
      2. 验证 scaling_ratio 不是 1.0（硬编码值）
    Expected Result: 显示真实并发扩展比
    Evidence: .sisyphus/evidence/task-9-multi-agent.txt
  ```

  **Commit**: YES
  - Message: `feat(benchmark): implement real agent evaluators`
  - Files: `benchmark/agent/intent_accuracy.py`, `benchmark/agent/response_perf.py`, `benchmark/agent/multi_agent.py`

---

## Final Verification Wave (MANDATORY)

- [ ] F1. **完整 Benchmark 运行** — `oracle`
  运行 `python -m benchmark --module agent`，验证所有 3 个评估器返回真实数据，无占位符值。
  Output: `Benchmark [PASS/FAIL] | Evaluators [3/3] | Metrics [N/N]`

- [ ] F2. **代码质量检查** — `unspecified-high`
  运行 `uv run ruff check .` 和 `uv run pytest tests/benchmark/`，确保无 lint 错误，测试全部通过。
  Output: `Ruff [PASS/FAIL] | Tests [N pass/N fail]`

- [ ] F3. **文档更新** — `unspecified-low`
  更新 `benchmark/README.md`，添加真实集成说明，移除占位符警告。
  Output: `README updated | Verified`

---

## Commit Strategy

- **Wave 1**: `feat(benchmark): add isolated test env and update intent cases` — config.benchmark.test.yaml, intent_cases.json
- **Wave 2**: `feat(api): add benchmark API endpoints` — benchmark_api.py, test_benchmark_api.py
- **Wave 3**: `feat(benchmark): implement real agent evaluators` — intent_accuracy.py, response_perf.py, multi_agent.py

---

## Success Criteria

### Verification Commands
```bash
# 运行 Agent benchmark
python -m benchmark --module agent

# 运行 TDD 测试
uv run pytest tests/benchmark/ -v

# 代码质量检查
uv run ruff check benchmark/
```

### Final Checklist
- [ ] 所有 3 个 Agent 评估器返回真实数据
- [ ] intent_cases.json 工具名称已更新
- [ ] Benchmark API 端点可调用
- [ ] 隔离环境自动清理
- [ ] 测试 100% 通过
- [ ] README 已更新
