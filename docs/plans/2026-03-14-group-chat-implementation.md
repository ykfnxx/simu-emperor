# 群聊TAPE CONTEXT实现计划

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**目标：** 修复群聊消息发送bug，并为群聊模式添加Agent选择器到TAPE CONTEXT

**架构：**
- 后端：修复 `GroupChatService.send_to_group_chat()` 实际调用 `MessageService.broadcast()` 发送消息
- 前端：新增 `selectedGroupAgentId` 状态，添加Agent下拉选择器（仅群聊模式显示）

**技术栈：**
- 后端：Python, FastAPI, ApplicationServices
- 前端：TypeScript, React, useState/useEffect

---

## Task 1: 后端 - 修复群聊消息发送

**根因：** `GroupChatService.send_to_group_chat()` 只增加message_count，没有实际发送消息给agents

**Files:**
- Modify: `src/simu_emperor/application/group_chat_service.py`
- Modify: `src/simu_emperor/adapters/web/server.py`
- Test: `tests/unit/test_application/test_group_chat_service.py`

### Step 1: 修改 GroupChatService 添加 MessageService 依赖

编辑 `src/simu_emperor/application/group_chat_service.py`:

```python
"""Group Chat Service - Multi-agent chat management."""

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING
import uuid

from simu_emperor.common import DEFAULT_WEB_SESSION_ID, strip_agent_prefix

if TYPE_CHECKING:
    from simu_emperor.session.manager import SessionManager
    from simu_emperor.session.group_chat import GroupChat
    from simu_emperor.application.message_service import MessageService


logger = logging.getLogger(__name__)


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class GroupChatService:
    """Group chat business service.

    Responsibilities:
    - Group chat creation/management
    - Agent addition/removal from groups
    - Group chat message handling (broadcasts to all agents)
    """

    def __init__(
        self,
        session_manager: "SessionManager",
        memory_dir: Path,
        message_service: "MessageService | None" = None,  # 新增
    ) -> None:
        """Initialize GroupChatService.

        Args:
            session_manager: Session lifecycle manager
            memory_dir: Memory storage directory
            message_service: Message service for broadcasting (optional, for circular dep)
        """
        self.session_manager = session_manager
        self.memory_dir = memory_dir
        self._group_chats: dict[str, "GroupChat"] = {}
        self._message_service: "MessageService | None" = message_service

    def set_message_service(self, message_service: "MessageService") -> None:
        """Set message service (called after initialization to avoid circular dependency)."""
        self._message_service = message_service
```

### Step 2: 修改 send_to_group_chat 实际发送消息

在 `GroupChatService.send_to_group_chat()` 方法中添加实际发送逻辑：

```python
    async def send_to_group_chat(
        self,
        group_id: str,
        message: str,
    ) -> list[str]:
        """Send message to all agents in a group chat.

        Args:
            group_id: Group chat ID
            message: Message to send

        Returns:
            List of agent IDs that received the message

        Raises:
            ValueError: If group chat not found
        """
        group = self._group_chats.get(group_id)
        if not group:
            raise ValueError(f"Group chat not found: {group_id}")

        # Increment message count
        group.message_count += 1
        await self._save_group_chats()

        # 实际发送消息给所有agents
        if self._message_service and group.agent_ids:
            await self._message_service.broadcast(
                message=message,
                session_id=group.session_id,
                agent_ids=group.agent_ids,
                source="player:web:group",
            )
            logger.info(f"Broadcast group message to {len(group.agent_ids)} agents: {group.agent_ids}")

        return group.agent_ids
```

### Step 3: 更新 ApplicationServices 注入 MessageService

编辑 `src/simu_emperor/application/services.py`:

找到 GroupChatService 初始化部分，修改为：

```python
        # GroupChatService 暂时不传 message_service（避免循环依赖）
        self.group_chat_service = GroupChatService(
            session_manager=self.session_manager,
            memory_dir=memory_dir,
        )
        # 设置 message_service 引用
        self.group_chat_service.set_message_service(self.message_service)
```

