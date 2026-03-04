# Scripts

此目录包含项目维护脚本。

## clean_runtime_data.sh

清理运行时生成的中间文件和日志。

### 使用方法

**干运行模式（推荐先运行）**：
```bash
./scripts/clean_runtime_data.sh --dry-run
```
只显示将要删除的文件，不实际删除。

**实际删除**：
```bash
./scripts/clean_runtime_data.sh
```

### 清理的内容

1. **游戏数据库**: `game.db`
2. **Agent 运行时数据**: `data/agent/`（运行时副本，可从 `default_agents/` 重建）
3. **记忆系统数据**: `data/memory/`（V3 记忆系统的 tape.jsonl、manifest.json）
4. **会话数据**: `data/sessions/`
5. **日志文件**: `data/logs/`、`logs/`
6. **Python 缓存**: `__pycache__/`、`.pytest_cache/`、`.ruff_cache/`

### 保留的内容

- ✅ `default_agents/` - Agent 模板（未修改）
- ✅ `skills/` - 技能模板
- ✅ `saves/` - 存档文件
- ✅ `config.yaml` - 配置文件
- ✅ 所有源代码和测试代码

### 何时使用

- 运行测试后清理临时数据
- 重新开始游戏时清除旧数据
- 调试内存系统时重置状态
- 减小仓库大小（删除已跟踪的运行时文件）

### 警告

⚠️ 此脚本会删除：
- 游戏进度（无法恢复）
- 记忆系统的历史记录
- 所有日志文件

请确保已保存重要数据后再运行！
