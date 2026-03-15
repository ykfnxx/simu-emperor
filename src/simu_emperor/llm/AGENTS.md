# LLM 模块文档

## 模块概述

`src/simu_emperor/llm` 模块是大语言模型（LLM）抽象层，提供统一的接口调用不同的 LLM 提供商。

### 核心特性
- **统一接口**: 所有 LLM 提供商都实现相同的 `LLMProvider` 接口
- **Function Calling 支持**: 完整的工具调用功能
- **可配置性**: 通过配置文件灵活切换提供商和模型
- **测试友好**: Mock 提供商支持智能工具调用生成

## 模块结构

```
src/simu_emperor/llm/
├── base.py          # 抽象基类 (LLMProvider)
├── anthropic.py     # Anthropic Claude 实现
├── openai.py        # OpenAI GPT 实现
└── mock.py          # Mock 测试实现
```

## 架构示意图

### 模块类图

```mermaid
classDiagram
    abstract class LLMProvider {
        <<abstract>>
        +call(prompt, system_prompt, temperature, max_tokens) str
        +call_with_functions(prompt, functions, system_prompt, temperature, max_tokens) dict
        +get_context_window_size() int
    }

    class AnthropicProvider {
        -client: AsyncAnthropic
        -model: str
        -_context_window: int
        +call(prompt, system_prompt, temperature, max_tokens) str
        +call_with_functions(prompt, functions, system_prompt, temperature, max_tokens) dict
        +get_context_window_size() int
    }

    class OpenAIProvider {
        -client: AsyncOpenAI
        -model: str
        -_context_window: int
        +call(prompt, system_prompt, temperature, max_tokens) str
        +call_with_functions(prompt, functions, system_prompt, temperature, max_tokens, messages) dict
        +get_context_window_size() int
    }

    class MockProvider {
        -response: str
        -tool_calls: list~dict~
        -call_count: int
        +call(prompt, system_prompt, temperature, max_tokens) str
        +call_with_functions(prompt, functions, system_prompt, temperature, max_tokens, messages) dict
        +set_response(response) None
        +set_tool_calls(tool_calls) None
        +reset() None
        -_generate_smart_tool_calls(prompt, system_prompt) list~dict~
        -_extract_event_type(prompt, system_prompt) str
    }

    class Agent {
        -llm: LLMProvider
        -agent_id: str
        +process_event(event) None
    }

    LLMProvider <|-- AnthropicProvider
    LLMProvider <|-- OpenAIProvider
    LLMProvider <|-- MockProvider

    Agent "1" --> "1" LLMProvider : 使用
```

### 提供商特性对比

```mermaid
graph TD
    subgraph "LLM 模块架构"
        LLMProvider["LLMProvider<br/>(抽象接口)"]

        subgraph "实现类"
            Anthropic["AnthropicProvider<br/>Claude API<br/>- claude-sonnet-4-20250514<br/>- 128K 上下文"]
            OpenAI["OpenAIProvider<br/>GPT API<br/>- gpt-4o<br/>- 自定义 Base URL<br/>- 8K+ 上下文"]
            Mock["MockProvider<br/>测试模式<br/>- 智能工具生成<br/>- 多轮对话模拟<br/>- 离线运行"]
        end

        subgraph "集成模块"
            AgentModule["Agent 模块<br/>- 获取 LLM 响应<br/>- Function Calling<br/>- 事件处理"]
        end
    end

    LLMProvider --> Anthropic
    LLMProvider --> OpenAI
    LLMProvider --> Mock

    AgentModule -.->|"依赖注入"| LLMProvider

    style LLMProvider fill:#e1f5fe
    style Anthropic fill:#fff3e0
    style OpenAI fill:#f3e5f5
    style Mock fill:#e8f5e9
    style AgentModule fill:#fce4ec
```

## 接口设计

### LLMProvider 抽象接口

