# Rich Content Blocks Spec (Phase 2)

> Frontend 富内容渲染规范，参考 clowder-ai 的 Rich Content Block 设计。
> Phase 1（组件拆分 + Zustand + Agent 视觉身份）完成后开始实施。

## 设计原则

1. **结构化优于纯文本** — TapeEvent 的 payload 包含结构化数据，应以卡片/表格等形式渲染，而非 JSON dump
2. **折叠优先** — 详细信息默认折叠，一级信息直接可见
3. **Agent 身份贯穿** — 每个 block 继承所属 Agent 的颜色系统
4. **三层分离** — 遵循 Phase 1 建立的消息分层：Agent 对话 / 系统事件 / 工具执行

## Block 类型定义

### 1. ToolCallBlock

**触发条件：** `event.type === "tool_call"`

**Payload 结构（来自 `react.py:_record_tool_calls`）：**
```typescript
interface ToolCallPayload {
  reasoning: string;         // LLM 的推理过程
  tool_calls: {
    name: string;            // 工具名称
    arguments: Record<string, unknown>;  // 工具参数
  }[];
}
```

**渲染方案：**
```
┌─ 🔧 工具调用 ──────────────────────────────────────┐
│                                                       │
│  [reasoning 文本，markdown 渲染，默认折叠]              │
│                                                       │
│  ┌─ send_message ─────────────────────────────┐      │
│  │  recipients: ["governor_zhili"]             │      │
│  │  message: "请问直隶今年税收情况..."           │      │
│  └────────────────────────────────────────────┘      │
│  ┌─ query_state ──────────────────────────────┐      │
│  │  path: "provinces.zhili"                    │      │
│  └────────────────────────────────────────────┘      │
└───────────────────────────────────────────────────────┘
```

**组件接口：**
```typescript
interface ToolCallBlockProps {
  reasoning: string;
  toolCalls: { name: string; arguments: Record<string, unknown> }[];
  agentColor: string;  // 从 agent-tokens 获取
}
```

**交互：**
- reasoning 默认折叠，点击展开
- 每个 tool call 显示为独立小卡片
- arguments 中已知字段特殊渲染（如 recipients 显示为 badge 列表）

---

### 2. ToolResultBlock

**触发条件：** `event.type === "tool_result"`

**Payload 结构（来自 `react.py:_record_tool_result`）：**
```typescript
interface ToolResultPayload {
  tool: string;           // 工具名称
  arguments: Record<string, unknown>;  // 调用参数
  result: string;         // 执行结果（可能是 JSON string）
  ends_loop?: boolean;    // 是否终止 ReAct 循环
}
```

**渲染方案：**
```
┌─ ✅ query_state 结果 ─────────────────────────────┐
│  path: "provinces.zhili"                            │
│  ┌─ 结果 ───────────────────────────────────────┐  │
│  │  production_value: 125,000                    │  │
│  │  population: 3,200,000                        │  │
│  │  tax_modifier: +0.02                          │  │
│  └───────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────┘
```

**特殊工具渲染：**

| 工具 | 渲染方式 |
|------|---------|
| `query_state` | 尝试 JSON.parse result，以表格渲染省份/国家数据 |
| `send_message` | 显示消息预览 + 收件人 badge |
| `create_incident` | 渲染为 IncidentBlock（见下） |
| `search_memory` | 记忆检索结果列表 |
| 其他 | 默认纯文本/代码块 |

**组件接口：**
```typescript
interface ToolResultBlockProps {
  tool: string;
  arguments: Record<string, unknown>;
  result: string;
  endsLoop?: boolean;
  agentColor: string;
}
```

---

### 3. IncidentBlock

**触发条件：** `event.type === "incident_created"` 或 ToolResult 中 `tool === "create_incident"`

