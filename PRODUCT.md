# Simu-Emperor

<!-- impeccable:product-schema 1 -->

## Platform

web

## Stack

全栈 TypeScript 实现：前端采用 React 19 / Vite（`web/`），后端采用 Node.js 24+（`Hono` + 内置 `node:sqlite`，`src/`），外部官员调用器采用 `@botiverse/oar@0.84.0`（`src/officers/`，支持 `--once` 与 `--watch` 模式）。

## Users

玩家扮演君主，通过地图、官员奏报、交涉和批复治理国家。外部 Agent 扮演官员，由用户选择和运行。

## Product Purpose

从头重写一款类似 Paradox EU4 的浏览器策略游戏。地图是主要操作空间，玩家通过地方信息和官员协作作出资源取舍，并观察按周产生的施政结果。

## Operating Context

- 首轮聚焦内政、财政与救灾。
- 游戏按周推进，玩家手动结束征询并批复提案。
- 外部官员程序使用 OAR 运行原生 Agent，并与游戏服务通信；游戏服务不托管用户的模型密钥。
- 正常游戏依靠奏报了解状态，调试时可查看真实状态。
- 当前以三个架空州（`甲州`、`乙州`、`丙州`）、三名官员（`officer_a` 兼领度支、`officer_b`、`officer_c`）、四周试玩剧本进行小范围验证；这是首轮验证范围，不是未来完整帝国版图的上限。

## Capabilities and Constraints

- 整体重写，旧 Python / EventBus 业务与旧聊天页面已移除，不作为新实现的一部分。
- 地图、奏报、官员对话、正式提案和真实资源结算分别承担明确职责。
- 由游戏服务控制权威状态、预算、权限与周结算。对话承诺和奏报数字不能直接修改账目。
- 普通页面的地图着色与数据严格遵守奏报可见性；未收到报告时显示斜纹与“本周未奏报（未知）”，不用零值代替。
- 官员通信和交互参考 Cumora 的参与者隔离、点名唤醒与串行批次机制；不接入其整套聊天产品或部署架构。
- 当前验证实现采用中性的架空三州（`甲州`、`乙州`、`丙州`）与非交互周边区域（`地理背景区（未启用）`），底层地理轮廓、水系与地形晕渲适配自 `DeanChensj/jiangshan-map`（commit `a9cd67c`，GPL-3.0，见 [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md)）。界面以桌面端（`1586×992`、`1440×900`、`1280×800`）为主，并完成 `<=960px`（`390×844`）窄屏适配。

## Brand Commitments

空间布局参考 EU4（顶部度支/周次/阶段操作栏、左侧可收起政务面板、右侧各州奏报总览、右下地图图层与视角控制），整体视觉风格与底图直接参考并适配 [江山时序（`DeanChensj/jiangshan-map`）](https://github.com/DeanChensj/jiangshan-map) 的简约浅色历史地图界面。保留大面积连续地图、地貌晕渲、干支流水系、分级标注、五种状态图例、时间与地区操作的联系；使用温暖浅米白卡片、细分割线、宋体标题/键值与朱砂重点色，不使用繁复画框、纹章、奇幻插画或深色厚重面板，也不能改成普通管理表格或以聊天记录占据主界面的产品。

## Evidence on Hand

- 全栈 TypeScript 服务端（`src/`）、OAR 官员调用器（`src/officers/`）与简约地图界面前端（`web/`）已在当前开发分支完成实装，并通过 `npm run typecheck`、30 项自动化测试、`npm run build` 以及本地真实 HTTP / 浏览器多视口交互验证。
- 视觉设计变量与组件规范已归档于 [DESIGN.md](DESIGN.md) 与 `.impeccable/design.json`（扩展元数据），首轮审查发现的 6 项界面细节问题（右侧总览单行防折行、左侧奏报面板高度与宋体层级、顶栏分组竖线、移动端全屏面板防透底与会话区自适应、禁用主按钮对比度、乙州地图副标题避让湖泊与治所）均已修复并复核通过。
- 验证边界说明：当前成果属于开发分支实现（尚未合并主干、部署上线或经过人工代码合并验收），且尚未完成跨四周的完整原生多 Agent 实盘长局评测。

## Product Principles

- 从地图中的地区、事件与官员进入操作，保持地理上下文。
- 信息的来源、所属周次和是否已上报应清楚可见。
- 官员可以交涉、建议和执行授权行为，最终资源变更以服务端规则为准。
- 小范围验证缩小模拟规模，仍须验证真实策略游戏的主要操作过程。
- 使用标准、易读的表达，不自造术语。

## Current Design & Implementation Baseline

- 视觉设计系统、设计变量与组件规范见 [DESIGN.md](DESIGN.md) 及 `.impeccable/design.json`（扩展元数据）。
- 交互状态机、周结算规则、OAR 接收回执与 18 条验收场景见 [地图交互与官员通信方案](docs/design/restart-ui-interactions.md)。
- 架构与开发命令见 [CLAUDE.md](CLAUDE.md)，第三方地图代码与资源许可说明见 [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md)。
