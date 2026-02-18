#!/usr/bin/env python
"""游戏初始化脚本：创建新游戏存档。

运行方式：uv run python scripts/seed_game.py

功能：
1. 从 initial_provinces.json 加载初始数据
2. 初始化数据库
3. 创建 GameState 并保存
4. 初始化 Agent 文件系统
"""

from __future__ import annotations

import asyncio
from pathlib import Path

from simu_emperor.agents.llm.providers import MockProvider
from simu_emperor.config import GameConfig
from simu_emperor.engine.models.state import GameState
from simu_emperor.game import GameLoop
from simu_emperor.persistence.database import init_database
from simu_emperor.player.web.app import load_initial_data


async def seed_game(
    db_path: str = "game.db",
    data_dir: Path = Path("data"),
    seed: int | None = None,
) -> GameLoop:
    """初始化新游戏。

    Args:
        db_path: 数据库路径
        data_dir: 数据根目录
        seed: 随机种子（None 为随机）

    Returns:
        初始化完成的 GameLoop 实例
    """
    config = GameConfig(db_path=db_path, data_dir=data_dir, seed=seed)
    conn = await init_database(db_path)
    provider = MockProvider()
    initial_data = load_initial_data(data_dir)
    state = GameState(base_data=initial_data)
    loop = GameLoop(state=state, config=config, provider=provider, conn=conn)

    agents = loop.initialize_agents()
    print(f"游戏 ID: {state.game_id}")
    print(f"初始回合: {state.current_turn}")
    print(f"初始阶段: {state.phase.value}")
    print(f"活跃 Agent: {agents}")
    print(f"国库: {state.base_data.imperial_treasury}")
    for p in state.base_data.provinces:
        print(f"  - {p.name} ({p.province_id}): 人口 {p.population.total}")

    # 保存初始状态
    await loop.save_game()
    print(f"\n游戏已保存到数据库: {db_path}")

    return loop


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description="初始化新游戏")
    parser.add_argument("--db", default="game.db", help="数据库路径")
    parser.add_argument("--data-dir", type=Path, default=Path("data"), help="数据根目录")
    parser.add_argument("--seed", type=int, default=None, help="随机种子")
    args = parser.parse_args()

    asyncio.run(seed_game(db_path=args.db, data_dir=args.data_dir, seed=args.seed))


if __name__ == "__main__":
    main()
