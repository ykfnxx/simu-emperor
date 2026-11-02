# Simu-Emperor

浏览器端帝王策略游戏（全栈 TypeScript 版）。玩家扮演君主，通过地图、官员奏报、朝堂交涉与提案批复治理国家；外部官员由本地 OAR（`@botiverse/oar@0.84.0`）原生 Agent 扮演，游戏服务端不托管模型密钥。

## 核心文档

- **产品定义**：见 [PRODUCT.md](PRODUCT.md)
- **交互与规则设计（v2.1）**：见 [docs/design/restart-ui-interactions.md](docs/design/restart-ui-interactions.md)
- **架构与开发规范**：见 [CLAUDE.md](CLAUDE.md)

## 环境要求

- Node.js `>= 24.0.0`（使用内置 `node:sqlite`、`node:util.parseEnv` 与 `process.loadEnvFile`）
  - 若 macOS 使用 Homebrew keg-only `node@24`，请先执行：`export PATH="/opt/homebrew/opt/node@24/bin:$PATH"`

## 快速开始（服务端 + 外部官员调用器）

```bash
# 1. 安装依赖
npm install

# 2. 配置游戏服务端角色凭据（服务端启动强制校验角色 Bearer Token）
cp .env.example .env

# 3. 类型检查与测试
npm run typecheck
npm test

# 4. 构建前端静态资源（dist/web）并由后端同源托管启动（默认监听 http://127.0.0.1:8787）
npm run build
npm start

# 或在开发模式下分别启动后端与 Vite 前端开发服务
npm run dev
npm run dev:web
```

### 运行外部官员客户端（`run-one-officer`）

每个官员客户端仅需该官员自身的身份与 Bearer Token、游戏服务地址及显式指定的 OAR 原生运行时（无需君主或其他官员凭据）：

```bash
# 1. 复制单官员调用器环境配置示例
cp .env.officer.example .env.officer

# 2. 单次执行模式（用于独立验证或单步触发：自动处理新 OPEN 周奏报/提案或当前待处理点名唤醒）
npm run run-one-officer -- --env-file .env.officer --once

# 或直接通过命令行参数指定官员、Token、服务地址与显式 OAR 运行时：
npm run run-one-officer -- \
  --officer officer_a \
  --token officer-a-token \
  --origin http://127.0.0.1:8787 \
  --runtime codex \
  --once

# 3. 串行监听循环模式（正常游玩时持续轮询并串行合并批次处理该官员会话）
npm run run-one-officer -- --env-file .env.officer --watch
```

### 外部官员会话与运行时说明

- **显式原生运行时配置**：必须通过 `OAR_RUNTIME` 或 `--runtime` 显式指定（如 `codex`），无隐式模型或运行时自动回退。Codex 运行时默认强制启用只读沙箱（`OAR_CODEX_SANDBOX=read-only`）并要求模型仅输出结构化 JSON 游戏动作。
- **单官员独立持久化会话**：每个官员在忽略目录 `data/runtime/officers/<officer_id>/` 下拥有独立工作目录 `workspace/` 与会话状态文件 `session-state.json`。进程重启时显式恢复原 `session_id`；若底层会话丢失或损坏则显式报错停止，绝不静默替换为新会话。

## 目录结构

```text
simu-emperor/
├── PRODUCT.md                         # 产品目标与边界定义
├── CLAUDE.md                          # 架构与开发规范
├── .env.example                       # 服务端环境变量模板
├── .env.officer.example               # 单官员外部调用器环境变量模板
├── docs/design/
│   ├── restart-ui-interactions.md     # v2.1 地图交互与官员通信设计方案
│   └── assets/ui-layout-v1.png        # 界面布局基线示意图
├── src/
│   ├── contracts/index.ts             # 服务端、前端与 OAR 官员调用器共享类型契约
│   ├── db/schema.ts                   # SQLite 表结构初始化
│   ├── engine/
│   │   ├── trial-script.ts            # 3 州 3 官员 4 周确定性剧本数据
│   │   └── game-store.ts              # 周状态机、快照冻结、单事务结算与会话存储
│   ├── officers/
│   │   ├── cli.ts                     # run-one-officer CLI 入口（once / watch 模式）
│   │   ├── config.ts                  # 单官员凭据与显式运行时配置解析
│   │   ├── game-client.ts             # 官员 Bearer Token 作用域 HTTP 客户端
│   │   ├── model-contract.ts          # 官员提示词构造与严格 JSON 动作校验
│   │   ├── runner.ts                  # OAR 会话恢复、accepted 回执边界与串行批次执行
│   │   └── state-store.ts             # data/runtime/officers/<officer_id> 持久化状态
│   ├── app.ts                         # Hono HTTP 路由、权限校验与前端静态资源托管
│   └── server.ts                      # Node HTTP 服务入口
├── web/                               # React/Vite 地图主界面、单侧抽屉、草稿与会话 UI
└── tests/
    ├── engine.test.ts                 # 账目核算、快照冻结、原子结算回滚测试
    ├── api.test.ts                    # HTTP 契约、权限隔离、会话与回执协议测试
    ├── web-logic.test.ts              # 地图图层、视口防遮挡平移与草稿逻辑测试
    └── officers.test.ts               # OAR 官员调用器回执边界、串行批次、跨周晚到与会话恢复测试
```

## 许可证

[MIT License](LICENSE)
