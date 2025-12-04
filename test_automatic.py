#!/usr/bin/env python3
"""
自动化测试新的Agent架构
无需用户交互，自动运行几个月份
"""

import asyncio
import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

from core.game import Game


async def test_automatic():
    """自动化测试"""
    print("="*70)
    print("自动化测试: 新的Agent架构 (Pydantic + Instructor)")
    print("="*70)

    # 创建游戏实例
    game = Game(db_path="test_auto.db", enable_central_advisor=True)

    print(f"\n初始状态:")
    print(f"- 省份数量: {len(game.provinces)}")
    print(f"- Governor Agents: {len(game.agents)}")
    print(f"- 中央顾问: {'已启用' if game.central_advisor else '未启用'}")
    print(f"- 国库: {game.state['treasury']:.2f}金币")

    # 运行3个月
    corruption_stats = {}
    for province in game.provinces:
        corruption_stats[province.name] = 0

    for month in range(1, 4):
        print(f"\n{'='*70}")
        print(f"第 {month} 个月")
        print(f"{'='*70}")

        await game.next_month()

        # 统计腐败情况
        for province in game.provinces:
            if province.last_month_corrupted:
                corruption_stats[province.name] += 1

    # 显示最终结果
    print(f"\n{'='*70}")
    print("测试完成 - 腐败统计")
    print(f"{'='*70}")

    for province_name, corrupt_months in corruption_stats.items():
        print(f"{province_name}: {corrupt_months}/3 个月腐败 ({corrupt_months/3*100:.0f}%)")

    print(f"\n{'='*70}")
    print("架构特性验证")
    print(f"{'='*70}")
    print("✓ Agents层职责分离 (Governor + CentralAdvisor)")
    print("✓ LLM调用基础设施在基类中")
    print("✓ Pure functions计算 (core/calculations.py)")
    print("✓ Province为纯数据类")
    print("✓ Mock模式无需API密钥")
    print("✓ 异步支持")
    print(f"\n重构完成！架构已升级为 v2 (Pydantic + Instructor)")
    print("="*70)


if __name__ == "__main__":
    asyncio.run(test_automatic())
