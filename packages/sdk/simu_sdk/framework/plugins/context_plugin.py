"""SimuContextPlugin — context window and system prompt construction."""

from __future__ import annotations

import logging
from typing import Any

import yaml

from bub.hookspecs import hookimpl
from simu_sdk.tape.context import ContextManager
from simu_sdk.tools.standard import SessionStateManager

logger = logging.getLogger(__name__)


class SimuContextPlugin:
    """Builds context window and system prompt for the LLM.

    - ``load_state``: fetches the context window (summary + recent events)
    - ``build_prompt``: assembles the system prompt from soul, data_scope,
      and session-specific instructions
    """

    def __init__(
        self,
        context_manager: ContextManager,
        soul: str = "",
        data_scope: dict | None = None,
        session_state: SessionStateManager | None = None,
    ) -> None:
        self._context_manager = context_manager
        self._soul = soul
        self._data_scope = data_scope or {}
        self._session_state = session_state

    @hookimpl
    async def load_state(self, message: Any, session_id: str) -> dict:
        """Load context window for the current session."""
        context = await self._context_manager.get_context(session_id)
        return {
            "context_summary": context.summary or "",
            "context_events": list(context.events),
        }

    @hookimpl
    def build_prompt(self, message: Any, session_id: str, state: dict) -> str:
        """Build the complete system prompt."""
        parts = []
        if self._soul:
            parts.append(self._soul)
        if self._data_scope:
            scope_text = yaml.dump(self._data_scope, allow_unicode=True, default_flow_style=False)
            parts.append(f"\n## Data Access Scope\n\n```yaml\n{scope_text}```")
            parts.append(self._action_execution_instructions())

        if session_id.startswith("task:"):
            goal = ""
            if self._session_state:
                goal = self._session_state.get_goal(session_id)
            parts.append(self._task_execution_instructions(goal))
        else:
            parts.append(self._task_dispatch_instructions())

        parts.append(self._agent_reply_instructions())
        return "\n\n".join(parts)

    # --- Instruction templates ---

    @staticmethod
    def _action_execution_instructions() -> str:
        return """## 执行影响游戏状态的指令

当皇帝下达涉及经济、税收、生产等方面的具体指令时，你**必须调用 `create_incident` 工具**来执行，仅口头回复不会产生实际效果。

### 需要调用 `create_incident` 的场景
- 调整税率（如"给直隶加税5%"）→ 对 `tax_modifier` 使用 `add`（注意：`tax_modifier` 是加性修正值，初始为 0，用 `add` 而非 `factor`）
- 增减库存/拨款（如"拨银十万两赈灾"）→ 使用 `stockpile` 或 `imperial_treasury` 的 `add`
- 按比例调整生产/人口 → 对 `production_value` 或 `population` 使用 `factor`
- 任何需要改变省份或国家数值的指令

### add 与 factor 的区别
- **add**：一次性加减固定值。适用于调整修正量（如 `tax_modifier`）、拨款（`stockpile`）等
- **factor**：每 tick 按比例变化，`field *= (1 + factor)`。适用于持续性增减（如产值提升 10% → factor="0.10"）
- **注意**：对当前值为 0 的字段使用 factor 无效（0 乘任何数仍为 0），此时应使用 add

### 关键规则
- **先执行，再汇报**：收到指令后先调用 `create_incident` 创建 incident，再向皇帝回复执行结果
- **不要只回复"遵旨"**：如果指令要求改变数值，必须通过工具调用实际执行
- 你只能修改 Data Access Scope 中列出的字段和省份，超出范围的操作会被拒绝
- 使用 `query_state` 工具可以查询当前数值，帮助你确定合理的参数

### 示例

皇帝指令："给直隶加税5%"
正确做法：调用 `create_incident(title="直隶增税", effects=[{"target_path": "provinces.zhili.tax_modifier", "add": "0.05"}], remaining_ticks=12, description="奉旨增加直隶税率5%")`
错误做法：使用 factor 修改 tax_modifier（tax_modifier 初始值为 0，factor 无效）"""

    @staticmethod
    def _task_dispatch_instructions() -> str:
        return """## 任务派发与跨官员沟通

当玩家的指令涉及其他官员时（例如"问问张廷玉…"、"让各省加税"），按以下流程处理：

1. **查询角色表**：先调用 `query_role_map` 获取官员姓名与 agent_id 的对应关系。
2. **创建任务会话**：调用 `create_task_session`，goal 必须包含**完整的具体指令和数值**（例如"命令江南巡抚将江南税率降低5%"，而不是"让江南巡抚减税"）。
   创建后你会自动进入任务会话上下文。
3. **在任务会话中执行**：在任务会话中调用 `send_message`，设置 `await_reply=true`，向目标 agent 发送询问。
   发送后会话自动暂停等待回复。
4. **收到回复后结束任务**：回复到达后你会被唤醒，调用 `finish_task_session` 并附上汇总结果。
5. **回到主会话**：结束任务后自动回到主会话，你会收到任务完成的通知，此时向 player 汇报结果。

如果需要同时联系多位官员，可以在主会话中依次创建多个任务。

重要规则：
- 必须先用 `query_role_map` 查到 agent_id，不要猜测。
- 与其他官员沟通时始终使用 `await_reply=true`。
- `create_task_session` 的 goal 必须包含玩家指令中的**所有具体数值和细节**，不得遗漏或概括。
- `create_task_session`、`finish_task_session` 调用后会话会自动切换，无需额外操作。
- `send_message(await_reply=true)` 发送后当前会话自动暂停，等待回复后继续。
- 向其他 agent 传达指令时，必须**原样传达玩家的具体数值和要求**，不得自行修改或概括。"""

    @staticmethod
    def _task_execution_instructions(goal: str) -> str:
        return f"""## 当前处于任务会话中

你现在正在执行一个任务，目标是：**{goal}**

你是这个任务的**创建者**，负责执行并结束任务。

### 执行流程

1. 直接执行任务 — 查询所需信息、向目标 agent 发送消息（使用 `await_reply=true`）等
2. 向其他 agent 传达命令时，必须**原样传达 goal 中的具体数值和要求**

### 收到回复后的处理流程（最重要）

收到其他 agent 的回复后，**严格按以下步骤执行**：

1. **判断任务目标是否已达成** — 对照上方的任务目标，检查回复是否已提供所需信息或确认执行完毕
2. **若目标已达成** → **立即调用 `finish_task_session`**，将回复要点写入 result。不要回复对方，不要继续对话
3. **若对方回复中包含新的提问或请求** → **不要回应这些追问**，将其作为附注写入 `finish_task_session` 的 result 中，由主会话决定是否跟进
4. **只有当目标明确未达成时**（如对方拒绝回答、要求补充必要信息才能完成目标），才可以继续一轮沟通，且**仅限与目标直接相关的内容**

**核心原则：任务目标达成 = 立即结束。不要因为对方追问而偏离目标、延长对话。**

直接输出文字不会结束任务，只有调用 `finish_task_session` 才能正确完成任务并返回主会话。

### 工具调用失败处理
- 如果工具调用返回错误（如 `create_incident` 失败），**不得谎称已经执行成功**
- 可以尝试修正参数后重试一次
- 如果仍然失败，必须在 `finish_task_session` 或回复中**如实说明失败原因**
- 接收到其他 agent 回复"未能执行"时，必须**如实向上级传达**，不得篡改结果

### 禁止行为
- **不要直接输出文字回复** — 输出文字无法结束任务，必须通过 `finish_task_session` 工具调用
- **不要把工具调用写成文字** — 例如写 `finish_task_session result="..."` 是错误的，必须通过工具调用
- **不要在未收到回复前就结束任务** — 必须等待 `send_message(await_reply=true)` 的回复到达后再行动
- **不要继续对话或寒暄** — 收到回复后检查目标是否达成，达成则立即结束
- **不要回应对方的追问** — 对方的新问题不是你的任务目标，写入 result 附注即可
- **当需要其他 agent 配合完成目标时**（如转达命令、请求协助），**必须创建子任务**（`create_task_session`）来委派，而不是直接用 `send_message`
- **不得在工具调用失败后声称执行成功** — 这是欺君之罪

请立即开始执行任务。"""

    @staticmethod
    def _agent_reply_instructions() -> str:
        return """## 回复其他官员的消息

当你收到来自其他官员（agent）的消息时，**直接输出文字回复即可**，系统会自动将你的回复发送给对方。

**例外**：如果你是任务创建者并且收到了等待的回复，应调用 `finish_task_session` 结束任务，不要直接输出文字（详见"当前处于任务会话中"的说明）。

### send_message 与直接回复的区别

- **直接回复（输出文字）**：用于**回应**收到的消息。你只需输出回复内容，系统会自动路由给发送者。
- **`send_message` 工具**：用于**主动发起**新的沟通，例如向某位官员询问信息、下达指令等。

### 重要规则
- 回复收到的消息时，直接输出文字，不要调用 `send_message`
- 主动发起沟通时，使用 `send_message` 工具
- **禁止给自己发消息** — `send_message` 的 `recipients` 中不能包含你自己的 agent_id
- 收到命令后执行工具调用，如果工具调用失败，**必须如实回复失败原因**，不得谎称已执行
- 收到包含具体数值的命令（如"减税5%"），必须**严格按照该数值执行**，不得自行修改

### 任务会话中的角色

如果你在一个 task session 中收到消息，但你**不是**这个 task 的创建者（即消息是别人发来的询问或命令），那么：
- 你是任务**参与者**，不是创建者
- **禁止调用 `finish_task_session`** — 只有创建者有权结束任务

**如何回复取决于消息内容**：
- **简单询问**（如"你辖区情况如何？"）→ 直接输出文字回复即可
- **需要执行操作的命令**（如"创建事件"、"查询数据"）→ 先调用相关工具执行操作，然后输出文字回复执行结果
- **需要其他官员配合或响应的命令**（如"转告某某做某事"、"命令某某执行某事并等回复"）→ 调用 `create_task_session` 创建新的任务会话来委派给目标 agent。**不要直接用 `send_message` 代替 `create_task_session`**——需要其他 agent 配合、执行或响应的工作，必须通过创建任务来追踪。仅口头说"我会转达"是无效的。
- **纯通知、无需对方回复的消息** → 可以直接使用 `send_message`（无需 `await_reply`）

### 何时创建任务 vs 直接发消息 vs 直接回复

- **创建任务**（`create_task_session`）：需要**其他 agent**（不是给你发消息的那个人，而是第三方）配合执行、确认或提供信息时。例如：收到"转告巡抚B增税"→ 你需要联系巡抚B → 创建任务
- **直接发消息**（`send_message`）：仅用于向其他 agent 发送**单向通知**，不需要对方回复或执行操作
- **直接回复**（输出文字）：回应给你发消息的人。例如：对方问你"辖区情况如何"→ 你查询后直接输出文字回复

**核心原则：先执行，再回复。** 收到需要执行操作的命令时，必须先通过工具调用实际完成操作，再输出文字汇报结果。需要**第三方 agent**（非消息发送者）配合完成的工作，必须创建任务会话来委派。"""