```python
class LLMProvider(ABC):
    async def call(
        prompt: str,
        system_prompt: str | None = None,
        temperature: float = 0.7,
        max_tokens: int = 2000,
    ) -> str

    async def call_with_functions(
        prompt: str,
        functions: list[dict[str, Any]],
        system_prompt: str | None = None,
        temperature: float = 0.7,
        max_tokens: int = 2000,
    ) -> dict[str, Any]

    def get_context_window_size() -> int
```

## 各提供商实现

### AnthropicProvider
- 使用 `anthropic` SDK 调用 Claude API
- 支持工具调用（tools）
- 模型：`claude-sonnet-4-20250514`

### OpenAIProvider
- 使用 `openai` SDK 调用 GPT API
- 支持自定义 API Base URL
- 模型：`gpt-4o`

### MockProvider
- 完全离线的测试实现
- 智能工具调用生成
- 支持多轮对话模拟

## Function Calling 支持

### 统一工具格式

```mermaid
graph LR
    subgraph "工具定义格式"
        A["函数Schema<br/>(OpenAI格式)"]
        B["Anthropic格式<br/>(tools)"]
        C["OpenAI格式<br/>(tools)"]
    end

    subgraph "转换过程"
        D["call_with_functions()"]
    end

    A -->|"统一输入"| D
    D -->|"转换为"| B
    D -->|"转换为"| C

    style A fill:#e3f2fd
    style D fill:#fff9c4
    style B fill:#ffccbc
    style C fill:#c8e6c9
```

### 工具函数格式
```python
function_schema = {
    "name": "function_name",
    "description": "函数描述",
    "parameters": {
        "type": "object",
        "properties": {...},
        "required": [...]
    }
}
```

### 提供商格式转换

| 提供商 | 输入格式 | 转换后格式 |
|--------|----------|------------|
| AnthropicProvider | OpenAI Schema | `{"name": str, "description": str, "input_schema": {...}}` |
| OpenAIProvider | OpenAI Schema | `{"type": "function", "function": {...}}` |
| MockProvider | OpenAI Schema | 智能生成 tool_calls |

## 运行流程

### LLM 调用流程

```mermaid
sequenceDiagram
    participant Agent as Agent 模块
    participant Provider as LLMProvider
    participant API as LLM API

    Agent->>Provider: call(prompt, system_prompt, temp, max_tokens)
    activate Provider

    alt AnthropicProvider
        Provider->>API: client.messages.create()
        API-->>Provider: Response
        Provider->>Provider: response.content[0].text
    else OpenAIProvider
        Provider->>API: client.chat.completions.create()
        API-->>Provider: Response
        Provider->>Provider: response.choices[0].message.content
    else MockProvider
        Provider->>Provider: 返回预定义 response
    end

    Provider-->>Agent: str (响应文本)
    deactivate Provider
```

### Function Calling 完整流程

```mermaid
sequenceDiagram
    participant Agent as Agent 模块
    participant Provider as LLMProvider
    participant API as LLM API
    participant Tools as 工具执行器

    Agent->>Provider: call_with_functions(prompt, functions)
    activate Provider

    Note over Provider: 1. 格式转换
    Provider->>Provider: 转换 functions 为提供商格式

    Note over Provider,API: 2. 首次 API 调用
    Provider->>API: 发送消息 + tools 定义
    API-->>Provider: 返回响应 + tool_calls

    Provider-->>Agent: 返回 tool_calls 列表
    deactivate Provider

    loop 对每个 tool_call
        Agent->>Tools: 执行工具函数
        Tools-->>Agent: 返回执行结果
        Agent->>Agent: 将结果添加到 messages
    end

    Agent->>Provider: call_with_functions(messages=messages)
    activate Provider

    Note over Provider,API: 3. 后续 API 调用
    Provider->>API: 发送完整对话历史
    API-->>Provider: 返回最终响应
    Provider-->>Agent: 返回最终 response_text
    deactivate Provider
```

### 错误处理流程