### Step 4: 更新单元测试

编辑 `tests/unit/test_application/test_group_chat_service.py`:

添加测试用例验证消息广播：

```python
import pytest
from unittest.mock import AsyncMock, Mock

from simu_emperor.application.group_chat_service import GroupChatService


@pytest.fixture
def mock_message_service():
    """Mock message service."""
    service = Mock()
    service.broadcast = AsyncMock()
    return service


@pytest.mark.asyncio
async def test_send_to_group_chat_broadcasts_to_agents(group_chat_service, mock_message_service):
    """Test send_to_group_chat calls broadcast."""
    # Set message service
    group_chat_service.set_message_service(mock_message_service)

    # Create a test group
    group = await group_chat_service.create_group_chat(
        name="Test Group",
        agent_ids=["agent_a", "agent_b"],
        session_id="session:test",
    )

    # Send message
    sent_agents = await group_chat_service.send_to_group_chat(
        group_id=group.group_id,
        message="Hello group",
    )

    # Verify broadcast was called
    mock_message_service.broadcast.assert_called_once_with(
        message="Hello group",
        session_id="session:test",
        agent_ids=["agent_a", "agent_b"],
        source="player:web:group",
    )
    assert sent_agents == ["agent_a", "agent_b"]
    assert group.message_count == 1
```

### Step 5: 运行测试验证

```bash
uv run pytest tests/unit/test_application/test_group_chat_service.py -v
```

预期：全部通过

### Step 6: 提交

```bash
git add src/simu_emperor/application/group_chat_service.py src/simu_emperor/application/services.py tests/unit/test_application/test_group_chat_service.py
git commit -m "fix(backend): broadcast group chat messages to all agents"
```

---

## Task 2: 前端 - 选择群聊后刷新chatTape

**根因：** `handleSelectGroup` 没有调用 `refreshChatTape`

**Files:**
- Modify: `web/src/App.tsx`

### Step 1: 找到 handleSelectGroup 函数

位置：`web/src/App.tsx` 约第979-987行

### Step 2: 添加 refreshChatTape 调用

修改 `handleSelectGroup` 函数：

```typescript
  const handleSelectGroup = (group: GroupChat) => {
    setCurrentGroupId(group.group_id);
    setCurrentSessionId(group.session_id);
    // 使用群聊的第一个agent作为当前agent
    const firstAgent = group.agent_ids[0];
    if (firstAgent) {
      setCurrentAgentId(firstAgent);
      // 新增：刷新chatTape
      void refreshChatTape(firstAgent, group.session_id);
    }
  };
```

### Step 3: 修改 handleSendToGroup 使用正确的agent刷新

位置：`web/src/App.tsx` 约第989-1010行

```typescript
  const handleSendToGroup = async () => {
    if (!currentGroupId || !inputText.trim()) return;
    const content = inputText.trim();
    setSending(true);
    setError(null);

    try {
      const result = await client.current.sendGroupMessage(currentGroupId, content);
      setInputText('');
      // 刷新chatTape显示 - 使用所有agents刷新以确保显示所有响应
      const group = groupChats.find(g => g.group_id === currentGroupId);
      if (group) {
        setTimeout(() => {
          // 刷新群聊中所有agents的tape
          for (const agentId of group.agent_ids) {
            void refreshChatTape(agentId, currentSessionId);
          }
        }, 1000);
      }
    } catch (err) {
      const message = err instanceof Error ? err.message : '发送群消息失败';
      setError(message);
    } finally {
      setSending(false);
    }
  };
```

### Step 4: 手动测试

1. 启动前端：`cd web && npm run dev`
2. 启动后端：`uv run simu-emperor`
3. 创建群聊
4. 选择群聊，验证chatTape显示历史消息
5. 发送群消息，验证agents响应并显示

### Step 5: 提交

