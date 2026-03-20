# Benchmark System Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Implement a comprehensive benchmark/evaluation system for 皇帝模拟器 to measure Agent quality, performance, and Memory system effectiveness.

**Architecture:** Standalone `benchmark/` module at project root with unified data structures, modular evaluators, and Markdown report generation. Uses real LLM calls with separate configuration from the main application.

**Tech Stack:** Python 3.12+, pytest patterns, asyncio, pydantic dataclasses, JSON test data

---

## TL;DR

> **Quick Summary**: Build a benchmark system that evaluates Agent (intent recognition, tool calls, concurrency) and Memory (retrieval, compression, consistency) with quantified metrics and auto-generated Markdown reports.
>
> **Deliverables**:
> - `benchmark/` module with CLI entry point
> - Agent evaluation: intent_accuracy.py, response_perf.py, multi_agent.py
> - Memory evaluation: retrieval.py, compression.py, cross_session.py
> - Test data: 50 agent cases + 30+20 memory events/queries
> - Markdown report generator with optimization suggestions
>
> **Estimated Effort**: Large (~4 days)
> **Parallel Execution**: YES - 5 waves
> **Critical Path**: Data structures → Agent quality → Memory retrieval → Integration → Test data

---

## Context

### Original Request
根据 `.design/benchmark.md` 制定评测系统实施计划

### Interview Summary
**Key Discussions**:
- Directory: `benchmark/` at project root (not in src/)
- No unit tests for benchmark code itself
- Full implementation (all P0/P1/P2 modules)
- Separate LLM config for benchmark, independent from agent config

**Research Findings**:
- Codebase uses pytest + pytest-asyncio, no existing benchmark code
- Agent system: `Agent` class + `ToolRegistry` + `EventBus` + `LLMProvider`
- Memory system: `StructuredRetriever` + `TwoLevelSearcher` + `ContextManager` + `QueryParser`
- No `ManifestIndex` class - uses `TapeMetadataIndex` instead

### Codebase References
- Agent: `src/simu_emperor/agents/agent.py`
- ToolRegistry: `src/simu_emperor/agents/tools/tool_registry.py`
- EventBus: `src/simu_emperor/event_bus/core.py`
- LLM Provider: `src/simu_emperor/llm/base.py`
- Memory Retrieval: `src/simu_emperor/memory/structured_retriever.py`
- ContextManager: `src/simu_emperor/memory/context_manager.py`
- QueryParser: `src/simu_emperor/memory/query_parser.py`

---

## Work Objectives

### Core Objective
Create a production-ready benchmark system that evaluates LLM application engineering capabilities with quantified metrics and actionable optimization suggestions.

### Concrete Deliverables
- `benchmark/__init__.py`, `benchmark/__main__.py`, `benchmark/runner.py`, `benchmark/report.py`
- `benchmark/agent/intent_accuracy.py`, `benchmark/agent/response_perf.py`, `benchmark/agent/multi_agent.py`
- `benchmark/memory/retrieval.py`, `benchmark/memory/compression.py`, `benchmark/memory/cross_session.py`
- `benchmark/data/intent_cases.json` (50 cases), `benchmark/data/memory_events.json` (30+20)
- `benchmark/reports/raw/` for JSON persistence

### Definition of Done
- [ ] `uv run python -m benchmark` runs successfully
- [ ] `uv run python -m benchmark --module agent` runs agent evaluation only
- [ ] `uv run python -m benchmark --repeat 3` runs 3 iterations
- [ ] Markdown report generated with all metrics
- [ ] JSON raw results saved for cross-run comparison

### Must Have
- All 6 evaluation modules implemented
- Unified data structures (MetricResult, CaseDetail, ModuleResult)
- CLI with --module, --repeat, --output options
- Separate benchmark LLM config
- Real LLM calls (no mocks)

### Must NOT Have (Guardrails)
- Do NOT put benchmark in `src/simu_emperor/benchmark/`
- Do NOT add unit tests for benchmark code
- Do NOT modify existing game code
- Do NOT use mock LLM for actual benchmarks
- Do NOT include API pressure testing (stated in design doc)

---

## Verification Strategy

### Test Decision
- **Infrastructure exists**: YES (pytest)
- **Automated tests**: None for benchmark code
- **Agent-Executed QA**: YES - run benchmark and verify output

### QA Policy
Every task MUST include agent-executed QA scenarios.
Evidence saved to `.sisyphus/evidence/task-{N}-{scenario-slug}.{ext}`.

- **CLI/Python**: Use Bash — Run commands, check exit codes, verify file output
- **Reports**: Use Read — Verify Markdown structure, check metric presence

---

## Execution Strategy

