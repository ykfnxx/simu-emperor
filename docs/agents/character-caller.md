# 人物调用器（Ming gameplay 契约）

此调用器使用 `src/contracts/gameplay.ts`，面向新的三省服务。旧 `run-one-officer` CLI 仍面向旧接口，二者不是自动回退关系；后端完成契约切换前，不能把新调用器当成已可连接旧服务的替代品。

## 运行

要求 Node 24+，以及职务运行配置指定的原生 runtime 已安装并完成其认证。

```sh
cp .env.character.example .env.character
# 编辑自己的游戏宿主凭据和角色后：
node --experimental-strip-types src/officers/character-cli.ts --env-file .env.character --once
node --experimental-strip-types src/officers/character-cli.ts --env-file .env.character --watch
```

`CHARACTER_ID` 是人物 ID。runtime、模型与 effort 从该人物当前职务的运行配置读取，不在调用器命令行另选一套。候任或离任人物没有可工作的任职，服务端明确拒绝，不创建临时替补角色。

支持 `json` 和显式选择的 `json+mcp-read` 模式。后者通过标准 MCP SDK 挂载人物专属的只读工具，并由 OAR 传入原生会话；不支持带凭据 HTTP MCP 的 runtime 会明确拒绝，不降级。配置文件只在宿主读取，不放入人物工作区或重新导出到环境；若宿主凭据从进程环境传入，原生会话显式移除该变量，不支持该会话环境选项的 runtime 会报错。

可选参数有 `--character`、`--origin`、`--data-dir`、`--poll-ms`、`--timeout-ms`、`--max-cycles`；`--new-session` 明确为本次启动新建原生会话。不要把宿主凭据放在命令行参数中。

## 行为

调用器先取得人物任职，捕获 game/person/appointment/office/province/turn 六项上下文，再读取本省简报和人物收件箱。原上下文用于该次生成的所有提交，不在模型结束后重定向给新任官员。

- 当前 OPEN 回合尚未上奏时调用模型。上奏允许仅正文和空披露列表，不必请款。
- 私聊或群聊点名形成待回复 wake 时调用模型。未点名公告本身不触发；下次实际调用时作为未读背景带入。
- 同一次生成可提交 report、创建/修改计划、明确撤回计划和回复。省略计划不清空旧承诺。
- 模型只选择披露字段，服务端填入真值；模型不能设置提交身份、审批或回执。
- 每个模型回复目标只对应本批捕获的一条 wake。wake ID、消息原回合与执行回合由宿主分别绑定，旧消息不冒充新回合。
- 未完成 wake 从其附带的原消息恢复，包括已接受和先前拒收的任务；已读位置不代表已回复。恢复仍使用原 wake 和消息源回合。
- 只有匹配的 OAR accepted 才登记接收，正文与正式动作要等生成完成并通过校验。空输出、坏 JSON 和隐式静默均报错。
- 正式操作收到 `STALE_TURN` 或 `WRONG_PHASE` 时记录拒收，仍可提交原任职合法的晚到聊天。`STALE_APPOINTMENT`、`STALE_GAME` 或其他错误终止本轮，不重套现任身份或自动重试。

watch 模式串行处理同一人物，跨回合复用原生 session；职务配置明确变化时新建会话并保留旧记录。每轮完成即打印一行宿主结果，显示实际上奏/计划/回复及正式拒收情况。第四回合结束且无待处理 wake 时退出。SIGINT/SIGTERM 中止生成，停止后不继续发布剩余动作。

数据路径与恢复规则见 [人物任职会话](character-sessions.md)。本步测试使用 OAR scripted runtime 和固定契约的测试 HTTP 服务，不能据此声称完成真实原生模型联测或 benchmark。

## 只读 MCP

`json+mcp-read` 提供四个工具：`read_local_state` 读取本省事实，`read_office_records` 读取职务项目/计划/署名报告/结算，`read_conversation` 读取已参与会话，`read_character_memory` 读取本人的已接受输入及署名报告。工具不接受人物或省份身份参数，执行上下文由宿主在每次生成期间绑定。任职失效后查询由同一游戏服务拒绝，生成结束后工具不再接受查询。写入仍只有最终 JSON。

宿主在 OAR 接受输入后，把本人接收的消息及当时已有的本人署名报告追加到人物目录的 `accepted-memory.jsonl`，保留会话参与者、任职、日期及消息源回合。人物换职可读取自己的旧记录，继任者不继承。它只包含本调用器接收过的内容，不是完整聊天服务器归档，也不导出隐藏推理。`read_conversation` 会将这份记录与当前收件箱合并，不把另一私聊视为当前群聊共同知识。旧调用器未采集的历史保持未知。

MCP 地址与随机连接凭据只在本次原生会话配置中提供，恢复时重新挂载，不写入人物持久会话状态。watch 跨回合重新绑定当前调用上下文；切换模式重新打开同一原生会话以更新工具配置。

原生兼容记录：OAR 0.84.0 的 `serveMcpTools` 不发布 MCP annotations，因此本实现使用固定的 `@modelcontextprotocol/sdk@1.32.2`，四个工具均声明 `readOnlyHint`、`idempotentHint`，并明确无破坏操作及封闭数据范围。MCP SDK 处理协议与连接，不新增游戏服务进程。工具元数据影响原生确认行为，服务端仍逐次检查人物任职与可见范围。参见 [官方 OpenAI MCP 文档](https://learn.chatgpt.com/docs/extend/mcp?surface=cli)。
