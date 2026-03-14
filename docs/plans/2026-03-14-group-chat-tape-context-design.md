# 群聊TAPE CONTEXT双选择器设计

## 概述

为群聊模式下的TAPE CONTEXT增加Agent选择器，允许用户查看群聊中不同agent的tape记录。

## 背景

### 当前问题
1. TAPE CONTEXT只显示单个agent (`currentAgentId`) 的sessions
2. 群聊模式有多个agents参与，无法切换查看不同agent的tape
3. 后端群聊消息未实际发送给agents

### 数据模型澄清
- 群聊使用同一个session（如 `session:web:main`）
- 每个agent独立记录自己收到的事件到各自的tape
- 不存在"公共群聊tape"

## UI设计

### 布局结构

```
┌─────────────────────────────────────┐
│ TAPE CONTEXT              XX 条      │
├─────────────────────────────────────┤
│ 🟣 群聊: [群聊名称]                  │
├─────────────────────────────────────┤
│ Agent: [Agent名称 ▼] ← 下拉选择器    │
├─────────────────────────────────────┤
│ Session: [主会话 ▼] ← 和私聊一致     │
│   ├─ 主会话                          │
│   └─ 子会话1 (task:xxx)             │
├─────────────────────────────────────┤
│ Tape事件列表                         │
│ └─ 显示选中agent的事件               │
└─────────────────────────────────────┘
```

### 非群聊模式（保持不变）

```
┌─────────────────────────────────────┐
│ TAPE CONTEXT              XX 条      │
├─────────────────────────────────────┤
│ Agent: [当前Agent] ← 非下拉，固定显示 │
├─────────────────────────────────────┤
│ Session: [主会话 ▼]                  │
└─────────────────────────────────────┘
```

## 设计决策

| 决策点 | 选择 |
|--------|------|
| Agent选择方式 | 下拉菜单，单选 |
| 默认Agent | 群聊的第一个agent |
| Session范围 | 当前群聊session的子sessions |
| 显示内容 | 选中agent的tape事件 |
| 与私聊差异 | 仅增加Agent选择器，Session逻辑复用 |

## 技术实现

### 前端状态管理

```typescript
// 新增状态
const [selectedGroupAgentId, setSelectedGroupAgentId] = useState<string | null>(null);

// 派生逻辑
const viewAgentId = selectedGroupAgentId ?? currentAgentId;

// 非群聊模式: selectedGroupAgentId = null, 使用 currentAgentId
// 群聊模式: selectedGroupAgentId = 群聊中选中的agent
```

### 行为逻辑

1. **进入群聊**：`selectedGroupAgentId` 自动设置为群聊第一个agent
2. **切换Agent**：重新加载选中agent的tape
3. **切换Session**：基于 `viewAgentId` 加载子sessions
4. **退出群聊**：`selectedGroupAgentId` 重置为 `null`

### API需求

#### 新增：获取群聊信息

```typescript
interface GroupChatDetail extends GroupChat {
  agents: AgentInfo[];  // 群聊中agents的详细信息（含display_name）
}
```

前端已有 `agentSessions` 数据，无需额外API。

## 实现任务

### Phase 1: 修复核心bug
1. 后端：修复群聊消息实际发送给agents
2. 前端：选择群聊后刷新chatTape

### Phase 2: 群聊TAPE CONTEXT
1. 前端：添加 `selectedGroupAgentId` 状态
2. 前端：添加Agent下拉选择器UI（仅群聊模式显示）
3. 前端：调整tape加载逻辑使用 `viewAgentId`
4. 前端：调整子session加载逻辑使用 `viewAgentId`

## 测试验证

- [ ] 群聊消息能发送给所有agents
- [ ] 选择群聊后chatTape正确显示
- [ ] TAPE CONTEXT显示Agent选择器（仅群聊模式）
- [ ] 切换Agent后tape正确更新
- [ ] 切换Session后子session列表正确（基于选中Agent）
- [ ] 退出群聊后Agent选择器消失