### Parallel Execution Waves

```
Wave 1 (Foundation — data structures + config):
├── Task 1: Create benchmark directory structure + __init__.py [quick]
├── Task 2: Unified data structures (MetricResult, CaseDetail, ModuleResult) [quick]
├── Task 3: Benchmark config (separate from main config) [quick]
└── Task 4: CLI entry point (__main__.py with argparse) [quick]

Wave 2 (Core infrastructure):
├── Task 5: runner.py — orchestration engine [deep]
├── Task 6: report.py — Markdown generator [deep]
└── Task 7: LLM metrics hook for response_perf [quick]

Wave 3 (Agent evaluation modules):
├── Task 8: intent_accuracy.py — quality evaluation [deep]
├── Task 9: response_perf.py — performance metrics [unspecified-high]
└── Task 10: multi_agent.py — concurrency testing [unspecified-high]

Wave 4 (Memory evaluation modules):
├── Task 11: retrieval.py — Recall@K, MRR [deep]
├── Task 12: compression.py — sliding window fidelity [unspecified-high]
└── Task 13: cross_session.py — consistency testing [unspecified-high]

Wave 5 (Test data):
├── Task 14: intent_cases.json — 50 agent test cases [quick]
└── Task 15: memory_events.json — 30 inject + 20 query [quick]

Wave FINAL (Integration verification):
├── Task F1: Full benchmark run verification
├── Task F2: Report structure validation
├── Task F3: Multi-run comparison test
└── Task F4: CLI options verification
```

### Dependency Matrix

- **1-4**: No dependencies (can run in parallel)
- **5-7**: Depend on 1, 2, 3
- **8-10**: Depend on 2, 5, 7
- **11-13**: Depend on 2, 5
- **14-15**: No dependencies (can run anytime)
- **F1-F4**: Depend on all previous tasks

### Agent Dispatch Summary
- **Wave 1**: 4 tasks → `quick`
- **Wave 2**: 3 tasks → 2×`deep`, 1×`quick`
- **Wave 3**: 3 tasks → 1×`deep`, 2×`unspecified-high`
- **Wave 4**: 3 tasks → 1×`deep`, 2×`unspecified-high`
- **Wave 5**: 2 tasks → `quick`
- **FINAL**: 4 tasks → `quick`

---

## TODOs

- [ ] 1. Create benchmark directory structure

  **What to do**:
  - Create `benchmark/` directory at project root
  - Create `benchmark/__init__.py` with module docstring
  - Create subdirectories: `benchmark/agent/`, `benchmark/memory/`, `benchmark/data/`, `benchmark/reports/raw/`
  - Create `__init__.py` for each subpackage
  - Add `.gitkeep` to `benchmark/reports/raw/`
  - Update `.gitignore` to ignore `benchmark/reports/*.md` but keep raw JSON

  **Must NOT do**:
  - Do NOT create in `src/simu_emperor/benchmark/`
  - Do NOT modify existing code

  **Recommended Agent Profile**:
  - **Category**: `quick`
  - **Skills**: []

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 1 (with Tasks 2, 3, 4)
  - **Blocks**: Tasks 5-7
  - **Blocked By**: None

  **References**:
  - Design doc: `.design/benchmark.md` lines 23-50 (directory structure)
  - Pattern: `tests/` directory organization

  **Acceptance Criteria**:
  - [ ] `benchmark/__init__.py` exists with docstring
  - [ ] All subdirectories created with `__init__.py`
  - [ ] `.gitignore` updated for reports

  **QA Scenarios**:
  ```
  Scenario: Directory structure exists
    Tool: Bash
    Steps:
      1. ls -la benchmark/
      2. ls -la benchmark/agent/ benchmark/memory/ benchmark/data/ benchmark/reports/raw/
    Expected Result: All directories exist with __init__.py files
    Evidence: .sisyphus/evidence/task-01-structure.txt
  ```

  **Commit**: YES
  - Message: `feat(benchmark): add directory structure`
  - Files: `benchmark/`, `.gitignore`

