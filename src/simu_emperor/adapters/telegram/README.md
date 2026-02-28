# Telegram Bot 适配器

为皇帝模拟器 V2 提供 Telegram Bot 接入，允许玩家通过 Telegram 与 AI Agent 官员交互。

## 目录

- [快速开始](#快速开始)
- [功能特性](#功能特性)
- [架构设计](#架构设计)
- [安装和配置](#安装和配置)
- [使用指南](#使用指南)
- [配置选项](#配置选项)
- [开发和测试](#开发和测试)
- [常见问题](#常见问题)
- [事件流映射](#事件流映射)
- [扩展开发](#扩展开发)
- [相关文档](#相关文档)

---

## 快速开始

### 5 分钟启动

```bash
# 1. 获取 Bot Token（从 @BotFather）
export SIMU_TELEGRAM__BOT_TOKEN="your_bot_token_here"

# 2. 启动 Bot
uv run simu-emperor telegram

# 3. 在 Telegram 中发送 /start
```

### 示例配置文件

参考 `config.example.yaml` 获取完整配置示例。

---

## 功能特性

### 核心功能

- **多用户隔离**：每个 Telegram 用户拥有独立的游戏会话，互不干扰
- **Agent 交互**：
  - `@agent_name 消息` - 与特定官员对话
  - `@all 消息` - 向所有官员广播
  - `/cmd @agent1 @agent2 命令` - 向多个官员下达命令
- **游戏管理**：
  - `/stat` - 查看游戏状态
  - `/agents` - 列出所有活跃官员
  - `/end_turn` - 结束当前回合
- **实时响应**：Agent 响应即时推送到 Telegram
- **可配置命令**：通过配置文件灵活启用/禁用命令

### 技术特点

- **完全异步**：基于 `asyncio` 的事件驱动架构
- **会话管理**：
  - 懒加载会话创建
  - 自动清理过期会话
  - 可配置的最大会话数限制
- **独立数据库**：每个会话使用独立的 SQLite 数据库文件
- **EventBus 集成**：通过 EventBus 与核心模块通信，遵循 V2 架构
- **HTML 消息格式**：稳定的富文本消息支持

---

## 架构设计

### 系统架构图

```
┌─────────────────────────────────────────────────────────────┐
│                   Telegram 用户 (User 1, 2, ...)            │
└────────────────────────┬────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────┐
│                      Telegram Bot API                        │
│                   (python-telegram-bot)                      │
└────────────────────────┬────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────┐
│                   TelegramBotService                         │
│  ┌─────────────────────────────────────────────────────┐   │
│  │  命令处理器 (可配置)                                 │   │
│  │  • /start, /help, /agents, /stat, /end_turn        │   │
│  │  • 自定义命令支持                                    │   │
│  └─────────────────────────────────────────────────────┘   │
│  ┌─────────────────────────────────────────────────────┐   │
│  │  消息路由器                                          │   │
│  │  • @agent, @all, /cmd 解析                          │   │
│  └─────────────────────────────────────────────────────┘   │
└────────────────────────┬────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────┐
│                    SessionManager                            │
│  • 管理多个 GameSession (chat_id 隔离)                       │
│  • 会话清理和超时管理                                        │
│  • 最大会话数限制                                            │
└────────────────────────┬────────────────────────────────────┘
                         │
         ┌───────────────┴───────────────┐
         ▼                               ▼
┌─────────────────────┐         ┌─────────────────────┐
│    GameSession      │         │    GameSession      │
│  (chat_id=123)      │   ...   │  (chat_id=456)      │
├─────────────────────┤         ├─────────────────────┤
│ • player_id         │         │ • player_id         │
│ • EventBus          │         │ • EventBus          │
│ • Repository        │         │ • Repository        │
│ • Calculator        │         │ • Calculator        │
│ • AgentManager      │         │ • AgentManager      │
│ • LLMProvider       │         │ • LLMProvider       │
│ • 独立数据库        │         │ • 独立数据库        │
└─────────────────────┘         └─────────────────────┘
         │                               │
         └───────────────┬───────────────┘
                         ▼
                  ┌──────────────┐
                  │   EventBus   │
                  │   (V2 Core)  │
                  │  事件驱动    │
                  └──────────────┘
```

### 模块说明

| 模块 | 文件 | 职责 |
|------|------|------|
| Bot 服务 | `bot.py` | TelegramBotService - Bot 生命周期、命令注册、消息路由 |
| 会话管理 | `session.py` | SessionManager, GameSession - 会话创建、隔离、清理 |
| 消息路由 | `router.py` | MessageRouter - 解析 @agent, @all, /cmd 格式 |
| 响应收集 | `handlers/response.py` | ResponseCollector - 响应处理（预留扩展） |

---

## 安装和配置

### 1. 获取 Bot Token

1. 在 Telegram 中找到 [@BotFather](https://t.me/botfather)
2. 发送 `/newbot` 创建新机器人
3. 按提示设置机器人名称
4. 保存获得的 Bot Token（格式：`123456789:ABCdefGHIjklMNOpqrsTUVwxyz`）

### 2. 配置方式

#### 方式 A：环境变量（推荐）

```bash
# 基础配置
export SIMU_TELEGRAM__BOT_TOKEN="your_bot_token_here"

# 可选配置
export SIMU_TELEGRAM__SESSION_TIMEOUT_HOURS=24
export SIMU_TELEGRAM__MAX_SESSIONS=100
export SIMU_TELEGRAM__ENABLED_COMMANDS='["start","help","agents","stat","end_turn"]'
```

#### 方式 B：配置文件

复制示例配置文件并修改：

```bash
cp config.example.yaml config.yaml
# 编辑 config.yaml
```

`config.yaml` 示例：

```yaml
telegram:
  bot_token: "your_bot_token_here"
  mode: "polling"
  session_timeout_hours: 24
  response_timeout_seconds: 30
  max_sessions: 100
  enabled_commands:
    - start
    - help
    - agents
    - stat
    - end_turn
```

### 3. 启动 Bot

```bash
# 安装依赖（首次运行）
uv sync

# 启动 Telegram Bot
uv run simu-emperor telegram
```

### 4. 验证启动

启动成功后，您会看到：

```
=== 皇帝模拟器 V2 - Telegram Bot 启动 ===
LLM provider initialized: mock
SessionManager initialized
TelegramBotService initialized (commands: {'start', 'help', 'agents', 'stat', 'end_turn'})
Registered 5 commands: ['start', 'help', 'agents', 'stat', 'end_turn']
=== Telegram Bot is running... ===
Max sessions: 100
Session timeout: 24h
Send /start to your bot to begin
```

### 5. 在 Telegram 中测试

1. 找到您创建的机器人（搜索 @your_bot_username）
2. 发送 `/start` 开始游戏
3. 尝试发送 `/help` 查看帮助

---

## 使用指南

### 基础命令

| 命令 | 说明 | 示例 |
|------|------|------|
| `/start` | 开始游戏，显示欢迎信息 | `/start` |
| `/help` | 查看完整帮助文档 | `/help` |
| `/agents` | 列出所有活跃官员 | `/agents` |
| `/stat` | 查看游戏状态 | `/stat` |
| `/end_turn` | 结束当前回合 | `/end_turn` |

### 与 Agent 交互

#### 单独对话

```
@governor_zhili 直隶省最近情况如何？
@minister_of_revenue 国库还剩多少银两？
```

#### 广播消息

```
@all 各位卿家，当前国家局势如何？
@all 报告各省情况
```

#### 下达命令

```
/cmd @governor_zhili 将直隶省税率提高至 10%
/cmd @minister_of_revenue @governor_zhili 查收国库和各省税收
```

### 会话隔离

每个 Telegram 用户拥有独立的游戏会话：

- **独立数据库**：`data/sessions/telegram_{chat_id}.db`
- **独立游戏进度**：回合、国库、官员状态等完全隔离
- **独立 Agent 实例**：每个会话有自己的一套 Agent

会话在以下情况会被清理：

1. 超过配置的超时时间（默认 24 小时）
2. 达到最大会话数限制时，最旧的会话被移除

---

## 配置选项

### Telegram 配置项

| 配置项 | 类型 | 默认值 | 说明 |
|--------|------|--------|------|
| `bot_token` | `str` | `""` | Telegram Bot Token（必填） |
| `mode` | `str` | `"polling"` | 运行模式：`polling` 或 `webhook`（暂只支持 polling） |
| `session_timeout_hours` | `int` | `24` | 会话超时时间（小时），≥1 |
| `response_timeout_seconds` | `int` | `30` | 响应超时时间（秒），≥5 |
| `max_sessions` | `int` | `100` | 最大并发会话数，≥1 |
| `enabled_commands` | `list[str]` | 所有命令 | 启用的命令列表 |

### 命令配置

通过 `enabled_commands` 配置项来控制启用的命令。

**可用命令：**

| 命令 | 说明 | 建议场景 |
|------|------|----------|
| `start` | 开始游戏 | 始终启用 |
| `help` | 查看帮助 | 始终启用 |
| `agents` | 列出所有官员 | 常用 |
| `stat` | 查看游戏状态 | 常用 |
| `end_turn` | 结束回合 | 核心功能，建议启用 |

**配置示例：**

```yaml
# 完整功能（所有命令）
telegram:
  enabled_commands:
    - start
    - help
    - agents
    - stat
    - end_turn

# 简化模式（仅核心命令）
telegram:
  enabled_commands:
    - start
    - help
    - end_turn

# 纯聊天模式（禁用所有命令，仅保留消息交互）
telegram:
  enabled_commands: []
```

### 环境变量命名规则

配置项使用双下划线 `__` 嵌套分隔：

```bash
# telegram.bot_token
export SIMU_TELEGRAM__BOT_TOKEN="your_token"

# telegram.session_timeout_hours
export SIMU_TELEGRAM__SESSION_TIMEOUT_HOURS=48

# telegram.max_sessions
export SIMU_TELEGRAM__MAX_SESSIONS=50

# telegram.enabled_commands（使用 JSON 数组格式）
export SIMU_TELEGRAM__ENABLED_COMMANDS='["start","help","end_turn"]'
```

---

## 开发和测试

### 运行单元测试

```bash
# 运行所有 Telegram adapter 测试
uv run pytest tests/unit/adapters/telegram/ -v

# 运行特定测试文件
uv run pytest tests/unit/adapters/telegram/test_session.py -v
uv run pytest tests/unit/adapters/telegram/test_router.py -v

# 运行特定测试
uv run pytest tests/unit/adapters/telegram/test_session.py::test_game_session_creation -v
```

### 测试覆盖

测试文件包括：

- **`test_session.py`** - 会话管理测试（9 个测试）
  - 会话创建和生命周期
  - 会话隔离验证
  - 会话管理器功能
  - 响应处理

- **`test_router.py`** - 消息路由测试（9 个测试）
  - @mentions 解析
  - 命令解析（/cmd）
  - 事件路由和发送

### 代码质量

```bash
# 运行 linter
uv run ruff check src/simu_emperor/adapters/telegram/

# 格式化代码
uv run ruff format src/simu_emperor/adapters/telegram/

# 检查类型（如果配置了 mypy）
uv run mypy src/simu_emperor/adapters/telegram/
```

---

## 常见问题

### 1. Bot 无响应

**症状：** 发送消息后 Bot 没有任何反应

**检查清单：**

- [ ] Bot Token 是否正确配置？
  ```bash
  echo $SIMU_TELEGRAM__BOT_TOKEN
  ```

- [ ] Bot 是否已启动？（查看日志输出）

- [ ] 是否与 Bot 进行过 `/start` 对话？

- [ ] LLM Provider 是否正确配置？（查看日志中的错误信息）

**解决方案：**

```bash
# 查看实时日志
uv run simu-emperor telegram 2>&1 | tee bot.log

# 检查是否有错误信息
grep -i error bot.log
```

### 2. 消息发送失败

**症状：** Bot 提示 "Failed to send message" 或类似错误

**可能原因：**

- 网络连接问题（Telegram API 访问受限）
- Bot Token 过期或被重置
- 消息格式错误（缺少 `@agent` 或 `@all`）
- 用户屏蔽了 Bot

**解决方案：**

```bash
# 测试 Telegram API 连接
curl -X POST https://api.telegram.org/bot<YOUR_BOT_TOKEN>/getMe

# 查看 Bot 日志中的错误
grep "Failed to send message" bot.log
```

### 3. 命令显示 "Unknown command"

**症状：** 发送 `/agents` 等命令时提示未知命令

**原因：** 该命令在配置中被禁用

**解决方案：**

```bash
# 检查启用的命令
echo $SIMU_TELEGRAM__ENABLED_COMMANDS

# 或查看 config.yaml
cat config.yaml | grep -A 10 enabled_commands
```

### 4. 会话数据丢失

**症状：** 游戏进度被重置

**原因：** 会话被清理（超时或达到最大会话数）

**解决方案：**

```bash
# 备份会话数据
cp -r data/sessions data/sessions.backup

# 恢复会话数据
cp -r data/sessions.backup/* data/sessions/

# 调整配置避免频繁清理
export SIMU_TELEGRAM__SESSION_TIMEOUT_HOURS=168  # 7 天
export SIMU_TELEGRAM__MAX_SESSIONS=200
```

### 5. 性能问题

**症状：** Bot 响应缓慢或占用资源过多

**优化建议：**

```yaml
telegram:
  max_sessions: 50           # 减少最大会话数
  session_timeout_hours: 12   # 缩短超时时间
  response_timeout_seconds: 20  # 缩短响应超时
```

**监控指标：**

```bash
# 查看活跃会话数
ls -la data/sessions/ | wc -l

# 查看数据库大小
du -sh data/sessions/*.db
```

### 6. HTML 格式错误

**症状：** 消息显示异常或格式错误

**已修复：** 当前版本使用 HTML 格式，避免 Markdown 解析问题。如果遇到问题：

1. 确保使用 `parse_mode="HTML"`
2. 转义特殊字符：`<` → `&lt;`，`>` → `&gt;`，`&` → `&amp;`
3. 使用 `<b>粗体</b>` 而不是 `**粗体**`

### 7. 多实例部署

**需求：** 运行多个 Bot 实例

**解决方案：**

1. 创建多个 Bot（从 @BotFather 获取多个 Token）
2. 使用不同的配置文件：

```bash
# 实例 1
 TELEGRAM_TOKEN="token1" uv run simu-emperor telegram &

# 实例 2
 TELEGRAM_TOKEN="token2" uv run simu-emperor telegram &
```

3. 使用进程管理工具（如 systemd、supervisord）

---

## 事件流映射

### Telegram 输入 → EventBus 事件

| Telegram 输入 | EventBus Event | 说明 |
|---------------|----------------|------|
| `@agent 消息` | `Event(src="player:telegram:123", dst=["agent:xxx"], type="chat")` | 单独对话 |
| `@all 消息` | `Event(src="player:telegram:123", dst=["*"], type="chat")` | 广播消息 |
| `/cmd @agent 命令` | `Event(src="player:telegram:123", dst=["agent:xxx"], type="command")` | 下达命令 |
| `/end_turn` | `Event(src="player:telegram:123", dst=["*"], type="end_turn")` | 结束回合 |

### EventBus 事件 → Telegram 输出

| EventBus Event | Telegram 输出 | 格式 |
|----------------|---------------|------|
| `Event(type="response", dst="player:telegram:123")` | 发送消息到 chat_id=123 | HTML |
| `Event(type="response", payload={"narrative": "..."})` | `📜 <b>agent_name</b>:\n\nnarrative` | HTML |

---

## 扩展开发

### 添加自定义命令

#### 步骤 1：实现命令处理器

在 `src/simu_emperor/adapters/telegram/bot.py` 的 `TelegramBotService` 类中添加方法：

```python
async def _cmd_mycommand(self, update: Update, context: Any) -> None:
    """
    自定义命令处理器

    Args:
        update: Telegram 更新对象
        context: 上下文对象
    """
    chat_id = update.effective_chat.id

    # 获取会话
    session = await self.session_manager.get_session(chat_id)

    # 你的命令逻辑
    await update.message.reply_text(
        "<b>我的自定义命令</b>\n\n这里执行你的逻辑",
        parse_mode="HTML",
    )
    logger.info(f"User {chat_id} used mycommand")
```

#### 步骤 2：注册命令

在 `_register_commands()` 方法的 `commands` 字典中添加：

```python
def _register_commands(self) -> None:
    """根据配置注册命令处理器"""
    # 命令映射
    commands = {
        "start": self._cmd_start,
        "help": self._cmd_help,
        "agents": self._cmd_agents,
        "stat": self._cmd_stat,
        "end_turn": self._cmd_end_turn,
        "mycommand": self._cmd_mycommand,  # 添加你的命令
    }
    # ... 其余代码
```

#### 步骤 3：更新配置

在 `config.yaml` 中启用新命令：

```yaml
telegram:
  enabled_commands:
    - start
    - help
    - mycommand  # 启用新命令
```

或通过环境变量：

```bash
export SIMU_TELEGRAM__ENABLED_COMMANDS='["start","help","mycommand"]'
```

#### 步骤 4：（可选）更新帮助信息

在 `_get_enabled_commands_list()` 方法中添加命令描述：

```python
def _get_enabled_commands_list(self) -> str:
    """获取启用的命令列表（格式化）"""
    command_descriptions = {
        "start": "开始游戏",
        "help": "查看帮助",
        "mycommand": "我的自定义命令",  # 添加描述
        # ... 其他命令
    }
    # ... 其余代码
```

### 自定义响应格式

编辑 `src/simu_emperor/adapters/telegram/session.py` 中的 `_on_response` 方法：

```python
async def _on_response(self, event: Event) -> None:
    """处理 Agent 响应 - 实时发送到 Telegram"""
    if event.type != EventType.RESPONSE:
        return

    narrative = event.payload.get("narrative", "")
    agent_name = event.src.replace("agent:", "")

    # 自定义消息格式（使用 HTML）
    custom_message = f"""
🎭 <b>{agent_name}</b>

{narrative}

<i>回复 @agent_name 与其对话</i>
""".strip()

    try:
        await self.bot_application.bot.send_message(
            chat_id=self.chat_id,
            text=custom_message,
            parse_mode="HTML",  # 使用 HTML 而不是 Markdown
        )
        logger.info(f"Sent response from {agent_name} to chat {self.chat_id}")
    except Exception as e:
        logger.error(f"Failed to send message to {self.chat_id}: {e}")
```

### 添加自定义消息类型

在 `router.py` 中扩展消息解析：

```python
class MessageRouter:
    async def route_and_send(self, text: str, chat_id: int, reply_func) -> None:
        # 添加自定义前缀解析
        if text.startswith("/custom "):
            await self._handle_custom(text, chat_id, reply_func)
            return

        # ... 现有逻辑

    async def _handle_custom(self, text: str, chat_id: int, reply_func) -> None:
        """处理自定义消息类型"""
        # 你的逻辑
        pass
```

---

## 相关文档

- **项目文档：**
  - [V2 架构设计](../../../../../.prd/V2_PRD.md)
  - [技术设计文档](../../../../../.design/V2_TDD.md)
  - [CLAUDE.md](../../../../../CLAUDE.md)

- **模块文档：**
  - [EventBus 文档](../../../event_bus/README.md)
  - [Agent 文档](../../../agents/README.md)
  - [Core 文档](../../../core/README.md)

- **外部资源：**
  - [python-telegram-bot 文档](https://docs.python-telegram-bot.org/)
  - [Telegram Bot API](https://core.telegram.org/bots/api)

---

## License

MIT License - 详见项目根目录 LICENSE 文件
