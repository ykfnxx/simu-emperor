# Simu-Emperor

浏览器端帝王策略游戏（全栈 TypeScript 重写版）。玩家扮演君主，通过地图、官员奏报、朝堂交涉与提案批复治理国家；外部官员由本地 OAR Agent 扮演，游戏服务端不托管模型密钥。

## 当前进度

- **产品定义**：见 [PRODUCT.md](PRODUCT.md)
- **交互与规则设计（v2.1）**：见 [docs/design/restart-ui-interactions.md](docs/design/restart-ui-interactions.md)
- **已实现（第一增量）**：
  - Node 24+ / TypeScript / Hono / SQLite 权威游戏服务端
  - 3 州（`甲州`、`乙州`、`丙州`）、3 官员（含甲州兼领度支）、4 周剧本确定性周模拟引擎
  - `OPEN -> LOCKED -> ARCHIVED` 周次状态机、三项权威快照冻结与单事务批复结算
  - 奏报与真值严格隔离（未知不以零代替）、双重调试真值鉴权（`ENABLE_DEBUG_TRUTH=1` + `MONARCH_DEBUG_TOKEN`）
  - 会话权限隔离、点名唤醒、只读收件箱与基于 `accepted` 证据的 `seen_seq` 推进协议
  - 供后续前端地图界面与外部 OAR 调用器直接消费的类型化契约（[`src/contracts/index.ts`](src/contracts/index.ts)）
- **待后续增量实现**：
  - React / Vite 地图主界面与右抽屉三页签交互
  - 原生 OAR（`@botiverse/oar`）外部官员调用进程

## 环境要求

- Node.js `>= 24.0.0`（使用内置 `node:sqlite` 与 `process.loadEnvFile`）
  - 若 macOS 使用 Homebrew keg-only `node@24`，可先执行 `export PATH="/opt/homebrew/opt/node@24/bin:$PATH"`。

## 快速开始

```bash
# 1. 安装依赖
npm install

# 2. 初始化本地运行环境变量（服务端启动强制校验角色 Bearer Token，无硬编码回退）
cp .env.example .env

# 3. 类型检查
npm run typecheck

# 4. 运行测试
npm test

# 5. 启动开发服务器（默认读取 .env，监听 8787 端口）
npm run dev
```

## 目录结构

```text
simu-emperor/
├── PRODUCT.md                         # 产品目标与边界定义
├── CLAUDE.md                          # 架构与开发规范
├── docs/design/
│   ├── restart-ui-interactions.md     # v2.1 地图交互与官员通信设计方案
│   └── assets/ui-layout-v1.png        # 界面布局基线示意图
├── src/
│   ├── contracts/index.ts             # 前后端及 OAR 共享类型契约与常量
│   ├── db/schema.ts                   # SQLite 表结构初始化
│   ├── engine/
│   │   ├── trial-script.ts            # 3 州 3 官员 4 周确定性剧本数据
│   │   └── game-store.ts              # 周状态机、快照冻结、单事务结算与会话存储
│   ├── app.ts                         # Hono HTTP 路由与权限校验
│   └── server.ts                      # Node HTTP 服务入口
└── tests/
    ├── engine.test.ts                 # 账目核算、快照冻结、原子结算回滚测试
    └── api.test.ts                    # HTTP 契约、权限隔离、会话与回执协议测试
```

## 许可证

[MIT License](LICENSE)