- [ ] 2. Create unified data structures

  **What to do**:
  - Create `benchmark/models.py` with dataclasses:
    - `MetricResult(name, value, target, unit, passed)`
    - `CaseDetail(case_id, passed, input, expected, actual, reason)`
    - `ModuleResult(module, metrics, details, duration_seconds)`
  - Add `to_dict()` methods for JSON serialization
  - Add `from_dict()` class methods for deserialization
  - Include type hints and docstrings

  **Must NOT do**:
  - Do NOT use pydantic (stick to dataclasses for simplicity)
  - Do NOT add validation logic beyond type hints

  **Recommended Agent Profile**:
  - **Category**: `quick`
  - **Skills**: []

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 1 (with Tasks 1, 3, 4)
  - **Blocks**: Tasks 5-13
  - **Blocked By**: None

  **References**:
  - Design doc: `.design/benchmark.md` lines 53-80 (data structures)
  - Pattern: `src/simu_emperor/event_bus/event.py` (dataclass pattern)

  **Acceptance Criteria**:
  - [ ] All 3 dataclasses defined with correct fields
  - [ ] `to_dict()` and `from_dict()` methods work
  - [ ] Type hints complete

  **QA Scenarios**:
  ```
  Scenario: Data structures serialize/deserialize
    Tool: Bash (python -c)
    Steps:
      1. Import MetricResult, create instance
      2. Call to_dict(), verify JSON structure
      3. Call from_dict(), verify roundtrip
    Expected Result: All operations succeed with correct types
    Evidence: .sisyphus/evidence/task-02-models.txt
  ```

  **Commit**: YES
  - Message: `feat(benchmark): add unified data structures`
  - Files: `benchmark/models.py`

- [ ] 3. Create benchmark configuration

  **What to do**:
  - Create `benchmark/config.py` with:
    - `BenchmarkConfig` dataclass with LLM settings
    - Load from `config.benchmark.yaml` or `BENCHMARK_*` env vars
    - Separate from main game config (independent LLM provider)
    - Default values: provider="anthropic", model="claude-3-5-sonnet-20241022"
  - Create `config.benchmark.example.yaml` template

  **Must NOT do**:
  - Do NOT reuse main `config.yaml` for benchmark
  - Do NOT hardcode API keys

  **Recommended Agent Profile**:
  - **Category**: `quick`
  - **Skills**: []

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 1 (with Tasks 1, 2, 4)
  - **Blocks**: Tasks 5-7, 8-13
  - **Blocked By**: None

  **References**:
  - Pattern: `config.example.yaml` structure
  - Pattern: `src/simu_emperor/llm/base.py` for LLM interface

  **Acceptance Criteria**:
  - [ ] `BenchmarkConfig` dataclass defined
  - [ ] `config.benchmark.example.yaml` created
  - [ ] Config loads from file or env vars

  **QA Scenarios**:
  ```
  Scenario: Config loads correctly
    Tool: Bash (python -c)
    Steps:
      1. Import BenchmarkConfig
      2. Create instance with defaults
      3. Verify LLM provider settings
    Expected Result: Config instantiates with correct defaults
    Evidence: .sisyphus/evidence/task-03-config.txt
  ```

  **Commit**: YES
  - Message: `feat(benchmark): add configuration system`
  - Files: `benchmark/config.py`, `config.benchmark.example.yaml`

- [ ] 4. Create CLI entry point

  **What to do**:
  - Create `benchmark/__main__.py` with argparse:
    - `--module` (agent/memory/all)
    - `--repeat` (int, default 1)
    - `--output` (path, default auto-generated)
    - `--config` (path to benchmark config)
  - Main function calls runner with parsed args
  - Handle errors gracefully with exit codes

  **Must NOT do**:
  - Do NOT implement runner logic here (just CLI parsing)
  - Do NOT use click (stick to argparse)

  **Recommended Agent Profile**:
  - **Category**: `quick`
  - **Skills**: []

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 1 (with Tasks 1, 2, 3)
  - **Blocks**: Task 5
  - **Blocked By**: None

  **References**:
  - Pattern: `src/simu_emperor/main.py` entry point
  - Design doc: `.design/benchmark.md` lines 343-360 (CLI usage)

  **Acceptance Criteria**:
  - [ ] `python -m benchmark --help` shows usage
  - [ ] All CLI options parsed correctly
  - [ ] Exit codes: 0=success, 1=error

  **QA Scenarios**:
  ```
  Scenario: CLI help works
    Tool: Bash
    Steps:
      1. uv run python -m benchmark --help
    Expected Result: Help text shows all options
    Evidence: .sisyphus/evidence/task-04-cli-help.txt

  Scenario: CLI with invalid option
    Tool: Bash
    Steps:
      1. uv run python -m benchmark --invalid-option
    Expected Result: Exit code 1, error message shown
    Evidence: .sisyphus/evidence/task-04-cli-error.txt
  ```

  **Commit**: YES
  - Message: `feat(benchmark): add CLI entry point`
  - Files: `benchmark/__main__.py`

