# Simu-Emperor

浏览器端帝王策略游戏。明代两京十三省中，陕西、河南、湖广参与四回合试玩，其余省份冻结。玩家通过署名奏报了解地方情况，任免人物、私聊或群聊官员，并决定每笔请求的实际拨款。

服务端保存真实账目并结算。人物由本机 OAR 原生 Agent 扮演；模型只能提出请求和回复，不能直接改账或替玩家批款。

## 启动

需要 Node.js 24+。在仓库根目录运行：

```bash
npm ci
cp .env.example .env
# 修改 .env 中三个互不相同的角色凭据。
npm run build
npm start
```

默认地址为 `http://localhost:8787`。Hono 同源提供新玩法 API 和 Next.js 静态导出的 `out/` 页面。页面登录使用 `MONARCH_TOKEN`；`AGENT_HOST_TOKEN` 仅供可信本机调用器使用。

默认数据库为 `data/runtime/ming-gameplay.db`。这是新剧本，旧三州试玩数据库不能直接使用；显式指定旧库会报 `INCOMPATIBLE_DATABASE`。本轮不迁移旧局。

开发时在两个终端分别运行：

```bash
npm run dev
npm run dev:web
```

前端开发地址 `http://localhost:5173`，默认代理至后端 8787。自定义端口时，后端使用 `PORT=18892 npm run dev`，另一个终端使用 `API_PORT=18892 npm run dev:web`。

## 人物 Agent

先安装并登录所选原生 runtime，在人才面板为职务配置 runtime、模型、推理强度与交互模式。调用器使用固定的 `@botiverse/oar@0.84.0`，不自动切换模型或创建替代会话。

```bash
cp .env.character.example .env.character
# 设置与服务端一致的 AGENT_HOST_TOKEN 和 GAME_ORIGIN。
npm run character -- --env-file .env.character --character character_a --once
npm run character -- --env-file .env.character --character character_a --watch
```

为其他在任人物分别启动调用器。人物 ID 保持稳定，每次任职拥有独立 session 和工作区；恢复失败直接报错。更换运行配置需要明确使用 `--new-session`。调用器的凭据留在宿主，不写入模型输入或人物工作区。

JSON 是唯一写入方式。`json+mcp-read` 模式增加只读查询，不增加游戏写入工具。详见 [人物接入文档](docs/agents/character-caller.md)。

## 观测记录

Agent 与游戏引擎分别写入 `logs/agent/`、`logs/game-engine/`，原生交互保存在 `traces/agent/`。使用 `npm run trace:extract -- --invocation CALL_ID --out trace-exports/call` 按调用提取。文件范围、恢复边界和人物回合筛选见[观测记录说明](docs/observability/agent-traces.md)。

## 开发与验证

```bash
npm run typecheck
npm test
npm run build
```

[共享 API 契约](docs/design/gameplay-api.md)规定人物、任职、奏报、计划和聊天字段。[架构说明](CLAUDE.md)记录当前实现边界。地图来源及许可见 [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md)。

固定场景与原生模型基准位于 `src/benchmarks/`。自动执行成功和行为评分分开记录，未人工评分的项保留空值。
