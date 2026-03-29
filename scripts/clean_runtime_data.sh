#!/bin/bash
# 清理运行时生成的中间文件和日志
# 使用方法: ./scripts/clean_runtime_data.sh [--dry-run]

set -e

# 颜色输出
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# 干运行模式（只显示将要删除的内容，不实际删除）
DRY_RUN=false
if [ "$1" = "--dry-run" ]; then
    DRY_RUN=true
    echo -e "${YELLOW}=== 干运行模式：只显示将要删除的文件，不实际删除 ===${NC}\n"
fi

# 删除文件的函数
cleanup_file() {
    local file="$1"
    local description="$2"

    if [ -e "$file" ]; then
        if [ "$DRY_RUN" = true ]; then
            echo -e "${YELLOW}[干运行]${NC} 将删除: $file ($description)"
        else
            rm -rf "$file"
            echo -e "${GREEN}✓${NC} 已删除: $file ($description)"
        fi
    else
        echo -e "${YELLOW}-${NC} 不存在: $file ($description)"
    fi
}

echo -e "${RED}=== 清理运行时数据 ===${NC}\n"

# 游戏数据库
echo "1. 游戏数据库："
cleanup_file "data/game.db" "游戏数据库文件"

# 运行时数据目录
echo -e "\n2. Agent 运行时数据："
cleanup_file "data/agent" "Agent 运行时目录（soul.md、data_scope.yaml 等运行副本）"

echo -e "\n3. 记忆系统数据："
cleanup_file "data/memory" "V3 记忆系统目录（tape.jsonl、manifest.json）"

echo -e "\n4. 会话数据："
cleanup_file "data/sessions" "会话数据目录"

echo -e "\n5. 日志文件："
cleanup_file "data/logs" "数据目录下的日志"
cleanup_file "logs" "根目录下的日志"

# Python 缓存
echo -e "\n6. Python 缓存："
cleanup_file "__pycache__" "Python 字节码缓存"
cleanup_file ".pytest_cache" "Pytest 缓存"
cleanup_file ".ruff_cache" "Ruff 缓存"

# 清理完成后的信息
echo -e "\n${GREEN}=== 清理完成 ===${NC}"

echo -e "\n${YELLOW}=== 保留的文件和目录 ===${NC}"
echo "✅ default_agents/ - Agent 模板（未修改）"
echo "✅ skills/ - 技能模板"
echo "✅ saves/ - 存档文件"
echo "✅ config.yaml - 配置文件"
echo "✅ config.example.yaml - 配置示例"
echo "✅ event_templates.json - 事件模板"
echo "✅ initial_provinces.json - 初始省份数据"
echo "✅ role_map.md - 角色映射"
echo "✅ RULE.md - 规则文档"
echo "✅ CLAUDE.md - Claude Code 指导文档"
echo "✅ src/ - 源代码"
echo "✅ tests/ - 测试代码"
echo "✅ scripts/ - 脚本文件"
echo "✅ data/skills/ - 技能文件（只读）"

if [ "$DRY_RUN" = true ]; then
    echo -e "\n${YELLOW}提示：这是干运行模式。要实际删除文件，请运行：${NC}"
    echo "  ./scripts/clean_runtime_data.sh"
else
    echo -e "\n${GREEN}提示：如需查看将要删除的文件（不实际删除），请运行：${NC}"
    echo "  ./scripts/clean_runtime_data.sh --dry-run"
fi