**渲染方案：**
```
┌─ ⚡ 事件：江南水患 ──────────────────────────────────┐
│  来源: governor_jiangnan (江南巡抚)                     │
│  持续: 3 个 tick                                       │
│                                                        │
│  影响:                                                 │
│  ┌──────────────────────────────────────────────────┐  │
│  │  📉 江南产值增长率  ×0.8  (-20%)                  │  │
│  │  📈 江南税率修正    +0.05                         │  │
│  └──────────────────────────────────────────────────┘  │
│                                                        │
│  描述: 连日暴雨导致江南多地受灾，产值增长放缓...         │
└────────────────────────────────────────────────────────┘
```

**组件接口：**
```typescript
interface IncidentBlockProps {
  title: string;
  description: string;
  source: string;
  remainingTicks: number;
  effects: {
    target_path: string;
    add: string | null;
    factor: string | null;
  }[];
}
```

**效果展示规则：**
- `factor` 显示为百分比变化（如 `0.8` → `-20%`）
- `add` 显示为绝对值变化（如 `0.05` → `+0.05`）
- `target_path` 解析为可读名称（如 `provinces.jiangnan.production_growth` → `江南产值增长率`）

---

### 4. TaskSessionBlock

**触发条件：** `event.type === "task_created" | "task_finished" | "task_failed" | "task_timeout"`

**Payload 结构：**
```typescript
// task_created
interface TaskCreatedPayload {
  goal: string;
  task_session_id: string;
  parent_session_id: string;
  depth: number;
}

// task_finished
interface TaskFinishedPayload {
  task_session_id: string;
  result: string;
  status: "completed";
}

// task_failed / task_timeout
interface TaskFailedPayload {
  task_session_id: string;
  reason: string;
  status: "failed" | "timeout";
}
```

**渲染方案：**
```
┌─ 📋 任务会话 ────────────────────────────────────────┐
│  🟢 已完成                                            │
│  目标: 协调各省税收调整方案                              │
│  会话: task:abc123...                                  │
│  层级: 2 / 5                                          │
│                                                       │
│  [展开查看子会话事件]                                   │
│                                                       │
│  结果: 已与直隶巡抚和户部尚书达成共识，建议...            │
└───────────────────────────────────────────────────────┘
```

**状态颜色：**
- `task_created`: 蓝色 🔵
- `task_finished`: 绿色 🟢
- `task_failed`: 红色 🔴
- `task_timeout`: 橙色 🟠

**交互：**
- 子会话事件可展开查看（调用 `/api/tape/subsessions` 获取）
- 深度用进度条展示（depth / MAX_TASK_DEPTH）

---

### 5. SystemNoticeBar

**触发条件：** `event.type === "tick_completed" | "system" | "shutdown" | "reload_config"`

**渲染方案：** 全宽通知栏，不使用气泡样式

```
──── ⏰ 雍正2年3月 第2周 ── 国库: 1,250,000 (+12,500) ── 人口: 15,200,000 (+50,000) ────
```

```
──── ⚠️ 系统: agent governor_zhili 已重新加载配置 ────
```

**组件接口：**
```typescript
interface SystemNoticeBarProps {
  type: "tick" | "system" | "shutdown" | "reload";
  payload: Record<string, unknown>;
  timestamp: string;
}
```

---

### 6. AgentMessageBlock（增强）

**触发条件：** `event.type === "agent_message"` 且 `dst` 包含其他 agent

**场景：** Agent 之间的对话（非回复玩家的消息）

**渲染方案：**
```
┌─ 💬 江南巡抚 → 户部尚书 ─────────────────────────────┐
│                                                       │
│  关于今年江南的税收调整，我有以下建议...                  │
│  [markdown 正文]                                       │
│                                                       │
│  ⏳ 等待回复中...                                      │
└───────────────────────────────────────────────────────┘
```

**增强点：**
- 显示消息路由方向（src → dst）
- 等待回复时显示 pending 状态
- agent-to-agent 消息用虚线边框区分于 agent-to-player

---

## Block 选择器逻辑