```bash
git add web/src/App.tsx
git commit -m "fix(frontend): refresh chatTape when selecting group and sending group messages"
```

---

## Task 3: 前端 - 添加 selectedGroupAgentId 状态

**Files:**
- Modify: `web/src/App.tsx`

### Step 1: 添加新状态定义

在状态定义区域（约第558行附近）添加：

```typescript
  // 群聊相关状态
  const [groupChats, setGroupChats] = useState<GroupChat[]>([]);
  const [showCreateGroupDialog, setShowCreateGroupDialog] = useState(false);
  const [newGroupName, setNewGroupName] = useState('');
  const [selectedGroupAgents, setSelectedGroupAgents] = useState<Set<string>>(new Set());
  const [currentGroupId, setCurrentGroupId] = useState<string | null>(null);
  // 新增：群聊模式下TAPE CONTEXT选中的agent
  const [selectedGroupAgentId, setSelectedGroupAgentId] = useState<string | null>(null);
```

### Step 2: 添加派生逻辑

在 `currentAgentName` 定义之后添加：

```typescript
  const currentAgentName = useMemo(
    () => agentSessions.find((group) => group.agent_id === currentAgentId)?.agent_name || currentAgentId,
    [agentSessions, currentAgentId]
  );

  // 新增：TAPE CONTEXT使用的agent ID（群聊模式用selectedGroupAgentId，否则用currentAgentId）
  const viewAgentId = selectedGroupAgentId ?? currentAgentId;
```

### Step 3: 提交

```bash
git add web/src/App.tsx
git commit -m "feat(frontend): add selectedGroupAgentId state for group tape context"
```

---

## Task 4: 前端 - 添加Agent下拉选择器UI

**Files:**
- Modify: `web/src/App.tsx`

### Step 1: 修改 handleSelectGroup 初始化 selectedGroupAgentId

```typescript
  const handleSelectGroup = (group: GroupChat) => {
    setCurrentGroupId(group.group_id);
    setCurrentSessionId(group.session_id);
    // 使用群聊的第一个agent作为当前agent
    const firstAgent = group.agent_ids[0];
    if (firstAgent) {
      setCurrentAgentId(firstAgent);
      // 新增：设置TAPE CONTEXT的选中agent
      setSelectedGroupAgentId(firstAgent);
      void refreshChatTape(firstAgent, group.session_id);
    }
  };
```

### Step 2: 添加退出群聊时重置逻辑

修改 `handleSelectSession` 函数：

```typescript
  const handleSelectSession = async (agentId: string, sessionId: string) => {
    // ... 现有代码 ...

    // 新增：退出群聊模式，重置selectedGroupAgentId
    setSelectedGroupAgentId(null);

    // ... 现有代码 ...
  };
```

### Step 3: 添加Agent选择器组件

找到 TAPE CONTEXT 的会话信息区域（约第1703-1709行），修改为：

```typescript
            {/* 固定会话信息 */}
            <div className="mb-3 rounded-lg border border-slate-200 bg-slate-50 px-3 py-2 text-sm">
              {/* 群聊模式：显示Agent选择器 */}
              {currentGroupId ? (
                <div className="flex items-center gap-2">
                  <Users className="h-4 w-4 text-purple-500" />
                  <select
                    value={selectedGroupAgentId || currentAgentId}
                    onChange={(e) => {
                      const newAgentId = e.target.value;
                      setSelectedGroupAgentId(newAgentId);
                      void refreshViewTape(newAgentId, selectedViewSessionId || currentSessionId);
                    }}
                    className="flex-1 rounded border border-slate-200 bg-white px-2 py-1 text-sm outline-none focus:border-purple-300"
                  >
                    {(() => {
                      const group = groupChats.find(g => g.group_id === currentGroupId);
                      if (!group) return null;
                      return group.agent_ids.map(agentId => {
                        const agentName = agentSessions.find(g => g.agent_id === agentId)?.agent_name || agentId;
                        return (
                          <option key={agentId} value={agentId}>{agentName}</option>
                        );
                      });
                    })()}
                  </select>
                </div>
              ) : (
                // 非群聊模式：显示固定agent
                <div className="flex items-center gap-2">
                  <CalendarClock className="h-4 w-4 text-slate-500" />
                  <span className="truncate">{viewAgentId}</span>
                </div>
              )}
              <div className="flex items-center gap-2 text-xs text-slate-500">
                <span>·</span>
                <span className="truncate">{viewTape.session_id ? viewTape.session_id.slice(-20) : currentSessionId.slice(-20)}</span>
              </div>
            </div>
```

