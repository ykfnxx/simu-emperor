---
name: create_incident
description: 创建持续 N 个 tick 的游戏事件，对省份或国家数据产生影响
version: "1.0"
author: System
tags:
  - incident
  - game_effect
priority: 10
required_tools:
  - create_incident
---

# 创建游戏事件

## 任务说明
创建一个持续 N 个 tick 的游戏事件（Incident），对游戏状态产生影响。

## 效果类型

### add（一次性数值变化）
- **作用**: 一次性改变数值，仅在事件首次生效时应用
- **允许目标**:
  - `provinces.{province_id}.stockpile` - 省级库存
  - `nation.imperial_treasury` - 国库
- **示例**: 拨款 +5000，消耗 -1000

### factor（持续比例变化）
- **作用**: 每个 tick 都会生效的比例变化
- **允许目标**:
  - `provinces.{province_id}.production_value` - 省级产值
  - `provinces.{province_id}.population` - 省级人口
- **示例**: 产值 +10% (factor=0.1)，人口 -5% (factor=-0.05)

## 参数说明

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| title | string | ✓ | 事件标题 |
| description | string | ✓ | 事件描述 |
| effects | array | ✓ | 效果列表 |
| effects[].target_path | string | ✓ | 目标路径 |
| effects[].add | number | ✗ | 一次性数值（与 factor 二选一） |
| effects[].factor | number | ✗ | 比例变化（与 add 二选一） |
| duration_ticks | integer | ✓ | 持续 tick 数（≥1） |

## 示例

### 示例 1：拨款事件（add 类型）

```json
{
  "title": "直隶救灾拨款",
  "description": "因直隶水灾，国库拨付白银赈济灾民",
  "effects": [
    {
      "target_path": "provinces.zhili.stockpile",
      "add": 10000
    },
    {
      "target_path": "nation.imperial_treasury",
      "add": -10000
    }
  ],
  "duration_ticks": 1
}
```

### 示例 2：政策效果（factor 类型）

```json
{
  "title": "直隶减税休养",
  "description": "直隶减税以休养生息，产值增长加快",
  "effects": [
    {
      "target_path": "provinces.zhili.production_value",
      "factor": 0.05
    }
  ],
  "duration_ticks": 12
}
```

### 示例 3：混合效果

```json
{
  "title": "直隶农业改革",
  "description": "投入资金并实施改革，促进农业发展",
  "effects": [
    {
      "target_path": "provinces.zhili.stockpile",
      "add": -5000
    },
    {
      "target_path": "provinces.zhili.production_value",
      "factor": 0.1
    },
    {
      "target_path": "provinces.zhili.population",
      "factor": 0.02
    }
  ],
  "duration_ticks": 24
}
```

## 注意事项

1. **add 和 factor 互斥**: 每个 effect 只能指定其中一个
2. **路径校验**: 必须使用允许的目标路径
3. **duration_ticks ≥ 1**: 事件至少持续 1 个 tick
4. **数值精度**: 使用 Decimal 确保精度