```typescript
// components/rich/BlockSelector.tsx

function selectBlock(event: TapeEvent): React.ComponentType<any> | null {
  const type = event.type.toLowerCase();
  
  switch (type) {
    case 'tool_call':
      return ToolCallBlock;
    case 'tool_result':
      return ToolResultBlock;
    case 'incident_created':
      return IncidentBlock;
    case 'task_created':
    case 'task_finished':
    case 'task_failed':
    case 'task_timeout':
      return TaskSessionBlock;
    case 'tick_completed':
    case 'system':
    case 'shutdown':
    case 'reload_config':
      return SystemNoticeBar;
    case 'agent_message':
      // agent-to-agent 用增强渲染，agent-to-player 用普通气泡
      if (!event.dst.some(d => d.startsWith('player'))) {
        return AgentMessageBlock;
      }
      return null; // 使用默认 MessageBubble
    default:
      return null; // 使用默认 MessageBubble
  }
}
```

## 在 TAPE CONTEXT 面板中的展示

TAPE CONTEXT（右侧面板底部）显示原始事件流，应使用 block 系统渲染：

- 所有事件类型都应通过 `BlockSelector` 渲染
- 与聊天区的区别：TAPE CONTEXT 显示**全部**事件（包括 tool_call/tool_result），聊天区只显示对话
- TAPE CONTEXT 中的 block 默认折叠，节省空间

## 目标路径可读名称映射

```typescript
// theme/path-labels.ts

const PATH_LABELS: Record<string, string> = {
  'imperial_treasury': '国库',
  'base_tax_rate': '基础税率',
  'tribute_rate': '上缴率',
  'fixed_expenditure': '固定支出',
  'provinces.jiangnan.production_value': '江南产值',
  'provinces.jiangnan.population': '江南人口',
  'provinces.jiangnan.tax_modifier': '江南税率修正',
  'provinces.jiangnan.production_growth': '江南产值增长率',
  'provinces.jiangnan.population_growth': '江南人口增长率',
  'provinces.zhili.production_value': '直隶产值',
  'provinces.zhili.population': '直隶人口',
  'provinces.zhili.tax_modifier': '直隶税率修正',
  'provinces.zhili.production_growth': '直隶产值增长率',
  'provinces.zhili.population_growth': '直隶人口增长率',
  // ... 动态生成：通过 agent 列表 + 省份列表组合
};

function resolvePathLabel(path: string): string {
  return PATH_LABELS[path] || path;
}
```

## 依赖

Phase 2 不引入新的 npm 依赖：
- Markdown 渲染：复用现有 `react-markdown` + `remark-gfm`
- 图标：复用现有 `lucide-react`
- 样式：Tailwind + CSS custom properties（Phase 1 已建立）

## 文件结构

```
src/components/rich/
├── BlockSelector.tsx         # 根据 event.type 选择 block 组件
├── ToolCallBlock.tsx         # 工具调用渲染
├── ToolResultBlock.tsx       # 工具结果渲染
├── IncidentBlock.tsx         # 事件卡片
├── TaskSessionBlock.tsx      # 任务会话卡片
├── SystemNoticeBar.tsx       # 系统通知栏
├── AgentMessageBlock.tsx     # Agent 间消息增强渲染
└── shared/
    ├── CollapsibleSection.tsx  # 可折叠区域
    ├── JsonTable.tsx           # JSON 对象表格渲染
    └── AgentBadge.tsx          # Agent 标识（复用 Phase 1）
```

## 实施顺序

1. `BlockSelector` + `SystemNoticeBar`（最简单，验证 block 选择机制）
2. `ToolCallBlock` + `ToolResultBlock`（频率最高的事件类型）
3. `IncidentBlock`（游戏核心功能可视化）
4. `TaskSessionBlock`（任务会话层级展示）
5. `AgentMessageBlock`（增强 agent 间通信展示）
6. TAPE CONTEXT 面板集成（全部事件用 block 渲染）