### Step 4: 提交

```bash
git add web/src/App.tsx
git commit -m "feat(frontend): add agent selector dropdown for group chat tape context"
```

---

## Task 5: 前端 - 调整tape加载逻辑使用 viewAgentId

**Files:**
- Modify: `web/src/App.tsx`

### Step 1: 修改 loadSubSessions 使用 viewAgentId

找到 `loadSubSessions` 调用位置（约第1716行），修改为：

```typescript
              <button
                type="button"
                onClick={() => {
                  if (!showSubSessions && viewAgentId && currentSessionId) {
                    loadSubSessions(currentSessionId, viewAgentId);
                  }
                  setShowSubSessions((prev) => !prev);
                }}
                className="flex w-full items-center justify-between px-3 py-2 text-sm hover:bg-slate-50"
              >
```

### Step 2: 修改 handleSwitchSession 使用 viewAgentId

```typescript
  const handleSwitchSession = async (sessionId: string) => {
    setSelectedViewSessionId(sessionId);
    await refreshViewTape(viewAgentId, sessionId);
  };
```

### Step 3: 修改子session刷新逻辑

确保所有 `refreshViewTape` 调用都使用正确的逻辑：

```typescript
  // 辅助函数：刷新TAPE CONTEXT的tape（使用selectedViewSessionId）
  const refreshViewTape = useCallback(async (agentId: string, sessionId: string) => {
    // 对于群聊模式，agentId可能是群聊中的某个agent
    // 对于非群聊模式，agentId是currentAgentId
    return refreshTape(agentId, sessionId, 'view');
  }, [refreshTape]);
```

### Step 4: 提交

```bash
git add web/src/App.tsx
git commit -m "refactor(frontend): use viewAgentId for tape context operations"
```

---

## Task 6: 端到端测试

### Step 1: 启动服务

```bash
# 终端1：后端
uv run simu-emperor

# 终端2：前端
cd web && npm run dev
```

### Step 2: 测试群聊消息发送

1. 创建包含多个agents的群聊
2. 向群聊发送消息
3. 验证所有agents都收到消息（检查chatTape）

### Step 3: 测试Agent选择器

1. 选择群聊
2. 验证TAPE CONTEXT显示Agent下拉选择器
3. 切换Agent
4. 验证tape事件列表更新为选中agent的事件

### Step 4: 测试Session切换

1. 在群聊模式下选择某个agent
2. 切换到子session
3. 验证显示的是选中agent的子session

### Step 5: 测试退出群聊

1. 从群聊切换到单agent session
2. 验证Agent选择器消失
3. 验证tape正常显示

### Step 6: 提交文档

```bash
git add docs/plans/2026-03-14-group-chat-tape-context-design.md docs/plans/2026-03-14-group-chat-implementation.md
git commit -m "docs: add group chat tape context design and implementation plan"
```

---

## 验收标准

- [ ] 群聊消息发送后，所有参与agents都能收到并响应
- [ ] 选择群聊后，chatTape正确显示历史消息
- [ ] 群聊模式下，TAPE CONTEXT显示Agent下拉选择器
- [ ] 切换Agent后，TAPE CONTEXT显示正确agent的tape
- [ ] 切换Session后，子session列表基于选中agent显示
- [ ] 退出群聊后，Agent选择器消失，恢复默认行为