- [ ] 5. Create orchestration runner

  **What to do**:
  - Create `benchmark/runner.py` with `BenchmarkRunner` class:
    - `run(module, repeat)` method
    - Initialize LLM provider from config
    - Run modules sequentially (agent → memory)
    - Collect `ModuleResult` from each
    - Aggregate results across repeats
    - Save raw JSON to `reports/raw/benchmark-YYYY-MM-DD-NNN.json`
  - Handle LLM provider initialization
  - Time each module execution

  **Must NOT do**:
  - Do NOT run modules in parallel (design says sequential)
  - Do NOT modify game state

  **Recommended Agent Profile**:
  - **Category**: `deep`
  - **Skills**: []

  **Parallelization**:
  - **Can Run In Parallel**: NO
  - **Parallel Group**: Wave 2 (after Wave 1)
  - **Blocks**: Tasks 8-13
  - **Blocked By**: Tasks 1, 2, 3

  **References**:
  - Design doc: `.design/benchmark.md` lines 343-360 (run commands)
  - Pattern: `src/simu_emperor/engine/` orchestration patterns

  **Acceptance Criteria**:
  - [ ] `BenchmarkRunner` class defined
  - [ ] `run()` method executes modules
  - [ ] JSON results saved correctly

  **QA Scenarios**:
  ```
  Scenario: Runner saves JSON results
    Tool: Bash
    Steps:
      1. Create minimal mock module
      2. Run BenchmarkRunner with repeat=1
      3. Check reports/raw/ for JSON file
    Expected Result: JSON file created with correct structure
    Evidence: .sisyphus/evidence/task-05-runner-json.txt
  ```

  **Commit**: YES
  - Message: `feat(benchmark): add orchestration runner`
  - Files: `benchmark/runner.py`

- [ ] 6. Create Markdown report generator

  **What to do**:
  - Create `benchmark/report.py` with `ReportGenerator` class:
    - `generate(results, output_path)` method
    - Follow template from design doc lines 267-341
    - Include: execution summary, agent metrics, memory metrics, optimization suggestions
    - Generate ASCII histogram for latency distribution
    - Apply optimization rules (lines 256-263) without LLM

  **Must NOT do**:
  - Do NOT use LLM for suggestion generation
  - Do NOT include sensitive data in reports

  **Recommended Agent Profile**:
  - **Category**: `deep`
  - **Skills**: []

  **Parallelization**:
  - **Can Run In Parallel**: NO
  - **Parallel Group**: Wave 2 (with Tasks 5, 7)
  - **Blocks**: F1-F4
  - **Blocked By**: Task 2

  **References**:
  - Design doc: `.design/benchmark.md` lines 243-341 (report template)
  - Optimization rules: lines 256-263

  **Acceptance Criteria**:
  - [ ] Report follows template structure
  - [ ] All metrics rendered correctly
  - [ ] Optimization suggestions generated

  **QA Scenarios**:
  ```
  Scenario: Report generates valid Markdown
    Tool: Bash + Read
    Steps:
      1. Create sample ModuleResult data
      2. Call ReportGenerator.generate()
      3. Read output Markdown file
      4. Check for required sections
    Expected Result: Valid Markdown with all sections
    Evidence: .sisyphus/evidence/task-06-report.md
  ```

  **Commit**: YES
  - Message: `feat(benchmark): add Markdown report generator`
  - Files: `benchmark/report.py`

- [ ] 7. Create LLM metrics hook

  **What to do**:
  - Create `benchmark/metrics_hook.py` with:
    - `LLMMetricsCollector` class
    - Hook to wrap `LLMProvider.call_with_functions()`
    - Track: latency per call, token counts, call count
    - Methods: `start_collection()`, `stop_collection()`, `get_metrics()`
  - Design for injection/removal without modifying game code

  **Must NOT do**:
  - Do NOT modify `src/simu_emperor/llm/` code
  - Do NOT use global state

  **Recommended Agent Profile**:
  - **Category**: `quick`
  - **Skills**: []

  **Parallelization**:
  - **Can Run In Parallel**: NO
  - **Parallel Group**: Wave 2 (with Tasks 5, 6)
  - **Blocks**: Task 9
  - **Blocked By**: Task 3

  **References**:
  - Design doc: `.design/benchmark.md` lines 130-141 (performance metrics)
  - Pattern: `src/simu_emperor/llm/base.py` LLMProvider interface

  **Acceptance Criteria**:
  - [ ] `LLMMetricsCollector` wraps provider
  - [ ] Tracks latency, tokens, call count
  - [ ] Can be attached/detached cleanly

  **QA Scenarios**:
  ```
  Scenario: Metrics hook captures LLM calls
    Tool: Bash (python -c)
    Steps:
      1. Create mock LLMProvider
      2. Wrap with LLMMetricsCollector
      3. Make call, check metrics recorded
    Expected Result: Metrics captured correctly
    Evidence: .sisyphus/evidence/task-07-hook.txt
  ```

  **Commit**: YES
  - Message: `feat(benchmark): add LLM metrics hook`
  - Files: `benchmark/metrics_hook.py`

