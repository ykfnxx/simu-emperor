# 皇帝模拟器 (Simu-Emperor)

> 事件驱动的多 Agent 回合制策略游戏

**皇帝模拟器**是一款基于大语言模型的模拟游戏。玩家扮演皇帝，AI Agent 扮演朝廷官员。官员们可能隐瞒真实情况、推诿执行命令，玩家需要通过对话和判断来治理帝国。

![Version](https://img.shields.io/badge/version-0.1.0-blue)
![Python](https://img.shields.io/badge/python-3.12+-green)
![License](https://img.shields.io/badge/license-MIT-orange)

## 简介

皇帝模拟器采用事件驱动架构，所有模块通过 EventBus 异步通信。游戏时间以 Tick 为单位自动推进（1 Tick = 1 周），AI 官员会根据游戏事件做出响应。

### 核心特性

- **AI 官员系统**：每个官员有独立的性格、说话风格和行为倾向
- **事件驱动架构**：基于 EventBus 的完全异步通信
- **Tick 时间系统**：自动推进时间，经济与人口自然增长
- **持久化记忆**：官员可跨会话回忆历史事件
- **文件驱动配置**：官员定义由 Markdown + YAML 配置，无需修改代码

### 官员行为特点

- **隐瞒信息**：官员可能隐瞒真实情况，粉饰太平
- **推诿执行**：命令执行可能打折扣，甚至拖延
- **利益博弈**：官员之间有复杂的利益关系
- **性格差异**：有的直率诚实，有的圆滑世故

## 快速开始

### 环境要求

- Python 3.12+
- Node.js 18+ (Web 界面)
- uv (推荐) 或 pip

### 安装步骤

```bash
# 克隆仓库
git clone https://github.com/xxx/simu-emperor.git
cd simu-emperor

# 安装 Python 依赖（推荐使用 uv）
uv sync

# 或使用 pip
pip install -e .
```

### 配置

```bash
# 复制配置示例
cp config.example.yaml config.yaml

# 编辑 config.yaml，设置 LLM API Key
# 支持：Anthropic Claude、OpenAI GPT、通义千问等
```

**最小配置示例：**

```yaml
llm:
  provider: "anthropic"  # 或 "openai"
  api_key: "sk-ant-xxx"  # 你的 API Key
  model: "claude-3-5-sonnet-20241022"
```

### 运行方式

#### Web 界面

```bash
# 启动后端服务器
uv run simu-emperor --host 0.0.0.0 --port 8000

# 开发模式（自动重载）
uv run simu-emperor --host 0.0.0.0 --port 8000 --reload
```

访问 http://localhost:8000 开始游戏。

#### 一键启动脚本 `start-web.sh`

**用法：**

```bash
./start-web.sh [模式]
```

**可用模式：**

| 模式 | 说明 |
|------|------|
| `dev` | 后台启动前端（dev 模式）+ 后端（默认） |
| `backend` | 仅后台启动后端 |
| `frontend` | 仅后台启动前端（dev 模式） |
| `build` | 构建前端后，仅后台启动后端 |
| `status` | 查看前后端进程状态 |
| `stop` | 停止前后端后台进程 |

**示例：**

```bash
# 开发模式（前后端都启动）
./start-web.sh dev

# 仅启动后端
./start-web.sh backend

# 查看状态
./start-web.sh status

# 停止所有服务
./start-web.sh stop
```

**日志和 PID：**

- 所有日志输出到 `logs/` 目录，分类存储
- PID 文件存储在 `logs/pids/`
- 支持 `./start-web.sh status` 查看运行状态

#### 清理运行时数据

```bash
# 预览将要删除的文件（不实际删除）
./scripts/clean_runtime_data.sh --dry-run

# 执行清理
./scripts/clean_runtime_data.sh
```

**清理内容：**

| 类别 | 文件/目录 |
|------|----------|
| 游戏数据库 | `game.db` |
| Agent 运行时数据 | `data/agent/` |
| 记忆系统数据 | `data/memory/` |
| 会话数据 | `data/sessions/` |
| 日志文件 | `data/logs/`, `logs/` |
| Python 缓存 | `__pycache__`, `.pytest_cache`, `.ruff_cache` |

**保留内容：** 模板文件、存档、配置、源代码等均不受影响。

## 功能介绍

### 游戏玩法

1. **扮演皇帝**：你是大清皇帝，需要治理国家
2. **与官员交互**：通过命令或对话与官员沟通
3. **时间推进**：游戏时间自动推进（每 5 秒 = 1 周）
4. **管理国家**：税收、拨款、调整税率、处理事件

### 官员系统

官员配置文件位于 `data/default_agents/` 目录，每个官员由 `soul.md`（性格定义）和 `data_scope.yaml`（数据权限）组成。可通过修改这些文件自定义官员行为。

### 自然语言交互

直接用自然语言与官员对话：

```
> 江南今年的税收如何？
> 给直隶拨款一万两银子
> 提高全国税率到 15%
```

## 配置说明

### LLM 配置

支持多种 LLM Provider：

```yaml
llm:
  provider: "anthropic"  # 可选: mock, anthropic, openai
  api_key: "sk-ant-xxx"
  model: "claude-3-5-sonnet-20241022"
  context_window: 200000  # 可选，自动检测
```

| Provider | 说明 | 推荐模型 |
|----------|------|----------|
| `anthropic` | Anthropic Claude | claude-3-5-sonnet-20241022 |
| `openai` | OpenAI GPT | gpt-4o, gpt-4-turbo |
| `mock` | 测试模式（无 API 调用） | - |

### 记忆系统配置

```yaml
memory:
  enabled: true
  context:
    max_tokens: 8000          # 上下文窗口大小
    threshold_ratio: 0.95     # 触发总结的比例
    keep_recent_events: 20    # 滑动窗口保留事件数
  retrieval:
    default_max_results: 5    # 检索最大结果数
    cross_session_enabled: true  # 跨会话检索
```

**记忆层级：**

- **短期记忆**：最近 3 回合的详细记录
- **长期记忆**：自动总结的历史摘要
- **跨会话检索**：可查询历史会话的事件

## 文档链接

- [架构文档](docs/architecture/ARCHITECTURE.md) — 事件驱动架构详解
- [开发指南](CLAUDE.md) — 开发命令和规范
- [配置示例](config.example.yaml) — 完整配置参考

## 开发相关

### 运行测试

```bash
# 运行所有测试
uv run pytest tests/

# 运行单个测试文件
uv run pytest tests/unit/test_engine.py

# 查看覆盖率
uv run pytest --cov=simu_emperor tests/
```

### 代码规范

```bash
# 代码检查
uv run ruff check .

# 自动格式化
uv run ruff format .
```

### 项目结构

```
simu-emperor/
├── src/simu_emperor/        # 源代码
│   ├── event_bus/           # 事件总线
│   ├── engine/              # 游戏引擎
│   ├── agents/              # AI 官员系统
│   ├── memory/              # 记忆系统
│   ├── cli/                 # 命令行界面
│   ├── application/         # 应用服务层
│   └── adapters/web/        # Web 适配器
├── data/
│   ├── default_agents/      # 官员模板
│   ├── skills/              # 技能定义
│   └── memory/              # 运行时记忆存储
├── tests/                   # 测试代码
├── docs/                    # 文档
└── web/                     # Web 前端
```

## 技术栈

- **后端**: Python 3.12+, FastAPI, asyncio, aiosqlite
- **前端**: React, TypeScript, Vite (可选)
- **LLM**: Anthropic Claude / OpenAI GPT
- **数据库**: SQLite
- **测试**: pytest, pytest-asyncio

## 许可证

MIT License

## 贡献

欢迎提交 Issue 和 Pull Request！

---

**皇帝模拟器** — 体验与 AI 官员斗智斗勇的乐趣