```mermaid
flowchart TD
    Start[开始调用 LLM] --> TryCatch{try-except}

    TryCatch -->|成功| Success[返回响应]
    TryCatch -->|异常| Catch[捕获异常]

    Catch --> LogError[记录错误日志<br/>logger.error + exc_info]
    LogError --> Raise[重新抛出异常]

    Success --> End[结束]
    Raise --> End

    style Start fill:#e8f5e9
    style Success fill:#c8e6c9
    style Catch fill:#ffebee
    style LogError fill:#fff3e0
    style Raise fill:#ffcdd2
    style End fill:#f5f5f5
```

### Mock Provider 智能工具生成流程

```mermaid
flowchart TD
    Start[call_with_functions 调用] --> CheckMessages{有 messages?}

    CheckMessages -->|是| ExtractPrompt[从 messages 提取最后一条 user 消息]
    CheckMessages -->|否| UsePrompt[使用 prompt 参数]

    ExtractPrompt --> CheckToolResults{有 tool 结果?}
    UsePrompt --> CheckPredefined{有预定义 tool_calls?}

    CheckToolResults -->|是| ReturnFinal[返回最终响应<br/>结束多轮对话]
    CheckToolResults -->|否| CheckPredefined

    CheckPredefined -->|是列表| CheckCallCount{第一次调用?}
    CheckPredefined -->|None| SmartGen[智能生成 tool_calls]
    CheckPredefined -->|空列表| ReturnEmpty[返回空 tool_calls]

    CheckCallCount -->|是| ReturnPredefined[返回预定义 tool_calls]
    CheckCallCount -->|否| ReturnEmpty

    SmartGen --> ExtractType[_extract_event_type<br/>提取事件类型]
    ExtractType --> EventType{事件类型?}

    EventType -->|COMMAND| GenCommand[生成 send_game_event<br/>+ send_message_to_agent<br/>+ respond_to_player]
    EventType -->|QUERY| GenQuery[生成 query_national_data<br/>+ respond_to_player]
    EventType -->|CHAT| GenChat[生成 respond_to_player]
    EventType -->|UNKNOWN| GenDefault[生成默认 respond_to_player]

    GenCommand --> ReturnCalls[返回 tool_calls]
    GenQuery --> ReturnCalls
    GenChat --> ReturnCalls
    GenDefault --> ReturnCalls

    ReturnFinal --> End[结束]
    ReturnPredefined --> End
    ReturnEmpty --> End
    ReturnCalls --> End

    style Start fill:#e8f5e9
    style SmartGen fill:#fff9c4
    style ReturnFinal fill:#c8e6c9
    style ReturnCalls fill:#c8e6c9
    style End fill:#f5f5f5
```

## 配置管理

### 环境变量
```bash
SIMU_LLM_PROVIDER=anthropic
SIMU_LLM_API_KEY=your-api-key
SIMU_LLM_MODEL=claude-sonnet-4-20250514
SIMU_LLM_CONTEXT_WINDOW=128000
```

### YAML 配置
```yaml
llm:
  provider: anthropic
  api_key: your-api-key
  model: claude-sonnet-4-20250514
  context_window: 128000
```

### 上下文窗口配置流程

```mermaid
graph TD
    subgraph "上下文窗口获取流程"
        A[调用 get_context_window_size] --> B{_context_window 已设置?}
        B -->|是| C[返回配置的值]
        B -->|否| D[返回默认值 8000]
    end

    subgraph "配置来源"
        E[config.py<br/>LLM_CONFIG]
        F[环境变量<br/>SIMU_LLM_CONTEXT_WINDOW]
    end

    E -->|初始化时注入| B
    F -->|初始化时注入| B

    style A fill:#e3f2fd
    style C fill:#c8e6c9
    style D fill:#fff9c4
```

## 开发约束

### 错误处理
- 显式错误信息
- API 调用错误处理
- 记录详细日志

### 异步模式
- 使用 async/await
- 并发调用使用 `asyncio.gather`

### 测试策略
- Mock Provider 用于单元测试
- 智能工具生成验证