- [ ] 8. Create intent accuracy evaluator

  **What to do**:
  - Create `benchmark/agent/intent_accuracy.py`:
    - Load test cases from `benchmark/data/intent_cases.json`
    - For each case: create Agent, send input event, capture tool calls
    - Score: must_have tools (baseline 1.0), nice_to_have (+0.1 each)
    - Calculate: intent accuracy, tool success rate, param correctness
    - Return `ModuleResult` with metrics and case details

  **Must NOT do**:
  - Do NOT use mock LLM (real calls required)
  - Do NOT modify Agent behavior

  **Recommended Agent Profile**:
  - **Category**: `deep`
  - **Skills**: []

  **Parallelization**:
  - **Can Run In Parallel**: NO
  - **Parallel Group**: Wave 3 (with Tasks 9, 10)
  - **Blocks**: F1-F4
  - **Blocked By**: Tasks 2, 5

  **References**:
  - Design doc: `.design/benchmark.md` lines 83-129 (intent accuracy)
  - Agent: `src/simu_emperor/agents/agent.py`
  - ToolRegistry: `src/simu_emperor/agents/tools/tool_registry.py`

  **Acceptance Criteria**:
  - [ ] Loads and runs test cases
  - [ ] Calculates 3 metrics: accuracy, tool success, param correctness
  - [ ] Returns `ModuleResult` with case details

  **QA Scenarios**:
  ```
  Scenario: Intent accuracy runs on sample cases
    Tool: Bash
    Steps:
      1. Create 3 sample test cases in intent_cases.json
      2. Run intent_accuracy evaluator
      3. Check ModuleResult has correct metrics
    Expected Result: Metrics calculated, all cases evaluated
    Evidence: .sisyphus/evidence/task-08-intent.txt
  ```

  **Commit**: YES
  - Message: `feat(benchmark): add intent accuracy evaluator`
  - Files: `benchmark/agent/intent_accuracy.py`

- [ ] 9. Create response performance evaluator

  **What to do**:
  - Create `benchmark/agent/response_perf.py`:
    - Reuse test cases from intent_accuracy
    - Attach `LLMMetricsCollector` to LLM provider
    - Measure: end-to-end latency (p50/p95/p99), LLM call count, token consumption
    - Return `ModuleResult` with performance metrics

  **Must NOT do**:
  - Do NOT include latency from intent_accuracy scoring
  - Do NOT use mock LLM

  **Recommended Agent Profile**:
  - **Category**: `unspecified-high`
  - **Skills**: []

  **Parallelization**:
  - **Can Run In Parallel**: NO
  - **Parallel Group**: Wave 3 (with Tasks 8, 10)
  - **Blocks**: F1-F4
  - **Blocked By**: Tasks 2, 5, 7

  **References**:
  - Design doc: `.design/benchmark.md` lines 130-141 (response perf)
  - Metrics hook: `benchmark/metrics_hook.py`

  **Acceptance Criteria**:
  - [ ] Latency percentiles calculated correctly
  - [ ] Token counts aggregated
  - [ ] LLM call count tracked

  **QA Scenarios**:
  ```
  Scenario: Performance metrics captured
    Tool: Bash
    Steps:
      1. Run response_perf evaluator with 5 cases
      2. Check ModuleResult.metrics for p50/p95/p99
      3. Verify token counts > 0
    Expected Result: All performance metrics present
    Evidence: .sisyphus/evidence/task-09-perf.txt
  ```

  **Commit**: YES
  - Message: `feat(benchmark): add response performance evaluator`
  - Files: `benchmark/agent/response_perf.py`

- [ ] 10. Create multi-agent concurrency evaluator

  **What to do**:
  - Create `benchmark/agent/multi_agent.py`:
    - Test agent_counts = [2, 5, 10]
    - Create N agents, send events simultaneously via EventBus
    - Measure latency distribution for each count
    - Verify sub-linear scaling (p95 < single_agent × multiplier)
    - Return `ModuleResult` with concurrency metrics

  **Must NOT do**:
  - Do NOT use mock LLM
  - Do NOT test beyond 10 agents (design limit)

  **Recommended Agent Profile**:
  - **Category**: `unspecified-high`
  - **Skills**: []

  **Parallelization**:
  - **Can Run In Parallel**: NO
  - **Parallel Group**: Wave 3 (with Tasks 8, 9)
  - **Blocks**: F1-F4
  - **Blocked By**: Tasks 2, 5

  **References**:
  - Design doc: `.design/benchmark.md` lines 142-166 (multi-agent)
  - EventBus: `src/simu_emperor/event_bus/core.py`
  - Agent: `src/simu_emperor/agents/agent.py`

  **Acceptance Criteria**:
  - [ ] Tests 2, 5, 10 agent counts
  - [ ] Latency scaling measured
  - [ ] Sub-linear verification logic implemented

  **QA Scenarios**:
  ```
  Scenario: Concurrency test runs
    Tool: Bash
    Steps:
      1. Run multi_agent evaluator
      2. Check metrics for 2, 5, 10 agents
      3. Verify scaling ratios calculated
    Expected Result: Metrics for all 3 configurations
    Evidence: .sisyphus/evidence/task-10-concurrency.txt
  ```

  **Commit**: YES
  - Message: `feat(benchmark): add multi-agent concurrency evaluator`
  - Files: `benchmark/agent/multi_agent.py`

