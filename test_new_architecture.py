#!/usr/bin/env python3
"""
测试新的Agent架构
"""

import asyncio
import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

from core.game import Game


async def test_game_with_agents():
    """测试带有Agent的游戏"""
    print("="*70)
    print("测试新的Agent架构")
    print("="*70)

    # 创建游戏实例（启用中央顾问）
    game = Game(db_path="test_new_arch.db", enable_central_advisor=True)

    print(f"\n初始状态:")
    print(f"- 省份数量: {len(game.provinces)}")
    print(f"- Governor Agents: {len(game.agents)}")
    print(f"- 中央顾问: {'已启用' if game.central_advisor else '未启用'}")
    print(f"- 国库: {game.state['treasury']:.2f}金币")

    # 运行几个月
    for month in range(1, 4):
        print(f"\n{'='*70}")
        print(f"第 {month} 个月")
        print(f"{'='*70}")

        # 进入下一月（异步）
        await game.next_month()

        # 显示各省份状态
        print("\n[省份状态]")
        for province in game.provinces:
            status = "🔴瞒报" if province.last_month_corrupted else "✅诚实"
            diff = province.actual_income - province.reported_income
            print(f"  {province.name}: {status}")
            print(f"    收入: {province.reported_income:.0f}/{province.actual_income:.0f} "
                  f"({diff:+.0f}) | 忠诚度: {province.loyalty:.0f}")

        input("\n按Enter继续...")

    print("\n" + "="*70)
    print("测试完成！")
    print("="*70)


if __name__ == "__main__":
    # 运行异步测试
    asyncio.run(test_game_with_agents())
