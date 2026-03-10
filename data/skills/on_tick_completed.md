---
name: on_tick_completed
description: Tick 完成时的周期性通知，Agent 可查询状态并记录观察
version: "1.0"
author: System
tags:
  - tick
  - periodic
  - observation
priority: 5
required_tools:
  - query_province_data
  - query_national_data
  - write_memory
---

# Tick 完成

## 任务说明
游戏时间推进了一个 tick（1周）。你可以查询当前状态并决定是否记录。

## 典型流程

1. **查询状态**（可选）: 使用 `query_*` 工具获取关注的数据
2. **判断是否需要记录**: 是否有重要变化值得记录？
3. **记录或结束**: 写入记忆，或直接结束

## 示例

### 示例 1：查询后记录

```json
{
  "actions": [
    {
      "type": "query_province_data",
      "province_id": "zhili",
      "field_path": "production_value"
    },
    {
      "type": "write_memory",
      "content": "本 tick 直隶产值增长至 12000，库存充裕。"
    },
    {
      "type": "finish_loop"
    }
  ]
}
```

### 示例 2：无需操作

```json
{
  "actions": [
    {
      "type": "finish_loop"
    }
  ]
}
```

## 行为规范

### ✅ 可选操作
- 查询你关注的数据（使用 `query_*` 工具）
- 记录重要的状态变化（使用 `write_memory`）
- 直接结束（调用 `finish_loop`）

### ❌ 禁止行为
- 不要调用 `respond_to_player`
- 不要主动发起行动（如 `send_game_event`、`create_incident`）
- 不要发送消息给其他 Agent