- [ ] 11. Create memory retrieval evaluator

  **What to do**:
  - Create `benchmark/memory/retrieval.py`:
    - Load events from `benchmark/data/memory_events.json`
    - Inject events into memory system
    - Execute queries, compare with ground truth
    - Calculate: Recall@5, MRR, retrieval latency p95
    - Break down by difficulty (easy/medium/hard)
    - Return `ModuleResult` with retrieval metrics

  **Must NOT do**:
  - Do NOT use mock QueryParser (real LLM parsing)
  - Do NOT skip difficulty breakdown

  **Recommended Agent Profile**:
  - **Category**: `deep`
  - **Skills**: []

  **Parallelization**:
  - **Can Run In Parallel**: NO
  - **Parallel Group**: Wave 4 (with Tasks 12, 13)
  - **Blocks**: F1-F4
  - **Blocked By**: Tasks 2, 5

  **References**:
  - Design doc: `.design/benchmark.md` lines 167-213 (retrieval)
  - Memory: `src/simu_emperor/memory/structured_retriever.py`
  - QueryParser: `src/simu_emperor/memory/query_parser.py`

  **Acceptance Criteria**:
  - [ ] Recall@5 calculated
  - [ ] MRR calculated
  - [ ] Latency p95 measured
  - [ ] Difficulty breakdown included

  **QA Scenarios**:
  ```
  Scenario: Retrieval metrics calculated
    Tool: Bash
    Steps:
      1. Create sample memory events + queries
      2. Run retrieval evaluator
      3. Verify Recall@5, MRR, latency present
    Expected Result: All metrics calculated with valid values
    Evidence: .sisyphus/evidence/task-11-retrieval.txt
  ```

  **Commit**: YES
  - Message: `feat(benchmark): add memory retrieval evaluator`
  - Files: `benchmark/memory/retrieval.py`

- [ ] 12. Create compression fidelity evaluator

  **What to do**:
  - Create `benchmark/memory/compression.py`:
    - Inject events until compression triggers (>8000 tokens)
    - Capture summary after compression
    - Check keyword retention rate (summary contains injected keywords)
    - Calculate compression ratio (compressed tokens / original tokens)
    - Return `ModuleResult` with compression metrics

  **Must NOT do**:
  - Do NOT force compression manually (let it trigger naturally)
  - Do NOT use mock LLM for summarization

  **Recommended Agent Profile**:
  - **Category**: `unspecified-high`
  - **Skills**: []

  **Parallelization**:
  - **Can Run In Parallel**: NO
  - **Parallel Group**: Wave 4 (with Tasks 11, 13)
  - **Blocks**: F1-F4
  - **Blocked By**: Tasks 2, 5

  **References**:
  - Design doc: `.design/benchmark.md` lines 214-228 (compression)
  - ContextManager: `src/simu_emperor/memory/context_manager.py`

  **Acceptance Criteria**:
  - [ ] Keyword retention rate calculated
  - [ ] Compression ratio calculated
  - [ ] Targets: retention >70%, ratio <0.3

  **QA Scenarios**:
  ```
  Scenario: Compression fidelity measured
    Tool: Bash
    Steps:
      1. Inject events with known keywords
      2. Trigger compression
      3. Check keyword retention in summary
    Expected Result: Retention rate and compression ratio calculated
    Evidence: .sisyphus/evidence/task-12-compression.txt
  ```

  **Commit**: YES
  - Message: `feat(benchmark): add compression fidelity evaluator`
  - Files: `benchmark/memory/compression.py`

