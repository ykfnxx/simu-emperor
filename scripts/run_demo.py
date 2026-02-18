#!/usr/bin/env python
"""无 LLM 演示模式：运行完整游戏流程。

演示脚本使用 MockProvider 模拟 Agent 响应，无需真实 LLM API。
运行方式：uv run python scripts/run_demo.py

流程：
1. 初始化游戏（数据库、GameLoop、Agent 文件系统）
2. 运行 3 个完整回合（RESOLUTION → SUMMARY → INTERACTION → EXECUTION）
3. 在 INTERACTION 阶段模拟玩家对话和命令
4. 输出每回合的关键数据变化
"""

from __future__ import annotations

import asyncio
from pathlib import Path

from simu_emperor.agents.llm.providers import MockProvider
from simu_emperor.config import GameConfig
from simu_emperor.engine.models.events import EventSource, PlayerEvent
from simu_emperor.engine.models.state import GameState
from simu_emperor.game import GameLoop
from simu_emperor.persistence.database import init_database
from simu_emperor.player.web.app import load_initial_data


def print_separator(title: str) -> None:
    print(f"\n{'=' * 60}")
    print(f"  {title}")
    print("=" * 60)


def print_state(loop: GameLoop) -> None:
    state = loop.state
    print(f"回合: {state.current_turn} | 阶段: {state.phase.value}")
    print(f"国库: {state.base_data.imperial_treasury:.0f} 两")
    for p in state.base_data.provinces:
        print(
            f"  {p.name}: 人口 {p.population.total:.0f} | 粮仓 {p.granary_stock:.0f} | 库银 {p.local_treasury:.0f}"
        )


async def run_demo(num_turns: int = 3) -> None:
    # 使用临时数据库
    import tempfile

    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "demo.db"

        # 初始化
        config = GameConfig(db_path=str(db_path), data_dir=Path("data"), seed=42)
        conn = await init_database(str(db_path))
        provider = MockProvider()
        initial_data = load_initial_data(config.data_dir)
        state = GameState(base_data=initial_data)
        loop = GameLoop(state=state, config=config, provider=provider, conn=conn)

        print_separator("初始化游戏")
        agents = loop.initialize_agents()
        print(f"活跃 Agent: {agents}")
        print_state(loop)

        for turn_num in range(1, num_turns + 1):
            print_separator(f"第 {turn_num} 回合")

            # 1. RESOLUTION → SUMMARY
            print("\n[RESOLUTION] 回合结算...")
            await loop.advance_to_resolution()
            print_state(loop)

            # 2. SUMMARY → INTERACTION
            print("\n[SUMMARY] Agent 汇总报告...")
            reports = await loop.advance_to_summary()
            for agent_id, report in reports.items():
                print(f"  {agent_id}: {report[:80]}...")

            # 3. INTERACTION: 模拟玩家对话和命令
            print("\n[INTERACTION] 玩家交互...")
            agents_list = loop._agent_manager.list_active_agents()
            if agents_list:
                agent_id = agents_list[0]
                response = await loop.handle_player_message(agent_id, "今年收成如何？")
                print(f"  玩家 → {agent_id}: 今年收成如何？")
                print(f"  {agent_id} → 玩家: {response[:80]}...")

            # 提交一个命令
            command = PlayerEvent(
                source=EventSource.PLAYER,
                command_type="build_granary",
                description="修缮粮仓",
                target_province_id="zhili",
                turn_created=loop.state.current_turn,
            )
            loop.submit_command(command)
            print(f"  提交命令: {command.command_type} → {command.target_province_id}")

            # 4. INTERACTION → EXECUTION
            print("\n[EXECUTION] 执行命令...")
            events = await loop.advance_to_execution()
            for event in events:
                print(f"  事件: {event.description[:60]}...")

            print_state(loop)

        print_separator("演示完成")
        print(f"共运行 {num_turns} 个回合")
        print(f"历史记录: {len(loop.state.history)} 条")

        await conn.close()


def main() -> None:
    print("皇帝模拟器 - 无 LLM 演示模式")
    print("使用 MockProvider 模拟 Agent 响应\n")
    asyncio.run(run_demo(num_turns=3))


if __name__ == "__main__":
    main()
