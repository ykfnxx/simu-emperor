# Simu-Emperor

<!-- impeccable:product-schema 1 -->

## Platform

web

## Stack

全栈 TypeScript 实现：前端采用 Next.js 16 静态导出 / React 19（`web/`），后端采用 Node.js 24+（`Hono` + 内置 `node:sqlite`，`src/`），外部官员调用器采用 `@botiverse/oar@0.84.0`（`src/officers/`，支持 `--once` 与 `--watch` 模式）。

## Users

玩家扮演君主，通过地图、官员奏报、交涉和批复治理国家。外部 Agent 扮演官员，由用户选择和运行。

## Product Purpose

从头重写一款类似 Paradox EU4 的浏览器策略游戏。地图是主要操作空间，玩家通过地方信息和官员协作作出资源取舍，并观察按周产生的施政结果。

## Operating Context

- 首轮聚焦内政、财政与救灾。
- 游戏按周推进，玩家手动结束征询并批复提案。
- 外部官员程序使用 OAR 运行原生 Agent，并与游戏服务通信；游戏服务不托管用户的模型密钥。
- 正常游戏依靠奏报了解状态，调试时可查看真实状态。
- 当前采用明代两京十三省，陕西、河南、湖广参与四回合试玩，其余十二个省级单位冻结。预设人物可任免，人物与职务分离。

## Capabilities and Constraints

- 整体重写，旧 Python / EventBus 业务与旧聊天页面已移除，不作为新实现的一部分。
- 地图、奏报、官员对话、正式提案和真实资源结算分别承担明确职责。
- 由游戏服务控制权威状态、预算、权限与周结算。对话承诺和奏报数字不能直接修改账目。
- 普通页面的地图着色与数据严格遵守奏报可见性；未收到报告时显示斜纹与“本周未奏报（未知）”，不用零值代替。
- 官员通信和交互参考 Cumora 的参与者隔离、点名唤醒与串行批次机制；不接入其整套聊天产品或部署架构。
- 地图采用江山图明末 `s_ming_c`（1636–1643）图层，固定源提交与资源许可见 [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md)。省份几何 ID 与游戏身份显式映射。

## Brand Commitments

空间布局参考 EU4（左上经济、人口、人才入口，左侧共用可收起省份与政务面板，右上日期与回合操作，右下地图控制），整体视觉风格与底图直接参考并适配 [江山时序（`DeanChensj/jiangshan-map`）](https://github.com/DeanChensj/jiangshan-map) 的简约浅色历史地图界面。保留大面积连续地图、地貌晕渲、干支流水系、分级标注、五种状态图例、时间与地区操作的联系；使用温暖浅米白卡片、细分割线、宋体标题/键值与朱砂重点色，不使用繁复画框、纹章、奇幻插画或深色厚重面板，也不能改成普通管理表格或以聊天记录占据主界面的产品。

## Validation

当前实现的验证以对应 PR 的固定提交、测试和真实页面记录为准。原生模型执行成功、行为评分与完整整局验证分别记录，不互相替代。

## Product Principles

- 从地图中的地区、事件与官员进入操作，保持地理上下文。
- 信息的来源、所属周次和是否已上报应清楚可见。
- 官员可以交涉、建议和执行授权行为，最终资源变更以服务端规则为准。
- 小范围验证缩小模拟规模，仍须验证真实策略游戏的主要操作过程。
- 使用标准、易读的表达，不自造术语。

## Current Design & Implementation Baseline

- 视觉设计系统、设计变量与组件规范见 [DESIGN.md](DESIGN.md) 及 `.impeccable/design.json`（扩展元数据）。
- 人物任职、计划、部分拨款、奏报和聊天接口见 [玩法 API 契约](docs/design/gameplay-api.md)。
- 架构与开发命令见 [CLAUDE.md](CLAUDE.md)，第三方地图代码与资源许可说明见 [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md)。
