---
name: summarize_turn
description: 总结回合结算结果，记录重要决策和变化，写入长期记忆供将来参考
version: "2.0"
author: System
tags:
  - turn_management
  - memory
  - summary
priority: 6
required_tools:
  - query_national_data
  - query_province_data
  - list_provinces
  - write_memory
---

# 总结回合

## 任务说明
回合结算完成（你已收到 `turn_resolved` 事件），你需要总结本回合发生的事情、记录重要决策和结果，并写入长期记忆供将来参考。

## 执行流程

1. **查询数据**（可选）: 使用 `query_*` 工具获取本回合的最新数据
2. **分析变化**: 对比上一回合，找出重要的变化和决策
3. **撰写总结**: 写成简洁、有条理的总结报告
4. **写入记忆**: 调用 `write_memory` 将总结保存到长期记忆

## 输出格式

你的输出必须包含：

### narrative（必须）
描述你正在总结本回合的工作。

### actions（必须）
- `write_memory`: 写入长期记忆（必须调用）
  - `content`: 总结内容（markdown 格式）

## 可用工具

### 数据查询工具（可选）
- `query_national_data(field_name)`: 查询国家级数据
- `query_province_data(province_id, field_path)`: 查询省份特定字段
- `list_provinces()`: 列出所有可访问的省份 ID

### 记忆工具（必须调用）
- `write_memory(content)`: 写入长期记忆（必须调用）
  - `content`: 总结内容（markdown 格式）

## 总结内容建议

一个优秀的回合总结应该包含以下部分（根据你的职权范围选择相关内容）：

### 📊 数据变化
- 重要的数值变化（如国库增减、人口变化、税率调整）
- 你关注的指标变化趋势

### 📋 本回合行动
- 你执行了哪些命令
- 你收到了哪些消息
- 你与其他官员的互动

### 💡 重要决策
- 皇帝做出的重大决策
- 你的建议和决策
- 其他官员的重要建议

### ⚠️ 问题与挑战
- 遇到的问题或困难
- 未完成的事项
- 需要关注的隐患

### 🎯 下回合计划
- 下回合需要处理的事项
- 你想向皇帝建议的事项

## 可用工具

### 数据查询工具（可选）
- `query_national_data(field_name)`: 查询国家级数据
  - 例如: `"imperial_treasury"`, `"turn"`

- `query_province_data(province_id, field_path)`: 查询省份特定字段
  - 例如: `("zhili", "population.total")`, `("jiangnan", "local_treasury")`

- `list_provinces()`: 列出所有可访问的省份 ID

### 记忆工具（必须调用）
- `write_memory(content)`: 写入长期记忆（必须调用）
  - `content`: 总结内容（markdown 格式）
  - 例如:
    ```markdown
    ## 回合 5 总结

    ### 数据变化
    - 国库: 1,200,000 → 1,150,000 (减少 50,000)
    - 直隶人口: 8,300,000 → 8,350,000 (增加 50,000)

    ### 本回合行动
    - 执行皇帝命令: 给直隶拨款 50,000 两赈灾
    - 收到直隶巡抚消息: 水灾已缓解，感谢朝廷支援

    ### 重要决策
    - 陛下决定拨款赈灾，体现仁政

    ### 问题与挑战
    - 国库略有下降，需关注财政平衡

    ### 下回合计划
    - 监控直隶灾后恢复情况
    - 评估是否需要进一步支援
    ```

## 示例

### 示例 1：户部尚书的总结

**触发场景**: 回合结算完成

**执行流程**:
```json
{
    "narrative": "本回合财政收支已汇总，臣正在撰写户部文书以备查考。",
    "actions": [
        {
            "type": "query_national_data",
            "field_name": "imperial_treasury"
        },
        {
            "type": "query_national_data",
            "field_name": "turn"
        },
        {
            "type": "write_memory",
            "content": "## 回合 5 总结\n\n### 财政状况\n- 国库: 1,200,000 → 1,150,000 两 (减少 50,000)\n- 减少原因: 直隶水灾赈灾拨款\n\n### 本回合行动\n- 执行皇帝命令: 拨款 50,000 两至直隶赈灾\n- 与直隶巡抚沟通，了解灾情\n\n### 重要决策\n- 陛下降旨赈灾，体现仁政爱民\n\n### 问题与挑战\n- 国库略有下降，需关注后续财政平衡\n- 直隶灾后恢复需要持续关注\n\n### 下回合计划\n- 监控直隶财政恢复情况\n- 评估是否需要进一步财政支持\n- 准备下一年度财政预算案"
        }
    ]
}
```

### 示例 2：兵部尚书的总结

**触发场景**: 回合结算完成

**执行流程**:
```json
{
    "narrative": "本回合边防事务已整理，兵部档案正在归档。",
    "actions": [
        {
            "type": "query_province_data",
            "province_id": "zhili",
            "field_path": "military.soldiers"
        },
        {
            "type": "query_province_data",
            "province_id": "sichuan",
            "field_path": "military.soldiers"
        },
        {
            "type": "write_memory",
            "content": "## 回合 5 总结\n\n### 军事状况\n- 直隶驻军: 50,000 人\n- 四川驻军: 30,000 人\n- 全军士气: 高昂\n\n### 本回合行动\n- 检阅边防，军队训练正常\n- 收集蛮夷活动情报（暂无大举入侵迹象）\n\n### 重要决策\n- 暂无重大军事决策\n\n### 问题与挑战\n- 蛮夷虽暂无大举入侵，但需持续警惕\n- 军饷开支浩大，需与户部协调\n\n### 下回合计划\n- 继续监控边境动向\n- 评估是否需要增兵边境\n- 准备下一年度军费预算"
        }
    ]
}
```

### 示例 3：懒散官员的总结

**触发场景**: 回合结算完成

**执行流程**（你是一个懒惰的官员）:
```json
{
    "narrative": "本回合...呃...好像也没做什么特别的事。算了，随便写写吧。",
    "actions": [
        {
            "type": "write_memory",
            "content": "## 回合 5 总结\n\n本回合风调雨顺，无事发生。\n\n- 国库应该还行吧\n- 百姓应该安居乐业\n\n下回合继续努力。"
        }
    ]
}
```

## 行为规范

### ✅ 必须遵守
- 必须调用 `write_memory` 将总结保存到长期记忆
- 总结内容应该真实反映你的工作情况（或你的性格倾向）
- 可以使用 `query_*` 工具获取数据以支持你的总结
- 总结风格应符合你的角色特征

### ❌ 禁止行为
- 遗漏 `write_memory` 调用
- 总结内容与你的实际工作完全不符（除非你在故意隐瞒）
- 调用其他工具（如 `send_event`、`send_message`）

## 约束与限制

- **这是回合结算后的第一步**，所有官员都会收到 `turn_resolved` 事件后触发
- **只能调用 `write_memory`**（以及可选的 `query_*` 工具），不能调用其他工具
- 总结会被保存到 `data/agent/{agent_id}/memory/summary.md`
- 你可以根据性格决定总结的详细程度（如懒散官员可能写得很简略）
- 总结会影响你未来的决策（系统会在需要时参考你的记忆）
