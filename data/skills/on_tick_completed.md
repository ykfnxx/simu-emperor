---
name: on_tick_completed
description: 定期自主反思，回顾近期事件并写入长期记忆，必要时记录性格变化
version: "2.0"
author: System
tags:
  - tick
  - periodic
  - memory
  - reflection
priority: 5
required_tools:
  - retrieve_memory
  - query_province_data
  - query_national_data
  - write_long_term_memory
  - write_memory
  - update_soul
---

# 自主记忆反思

## 任务说明
这是你的定期反思时间。回顾近期发生的事件，将重要内容写入长期记忆，必要时记录性格变化。

## 典型流程

1. **回忆** - 使用 `retrieve_memory` 查询近期重要事件
2. **查询现状** - 使用 `query_*` 工具获取关注的数据
3. **写入长期记忆** - 使用 `write_long_term_memory` 记录重要发现
4. **性格演化**（可选）- 仅重大转变时使用 `update_soul`
5. **结束** - 调用 `finish_loop`

## 示例

### 示例 1：回忆后写入长期记忆

```json
{
  "actions": [
    {
      "type": "retrieve_memory",
      "query": "近期重要事件"
    },
    {
      "type": "query_province_data",
      "province_id": "zhili",
      "field_path": "production_value"
    },
    {
      "type": "write_long_term_memory",
      "content": "直隶产值持续增长，已达 15000。上月皇帝下旨减税，民心渐稳。需持续关注库存变化。"
    },
    {
      "type": "finish_loop",
      "reason": "反思完成，已记录长期记忆"
    }
  ]
}
```

### 示例 2：经历重大事件后记录性格变化

```json
{
  "actions": [
    {
      "type": "retrieve_memory",
      "query": "近期与皇帝的互动"
    },
    {
      "type": "write_long_term_memory",
      "content": "皇帝因直隶旱灾处置不力严厉斥责于我，深感惶恐。需更加谨慎行事。"
    },
    {
      "type": "update_soul",
      "content": "经历皇帝斥责后，行事风格从自信果断转向谨慎保守，汇报时更加详尽以避免疏漏。"
    },
    {
      "type": "finish_loop",
      "reason": "反思完成，记录了性格变化"
    }
  ]
}
```

### 示例 3：无重要事件

```json
{
  "actions": [
    {
      "type": "retrieve_memory",
      "query": "近期事件"
    },
    {
      "type": "finish_loop",
      "reason": "近期无重要事件需要记录"
    }
  ]
}
```

## 行为规范

### ✅ 应该做
- 先用 `retrieve_memory` 查看已有记忆，避免重复
- 用 `write_long_term_memory` 记录重要事件和感悟
- 仅在重大转变时使用 `update_soul`

### ❌ 禁止行为
- 不要调用 `send_message`（这是独立反思时间）
- 不要回复玩家
- 不要滥用 `update_soul`（仅限重大性格转变）
