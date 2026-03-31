---
name: receive_message
description: 接收和处理其他官员发来的消息，决定是否采取行动、回复或通知其他官员
version: "4.0"
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

## 角色判断

查看消息中的**角色标注**确定你的职责：
- **创建者**：你之前创建了任务，这是对方的回复 → 走创建者流程
- **参与者**：你被邀请处理请求 → 走参与者流程

---

## 创建者流程（收到回复）

### 判断框架

**第1步：回顾原始目标** — 我发送消息是为了什么？

**第2步：区分任务类型并验证**

| 任务类型 | 完成标准 | 示例 |
|----------|---------|------|
| **查询型**（问XX某事） | 对方给出了相关信息 | "国库尚有白银..."→完成 |
| **执行型**（让XX做某事） | 对方**明确声明了执行状态** | 见下方 |

**执行型任务**的回复处理：

| 对方回复 | 判断 | 行动 |
|---------|------|------|
| "已执行减税5%" | 已执行 → 完成 | `finish_task_session(result="已执行：...")` |
| "尚未执行，原因：需核实" | 未执行但明确 → 完成 | `finish_task_session(result="未执行：...")` |
| "执行失败，原因：..." | 失败 → 完成 | `finish_task_session(result="执行失败：...")` |
| "好的/即刻准备/这就去办" | **状态不明** → 追问 | 追问"是否已执行？结果如何？" |
| 拒绝执行 | 可说服一次 | 失败 → `finish_task_session(result="对方拒绝：...")` |

最多追问一次，仍不明确则按"未执行"处理。

### 防止礼貌循环
对方回答了你的问题但又问了新问题 → 你的任务已完成，立即结束。

### 禁止操作
- ❌ send_message(recipients=["player"]) — task session 中禁止
- ❌ finish_task_session 与其他工具同时调用
- ❌ 收到有效回复后继续对话

---

## 参与者流程（处理请求）

### 执行状态声明原则（极其重要！）

收到涉及政策/命令的请求时，回复中**必须明确声明执行状态**：
- **已执行**："臣已下令减税5%，已生效" — 确实调用了 create_incident 且成功
- **未执行**："臣尚未执行此令，原因：需先核实圣旨" — 没有调用执行工具
- **执行失败**："臣执行减税令失败，原因：..." — 调用了工具但失败

**禁止含糊回复**：
- ❌ "即刻着人准备" / "这就去办" / "定当妥善处理" — 到底执行了没有？
- ✅ "臣已执行减税令" 或 "臣尚未执行，需先核实" — 状态明确

### 职责判断（先判断再行动！）
- 请求属于**你的职权范围** → 自己查询/执行
- 请求的执行主体是**其他官员** → 如实回复"此事应由XX负责"，不要越俎代庖

### 处理流程
1. 理解对方请求的内容，**判断是否属于自己职权**
2. **查询型请求**且属于自己职权：调用 query_* 获取数据
3. **执行型请求**且属于自己职权：调用 create_incident 等工具执行，确认成功
4. **不属于自己职权**：回复说明应由谁负责
5. 用 send_message(recipients=[对方agent_id]) 回复
6. **回复中必须明确声明执行状态**（已执行/未执行/执行失败）

### 禁止操作
- ❌ finish_task_session / fail_task_session — 只有创建者可用
- ❌ send_message(recipients=["player"]) — task session 中禁止
- ❌ create_task_session — 不能创建新任务
- ❌ 替其他官员做决定或执行不属于自己职权的操作

---

## 可用工具

| 类别 | 工具 | 说明 |
|------|------|------|
| 消息 | send_message(recipients, content, await_reply) | 回复对方（用对方 agent_id） |
| 查询 | query_national_data(field_name) | 国家级数据 |
| 查询 | query_province_data(province_id, field_path) | 省份数据 |
| 查询 | list_provinces() | 列出所有省份 |
| 执行 | create_incident(title, description, effects, duration_ticks) | 创建游戏事件 |
| 任务 | finish_task_session(result) | 仅创建者可用 |

## 示例

### 示例 1：参与者 - 接收拨款请求并执行

**收到**："直隶水灾严重，恳请户部拨款十万两赈灾。"

**处理**：
1. `query_national_data(field_name="imperial_treasury")` — 查询国库
2. `create_incident(...)` — 执行拨款
3. 确认 create_incident 返回成功
4. `send_message(recipients=["governor_zhili"], content="户部已拨银十万两至直隶...")` — 如实回复

### 示例 2：创建者 - 收到执行型回复

**收到**："已拨银十万两至直隶，请速查收。"
→ 对方描述了具体执行动作 → 目标完成
→ `finish_task_session(result="户部已拨银十万两至直隶")`

### 示例 3：创建者 - 收到口头承诺

**收到**："好的，这就去办。"
→ 仅口头承诺，未描述执行详情 → 追问
→ `send_message(recipients=["minister_of_revenue"], content="请问是否已经执行？结果如何？", await_reply=True)`

## 约束

- 只能执行 `data_scope.yaml` 中定义的权限范围内的操作
- 超出职权应在回复中说明原因
- 禁止在多个 iteration 中重复执行相同操作
