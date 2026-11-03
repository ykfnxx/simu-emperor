# 人物与任职的原生会话

`openOrResumeCharacterSession` 提供人物调用器的会话生命周期。它接收宿主已绑定的游戏、人物、任职、职务和省份身份；不从模型输出选择身份，也不负责判断任职当前是否有效。实际读写权限仍由游戏服务检查。

此模块是新人物调用器的第一步，尚未替换旧 `run-one-officer` CLI 的三官流程，也不提交上奏、请求、回复或回执。后续调用器使用固定的共享玩法契约接入。

## 所属关系

会话状态按以下层次持久化：

```text
<dataDir>/games/<game_id>/characters/<character_id>/appointments/<appointment_id>/
  workspace/
  session-state.json
  sessions/<previous_native_session_id>.json
```

目录段对不适合路径的 ID 字符编码，状态内保留原始 ID。每段任职独享工作区；消息会话 ID 不进入路径，同一人物任职期间的私聊、群聊和上奏共享原生会话。新局、继任者和同一人物重新任职均使用新的所属路径。

## 创建、恢复与配置变更

宿主传入 `identity`、`dataDir`、`runtimeId`、可选 `model` 和 `effort`，调用 `openOrResumeCharacterSession(options, registry?)`：

- 没有已保存状态时创建新原生 session，并保存 session ID 和绝对 cwd。
- 再次调用时恢复同一 session ID 与 cwd，不创建替代会话掩盖恢复错误。
- 保存的身份或 cwd 不匹配、状态损坏、运行时不可用、原生恢复失败，均明确报错，保留原状态。
- 改变 runtime、model 或 effort 需要宿主明确传入 `startNewSession: true`。新原生会话成功创建后，原状态保存在 `sessions/`，当前指向新会话；人物身份与任职工作区不变。不在不同 runtime 间迁移原生历史。
- Codex 延续现有调用器的只读沙箱设置。该目录划分不等于操作系统隔离。

同一人物仍由宿主串行调度；本模块不增加跨进程锁或自动重试。任免之后调用器必须采用新的任职上下文，不能在生成结束后将旧调用重标为当前现任。

测试使用 OAR 的 scripted runtime，无需真实模型或登录：

```sh
npm test -- tests/character-session.test.ts
```