- [ ] 13. Create cross-session consistency evaluator

  **What to do**:
  - Create `benchmark/memory/cross_session.py`:
    - Inject events into multiple sessions
    - Execute same query 3 times
    - Compare result sets using Jaccard similarity
    - Return `ModuleResult` with consistency metric
    - Target: >90% consistency

  **Must NOT do**:
  - Do NOT use deterministic query parsing (use real LLM)
  - Do NOT skip multiple session setup

  **Recommended Agent Profile**:
  - **Category**: `unspecified-high`
  - **Skills**: []

  **Parallelization**:
  - **Can Run In Parallel**: NO
  - **Parallel Group**: Wave 4 (with Tasks 11, 12)
  - **Blocks**: F1-F4
  - **Blocked By**: Tasks 2, 5

  **References**:
  - Design doc: `.design/benchmark.md` lines 229-242 (cross-session)
  - TwoLevelSearcher: `src/simu_emperor/memory/two_level_searcher.py`

  **Acceptance Criteria**:
  - [ ] Jaccard similarity calculated
  - [ ] 3 query runs executed
  - [ ] Target: >90% consistency

  **QA Scenarios**:
  ```
  Scenario: Cross-session consistency measured
    Tool: Bash
    Steps:
      1. Create events in multiple sessions
      2. Run same query 3 times
      3. Calculate Jaccard similarity
    Expected Result: Consistency metric calculated
    Evidence: .sisyphus/evidence/task-13-consistency.txt
  ```

  **Commit**: YES
  - Message: `feat(benchmark): add cross-session consistency evaluator`
  - Files: `benchmark/memory/cross_session.py`

- [ ] 14. Create intent test cases data

  **What to do**:
  - Create `benchmark/data/intent_cases.json` with 50 test cases:
    - 20 query cases (e.g., "直隶省今年的税收情况如何？")
    - 15 action cases (e.g., "给直隶拨款一万两银子")
    - 10 dialog cases (e.g., "你觉得如何？")
    - 5 edge cases (ambiguous, multi-intent)
  - Each case has: id, category, input, must_have_tools, nice_to_have_tools, must_have_args, expected_keywords

  **Must NOT do**:
  - Do NOT use real user data
  - Do NOT exceed 50 cases

  **Recommended Agent Profile**:
  - **Category**: `quick`
  - **Skills**: []

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 5 (with Task 15)
  - **Blocks**: Task 8
  - **Blocked By**: Task 1

  **References**:
  - Design doc: `.design/benchmark.md` lines 87-104 (test data format)
  - Pattern: `data/event_templates.json` structure

  **Acceptance Criteria**:
  - [ ] 50 cases created
  - [ ] All 4 categories covered
  - [ ] JSON schema validated

  **QA Scenarios**:
  ```
  Scenario: Intent cases JSON valid
    Tool: Bash
    Steps:
      1. python -c "import json; data=json.load(open('benchmark/data/intent_cases.json')); print(len(data['cases']))"
    Expected Result: Prints 50
    Evidence: .sisyphus/evidence/task-14-intent-data.txt
  ```

  **Commit**: YES
  - Message: `feat(benchmark): add intent test cases data`
  - Files: `benchmark/data/intent_cases.json`

- [ ] 15. Create memory test events data

  **What to do**:
  - Create `benchmark/data/memory_events.json` with:
    - `inject_events`: 30 events with id, content, keywords, session_id, event_type
    - `test_queries`: 20 queries with query, relevant_event_ids, difficulty (10 easy, 7 medium, 3 hard)
  - Cover diverse scenarios: tax, population, incidents, commands

  **Must NOT do**:
  - Do NOT use fewer than 30 inject events
  - Do NOT skip difficulty distribution

  **Recommended Agent Profile**:
  - **Category**: `quick`
  - **Skills**: []

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 5 (with Task 14)
  - **Blocks**: Tasks 11, 12, 13
  - **Blocked By**: Task 1

  **References**:
  - Design doc: `.design/benchmark.md` lines 175-203 (memory data format)
  - Pattern: `data/initial_state_v4.json` structure

  **Acceptance Criteria**:
  - [ ] 30 inject events created
  - [ ] 20 test queries created
  - [ ] Difficulty breakdown: 10/7/3

  **QA Scenarios**:
  ```
  Scenario: Memory events JSON valid
    Tool: Bash
    Steps:
      1. python -c "import json; d=json.load(open('benchmark/data/memory_events.json')); print(len(d['inject_events']), len(d['test_queries']))"
    Expected Result: Prints "30 20"
    Evidence: .sisyphus/evidence/task-15-memory-data.txt
  ```

  **Commit**: YES
  - Message: `feat(benchmark): add memory test events data`
  - Files: `benchmark/data/memory_events.json`

---

## Final Verification Wave

