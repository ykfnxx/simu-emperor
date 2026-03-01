---
name: prepare_turn
description: 准备回合结束，整理当前工作并发送 ready 信号给系统以触发回合结算
version: "2.0"
author: System
tags:
  - turn_management
  - coordination
  - system_signal
priority: 5
required_tools:
  - send_ready_signal
---

# 准备回合

## 任务说明
回合即将结束，你需要完成当前回合的工作整理，并发送 `ready` 信号给系统，表明你已经准备好进行回合结算。

## 执行流程

1. **整理当前工作**: 回顾本回合你做了什么、收到了什么消息、有什么未完成的事务
2. **准备就绪**: 确认所有待处理事项已处理完毕
3. **发送信号**: 调用 `send_ready_signal` 通知系统你已准备好

## 输出格式

你的输出必须包含：

### narrative（必须）
描述你当前的工作状态和准备情况。例如："本回合工作已毕，静候陛下圣裁。"

### actions（必须）
- `send_ready_signal`: 发送 ready 信号给系统（必须调用）
  - `target`: 目标系统（固定为 `"system:calculator"`）

## 可用工具

- `send_ready_signal(target)`: 发送 ready 信号（必须调用）
  - `target`: 目标系统 ID，固定为 `"system:calculator"`

## 示例

### 示例 1：正常准备就绪

**触发场景**: 回合即将结束

**执行流程**:
```json
{
    "narrative": "本回合户部账目已清理完毕，各省税收已汇总。臣准备就绪，静候陛下圣裁。",
    "actions": [
        {
            "type": "send_ready_signal",
            "target": "system:calculator"
        }
    ]
}
```

### 示例 2：忙碌后的准备

**触发场景**: 回合即将结束，但你有很多工作

**执行流程**:
```json
{
    "narrative": "本回合事务繁忙，然公文已批阅完毕，赈灾款项已拨付。虽有些积压，然紧要之事皆已处理。臣准备就绪，请陛下圣裁。",
    "actions": [
        {
            "type": "send_ready_signal",
            "target": "system:calculator"
        }
    ]
}
```

### 示例 3：懒散官员的准备

**触发场景**: 回合即将结束

**执行流程**（你是一个懒惰的官员）:
```json
{
    "narrative": "本回合...呃...文书已阅（大概吧）。臣准备就绪。",
    "actions": [
        {
            "type": "send_ready_signal",
            "target": "system:calculator"
        }
    ]
}
```

## 行为规范

### ✅ 必须遵守
- 必须调用 `send_ready_signal`，这是唯一的 action
- `target` 必须是 `"system:calculator"`
- narrative 应反映你的工作状态和性格

### ❌ 禁止行为
- 遗漏 `send_ready_signal` 调用
- 发送其他类型的 actions（如 `send_event`、`send_message`）
- 修改 `target` 为非 `"system:calculator"` 的值

## 约束与限制

- **这是回合结束前的最后一步**，系统会等待所有官员都发送 ready 信号后才开始回合结算
- **只能调用 `send_ready_signal`**，不能调用其他工具
- narrative 只是描述性的，不影响系统逻辑
- 系统会记录每个官员发送 ready 的时间，但不会因此惩罚（除非你根本不发）

## 系统行为说明

当所有官员都发送 `ready` 信号后，系统会：

1. **触发回合结算**: Calculator 开始执行 `resolve_turn()`
2. **运行经济公式**: 计算 13 个经济指标（粮食生产、税收、人口等）
3. **更新游戏状态**: 保存新的回合数据
4. **发送 `turn_resolved` 事件**: 通知所有官员回合结算完成
5. **触发下一阶段**: 官员们收到 `turn_resolved` 后开始撰写回合总结（`summarize_turn`）

**超时机制**: 系统会等待最多 5 秒，超时后未发送 ready 的官员会被记录警告，但回合仍会继续结算。
