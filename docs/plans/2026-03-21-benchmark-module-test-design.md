# Benchmark 模块测试重构设计

> 日期: 2026-03-21
> 状态: 已确认 (v2 - 细化版)

## 背景

当前 benchmark 测试存在以下问题：

1. **Agent 评测**通过 HTTP API 调用 `/api/benchmark/agent/chat`，需要启动完整服务器
2. **Memory 评测**使用硬编码 placeholder，没有真实测试
3. **multi_agent 模块**不需要（只用直隶总督）

## 目标

将 API 测试改为直接调用 Application 层服务，使用真实 LLM 调用。

## 设计决策

| 决策点 | 选择 | 理由 |
|--------|------|------|
| 核心架构 | 复用 `ApplicationServices` | 保持与生产环境一致的行为 |
| Agent 初始化 | 仅 governor_zhili | benchmark 只需测试一个 agent |
| 测试数据库 | SQLite :memory: | 测试结束后自动清理，无副作用 |
| Agent 响应获取 | EventBus 通知 + Tape 查询 | 实时通知 + 详细事件数据 |
| Memory 数据准备 | 直接写 tape.jsonl 文件 | 精确控制测试数据，不依赖 Agent |
| 旧代码处理 | 完全删除 API 测试代码 | 简化维护 |

## 架构设计

### 组件关系

```
benchmark/
├── context.py              # 新增：BenchmarkContext 服务容器
├── base.py                 # 新增：BaseEvaluator 基类
├── agent/
│   ├── intent_accuracy.py  # 重构：继承 BaseEvaluator
│   └── response_perf.py    # 重构：继承 BaseEvaluator
│   # multi_agent.py        # 删除
├── memory/
│   ├── retrieval.py        # 重构：实现真实检索
│   ├── compression.py      # 重构：实现真实压缩
│   └── cross_session.py    # 重构：实现真实跨会话
└── runner.py               # 更新：移除 multi_agent 引用
```

### BenchmarkContext 结构

```python
class BenchmarkContext:
    """Benchmark 专用服务容器"""
    
    # 核心组件
    services: ApplicationServices      # 完整服务容器
    agent: Agent                       # governor_zhili 实例
    memory_dir: Path                   # 临时目录
    
    # Memory 组件（直接访问）
    two_level_searcher: TwoLevelSearcher
    tape_writer: TapeWriter
    tape_metadata_mgr: TapeMetadataManager
    
    # 响应等待机制
    _session_id: str
    _response_event: asyncio.Event
    _last_response: dict
    
    @classmethod
    async def create(cls, config: BenchmarkConfig) -> "BenchmarkContext":
        """
        1. 创建临时目录 (tempfile.mkdtemp)
        2. 构造 GameConfig (使用 config 中的 LLM 配置，DB 为 :memory:)
        3. 调用 ApplicationServices.create(settings)
        4. services.start() -> 只初始化 governor_zhili
        5. 获取 agent 实例和 memory 组件引用
        6. 设置 EventBus 响应监听
        """
    
    async def send_message(self, message: str) -> dict:
        """
        发送消息并获取响应 (EventBus 通知 + Tape 查询)
        
        1. 重置状态: _response_event.clear(), _last_response = {}
        2. 订阅 EventBus 等待 RESPONSE 事件
        3. 调用 services.message_service.send_command()
        4. 等待 asyncio.Event (60s timeout)
        5. 查询 TapeService.get_current_tape() 获取 tool_calls
        6. 返回 {response, tool_calls, latency_ms}
        """
    
    async def retrieve_memory(self, query: str) -> list[dict]:
        """
        检索记忆 (直接调用 TwoLevelSearcher)
        
        1. 构造 StructuredQuery
        2. 直接调用 two_level_searcher.search()
        3. 返回 [{session_id, content, score}, ...]
        """
    
    def inject_memory_events(self, session_id: str, events: list[dict]) -> None:
        """
        注入测试事件到 tape 文件（同步写文件）
        
        1. 构造 tape 文件路径: memory_dir/agents/governor_zhili/sessions/{session_id}/tape.jsonl
        2. 直接写入 tape.jsonl
        3. 更新 tape_meta.jsonl
        """
    
    async def shutdown(self):
        """清理资源: 关闭数据库，删除临时目录"""
```

### BaseEvaluator 结构

```python
class BaseEvaluator:
    """Evaluator 基类，管理共享的 BenchmarkContext"""
    
    _shared_context: ClassVar[BenchmarkContext | None] = None  # 类级别共享
    
    def __init__(self, config: BenchmarkConfig):
        self.config = config
    
    @classmethod
    async def get_context(cls) -> BenchmarkContext:
        """懒加载创建 context，所有 evaluator 共享同一个实例"""
        if cls._shared_context is None:
            cls._shared_context = await BenchmarkContext.create(cls._config)
        return cls._shared_context
    
    @classmethod
    async def cleanup(cls):
        """清理 context"""
        if cls._shared_context:
            await cls._shared_context.shutdown()
            cls._shared_context = None
```

### Agent 评测流程

```python
class IntentAccuracyEvaluator(BaseEvaluator):
    async def _evaluate_case(self, case: dict) -> CaseDetail:
        ctx = await self.get_context()
        
        # 直接调用服务层
        result = await ctx.send_message(case["input"])
        
        actual_tools = [tc["name"] for tc in result["tool_calls"]]
        must_have = set(case.get("must_have_tools", []))
        passed = must_have.issubset(set(actual_tools))
        
        return CaseDetail(
            case_id=case["id"],
            passed=passed,
            input=case["input"],
            expected=list(must_have),
            actual=actual_tools,
            reason=...
        )
```

### Memory 评测流程

```python
class RetrievalEvaluator(BaseEvaluator):
    async def evaluate(self) -> ModuleResult:
        ctx = await self.get_context()
        
        # 注入测试数据
        events = self._load_inject_events()
        await ctx.inject_memory_events(events)
        
        # 执行检索测试
        queries = self._load_test_queries()
        for query in queries:
            results = await ctx.retrieve_memory(query["query"])
            # 计算 Recall@5, MRR...
```

## 实现步骤

### Phase 1: 基础设施

1. 创建 `benchmark/context.py` - BenchmarkContext 类
2. 创建 `benchmark/base.py` - BaseEvaluator 基类
3. 更新 `benchmark/runner.py` - 管理 context 生命周期

### Phase 2: Agent 评测重构

4. 重构 `benchmark/agent/intent_accuracy.py`
5. 重构 `benchmark/agent/response_perf.py`
6. 删除 `benchmark/agent/multi_agent.py`

### Phase 3: Memory 评测实现

7. 重构 `benchmark/memory/retrieval.py` - 实现真实检索
8. 重构 `benchmark/memory/compression.py` - 实现 ContextManager 压缩测试
9. 重构 `benchmark/memory/cross_session.py` - 实现跨会话检索

### Phase 4: 清理

10. 删除 `src/simu_emperor/adapters/web/benchmark_api.py` (不再需要)
11. 更新 `benchmark/README.md`

## 测试验证

每个阶段完成后运行：

```bash
# 运行 benchmark 测试
python -m benchmark --module agent
python -m benchmark --module memory

# 运行单元测试
uv run pytest tests/benchmark/
```

## 风险与缓解

| 风险 | 缓解措施 |
|------|----------|
| LLM 调用不稳定 | 保留 retry 逻辑，使用 timeout 配置 |
| :memory: 数据库隔离 | 每次测试创建新 context |
| 初始化耗时长 | Context 懒加载，所有 evaluator 共享 |