- [ ] F1. Full benchmark run verification

  **What to do**:
  - Run `uv run python -m benchmark --repeat 1`
  - Verify all 6 modules execute without errors
  - Check JSON results saved to `reports/raw/`
  - Check Markdown report generated

  **QA Scenarios**:
  ```
  Scenario: Full benchmark completes
    Tool: Bash
    Steps:
      1. uv run python -m benchmark --output reports/test-run.md
      2. Check exit code is 0
      3. Verify reports/test-run.md exists
      4. Verify reports/raw/*.json exists
    Expected Result: All outputs generated successfully
    Evidence: .sisyphus/evidence/final-01-full-run.txt
  ```

- [ ] F2. Report structure validation

  **What to do**:
  - Read generated Markdown report
  - Verify all sections present: summary, agent metrics, memory metrics, suggestions
  - Check ASCII histogram renders correctly
  - Verify all metrics have values and status icons

  **QA Scenarios**:
  ```
  Scenario: Report has all sections
    Tool: Read
    Steps:
      1. Read reports/test-run.md
      2. Check for "## 1. 执行概要", "## 2. Agent 评测", "## 3. 记忆系统评测", "## 4. 优化建议"
    Expected Result: All sections present
    Evidence: .sisyphus/evidence/final-02-report-structure.txt
  ```

- [ ] F3. Multi-run comparison test

  **What to do**:
  - Run `uv run python -m benchmark --repeat 3`
  - Verify 3 JSON files created in `reports/raw/`
  - Verify report shows averaged results

  **QA Scenarios**:
  ```
  Scenario: Multi-run creates multiple JSON files
    Tool: Bash
    Steps:
      1. rm -f benchmark/reports/raw/*.json
      2. uv run python -m benchmark --repeat 3
      3. ls benchmark/reports/raw/*.json | wc -l
    Expected Result: At least 3 JSON files created
    Evidence: .sisyphus/evidence/final-03-multi-run.txt
  ```

- [ ] F4. CLI options verification

  **What to do**:
  - Test `--module agent` runs only agent evaluation
  - Test `--module memory` runs only memory evaluation
  - Test `--output` specifies custom path

  **QA Scenarios**:
  ```
  Scenario: Module filter works
    Tool: Bash
    Steps:
      1. uv run python -m benchmark --module agent --output reports/agent-only.md
      2. Check report contains only agent section
    Expected Result: Only agent metrics in report
    Evidence: .sisyphus/evidence/final-04-cli-options.txt
  ```

---

## Commit Strategy

- **Task 1**: `feat(benchmark): add directory structure` — benchmark/, .gitignore
- **Task 2**: `feat(benchmark): add unified data structures` — benchmark/models.py
- **Task 3**: `feat(benchmark): add configuration system` — benchmark/config.py, config.benchmark.example.yaml
- **Task 4**: `feat(benchmark): add CLI entry point` — benchmark/__main__.py
- **Task 5**: `feat(benchmark): add orchestration runner` — benchmark/runner.py
- **Task 6**: `feat(benchmark): add Markdown report generator` — benchmark/report.py
- **Task 7**: `feat(benchmark): add LLM metrics hook` — benchmark/metrics_hook.py
- **Task 8**: `feat(benchmark): add intent accuracy evaluator` — benchmark/agent/intent_accuracy.py
- **Task 9**: `feat(benchmark): add response performance evaluator` — benchmark/agent/response_perf.py
- **Task 10**: `feat(benchmark): add multi-agent concurrency evaluator` — benchmark/agent/multi_agent.py
- **Task 11**: `feat(benchmark): add memory retrieval evaluator` — benchmark/memory/retrieval.py
- **Task 12**: `feat(benchmark): add compression fidelity evaluator` — benchmark/memory/compression.py
- **Task 13**: `feat(benchmark): add cross-session consistency evaluator` — benchmark/memory/cross_session.py
- **Task 14**: `feat(benchmark): add intent test cases data` — benchmark/data/intent_cases.json
- **Task 15**: `feat(benchmark): add memory test events data` — benchmark/data/memory_events.json

---

## Success Criteria

### Verification Commands
```bash
# Run full benchmark
uv run python -m benchmark

# Run single module
uv run python -m benchmark --module agent

# Run with repeats
uv run python -m benchmark --repeat 3 --output reports/my-benchmark.md

# Verify structure
ls -la benchmark/
ls -la benchmark/reports/raw/
```

### Final Checklist
- [ ] `uv run python -m benchmark` runs without errors
- [ ] All 6 evaluation modules implemented
- [ ] 50 intent test cases created
- [ ] 30+20 memory test data created
- [ ] Markdown report generated with all sections
- [ ] JSON results saved for cross-run comparison
- [ ] CLI options work (--module, --repeat, --output)
- [ ] Separate benchmark config working
