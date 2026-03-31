---
name: receive_message
description: 接收和处理其他官员发来的消息，决定是否采取行动、回复或通知其他官员
version: "3.0"
author: System
tags:
  - communication
  - inter_agent
  - message_handling
priority: 15
required_tools:
  - send_message
  - query_national_data
  - query_province_data
  - list_provinces
  - create_incident
  - finish_task_session
---

# 接收消息

## 任务说明

你负责接收和处理其他官员发来的消息。查看消息中的**角色标注**来确定你的职责。

## 角色判断（极其重要！）

消息中会标注你在当前 task session 中的角色：

### 创建者（收到回复）

你之前创建了任务并发送了消息，这是对方的回复。

**处理原则**：
- 评估对方是否回应了你的问题/请求
- 如果已回应 → 立即调用 `finish_task_session(result="...")` 结束任务
- 如果未回应 → 继续追问

**禁止**：
- ❌ `send_message(recipients=["player"])` — 任务会话中禁止使用
- ❌ 收到有效回复后继续对话 — 应立即结束任务
- ❌ `finish_task_session` 与其他工具同时调用

**容易出错**：对方回答了你的问题但又问了新问题 → 这时你的任务已完成，立即结束，不要陷入礼貌性社交循环。

### 参与者（处理请求）

你是被邀请到任务中的，需要处理对方的请求。

**可以做的**：
- ✅ `send_message(recipients=["对方agent_id"], content="...")` 回复发送者
- ✅ `query_*` 查询数据
- ✅ `create_incident` 执行政策

**严格禁止**：
- ❌ `finish_task_session` — 只有创建者可以结束任务
- ❌ `fail_task_session` — 只有创建者可以结束任务
- ❌ `send_message(recipients=["player"])` — 任务会话中禁止使用
- ❌ `create_task_session` — 不能创建新任务

## 可用工具

### 消息工具
- `send_message(recipients, content, await_reply)`: 发送消息
  - `recipients`: 接收者列表，如 `["governor_zhili"]`（不要用 `["player"]`）
  - `await_reply`: 是否等待回复（默认 false）

### 查询工具（可选）
- `query_national_data(field_name)`: 查询国家级数据
- `query_province_data(province_id, field_path)`: 查询省份特定字段
- `list_provinces()`: 列出所有可访问的省份 ID

### 执行工具（按需使用）
- `create_incident(title, description, effects, duration_ticks)`: 创建游戏事件
  - effects 中每个元素需要 `target_path` + (`add` 或 `factor`)
  - add 类型：作用于 `provinces.{id}.stockpile` 或 `nation.imperial_treasury`
  - factor 类型：作用于 `provinces.{id}.production_value` 或 `provinces.{id}.population`

### 任务工具（仅创建者）
- `finish_task_session(result)`: 完成任务会话（仅创建者可用）

## 示例

### 示例 1：参与者 - 接收拨款请求并执行

**角色**：参与者
**收到消息**:
```
从: governor_zhili（直隶巡抚）
内容: "直隶水灾严重，恳请户部拨款十万两赈灾。"
```

**处理**:
1. `query_national_data(field_name="imperial_treasury")` — 查询国库
2. `create_incident(title="直隶赈灾拨款", description="拨银十万两赈济直隶水灾", effects=[{"target_path": "provinces.zhili.stockpile", "add": 100000}], duration_ticks=1)`
3. `send_message(recipients=["governor_zhili"], content="户部已拨银十万两至直隶，请速查收用于赈灾安民。")`

### 示例 2：创建者 - 收到回复后结束任务

**角色**：创建者
**收到消息**:
```
从: governor_zhili（直隶巡抚）
内容: "直隶一切安好，百姓安居乐业。"
```

**处理**:
```
finish_task_session(result="李卫回复：直隶一切安好，百姓安居乐业。")
```
→ 单独调用，不要同时调用其他工具！

### 示例 3：参与者 - 简单回复

**角色**：参与者
**收到消息**:
```
从: minister_of_revenue（户部尚书）
内容: "各省税收报表已汇总，请查收。"
```

**处理**:
```
send_message(recipients=["minister_of_revenue"], content="报表收悉，辛苦。")
```

## 行为规范

### ✅ 必须遵守
- 先看角色标注，再决定行为
- 回复对方时使用对方的 agent_id（如 `governor_zhili`），不要用 `"player"`
- 根据你的性格和职权做出合理决策
- 回复风格应符合你的角色特征

### ❌ 禁止行为
- 参与者调用 `finish_task_session` 或 `fail_task_session`
- 在 task session 中 `send_message(recipients=["player"])`
- 创建者收到有效回复后继续对话而不结束任务
- 在同一个事件处理中重复发送相同的消息给同一个官员
- 在多个 LLM iteration 中重复执行相同的 action

## 约束与限制

- 只能执行 `data_scope.yaml` 中 `execute_command` 定义的权限范围内的操作
- 如果请求超出职权，应在回复中说明原因
- 根据消息的重要性和你的性格决定响应方式
