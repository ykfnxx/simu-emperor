#!/usr/bin/env python3
"""
事件系统测试

演示Agent主动事件生成和三层数据模型的使用
"""

import asyncio
import sys
sys.path.insert(0, '.')

from events.event_generator import EventGenerator
from events.agent_event_generator import AgentEventGenerator
from events.event_manager import EventManager
from events.event_models import Event
from agents.personality import PERSONALITY_PRESETS, PersonalityTrait
from db.database import Database
from db.event_database import save_event, get_active_events, update_event

# 将新方法添加到Database类
Database.save_event = save_event
Database.get_active_events = get_active_events
Database.update_event = update_event


async def test_event_system():
    """测试完整的事件系统"""

    print("=" * 70)
    print("事件系统测试")
    print("=" * 70)

    # 初始化
    db = Database(":memory:")  # 使用内存数据库
    db.init_database()

    event_manager = EventManager(db)
    event_generator = EventGenerator()
    agent_event_generator = AgentEventGenerator()

    # 创建测试省份数据
    provinces = [
        {
            'province_id': 1,
            'name': '首都',
            'population': 35000,
            'development_level': 7.0,
            'loyalty': 85,
            'stability': 72,
            'actual_income': 850.0,
            'actual_expenditure': 600.0
        }
    ]

    game_state = {
        'treasury': 1000.0,
        'current_month': 1
    }

    # 测试1：生成普通事件
    print("\n[测试1] 生成普通事件")
    print("-" * 70)

    events = event_generator.generate_events(game_state, provinces, 2)

    for event in events:
        print(f"事件: {event.name}")
        print(f"  类型: {event.event_type}")
        print(f"  省份: {event.province_id}")
        print(f"  严重程度: {event.severity}")
        print(f"  持续效果: {len(event.continuous_effects)}个")

        for effect in event.continuous_effects:
            print(f"    - {effect.scope}: {effect.operation} {effect.value}")
            if effect.duration:
                print(f"      持续{effect.duration}回合")

        # 保存事件
        event_manager.save_event(event)
        print()

    # 测试2：Agent事件生成
    print("\n[测试2] Agent生成事件")
    print("-" * 70)

    # 创建不同性格的Governor
    for name, personality in PERSONALITY_PRESETS.items():
        if 'honest' in name:
            # 诚实的官员
            honest_governor = type('Governor', (), {
                'agent_id': f'governor_honest',
                'personality': personality
            })()

            # 生成事件
            agent_event = agent_event_generator.generate_agent_event(
                honest_governor,
                provinces[0],
                {'treasury': 1000, 'month': 2, 'central_attention': 0.3}
            )

            if agent_event:
                print(f"诚实官员生成事件: {agent_event.name}")
                print(f"  是否编造: {agent_event.is_fabricated}")
                print(f"  叙事: {agent_event.narrative[:50]}...")
                event_manager.save_event(agent_event)
            else:
                print("诚实官员选择不生成事件")

        elif 'corrupt' in name:
            # 腐败的官员
            corrupt_governor = type('Governor', (), {
                'agent_id': f'governor_corrupt',
                'personality': personality
            })()

            # 生成事件
            agent_event = agent_event_generator.generate_agent_event(
                corrupt_governor,
                provinces[1],
                {'treasury': 1000, 'month': 2, 'central_attention': 0.3, 'needs_cover': True}
            )

            if agent_event:
                print(f"腐败官员生成事件: {agent_event.name}")
                print(f"  是否编造: {agent_event.is_fabricated}")
                print(f"  理由: {agent_event.fabrication_reason}")
                print(f"  叙事: {agent_event.narrative[:50]}...")
                event_manager.save_event(agent_event)
            else:
                print("腐败官员选择不生成事件")

    # 测试3：事件效果计算
    print("\n[测试3] 事件效果计算")
    print("-" * 70)

    # 加载活跃事件
    active_events = event_manager.load_active_events(2)
    print(f"活跃事件数量: {len(active_events)}")

    # 计算省份1的修正值
    from events.event_effects import calculate_event_modifiers

    modifiers = calculate_event_modifiers(active_events, province_id=1, current_month=2)

    print(f"\n省份1的事件修正值:")
    for key, value in modifiers.items():
        if value != 1.0 and value != 0.0:
            print(f"  {key}: {value:.2f}")

    # 测试4：数据库存储和查询
    print("\n[测试4] 数据库操作")
    print("-" * 70)

    # 查询Agent生成的事件
    agent_events = event_manager.get_agent_generated_events()
    print(f"Agent生成事件数量: {len(agent_events)}")

    for event in agent_events:
        print(f"  - {event.name} (编造: {event.is_fabricated})")

    # 查询隐藏事件
    hidden_events = event_manager.get_hidden_events()
    print(f"\n隐藏事件数量: {len(hidden_events)}")

    # 获取事件摘要
    summary = event_manager.get_event_summary(2)
    print(f"\n事件摘要:")
    print(f"  总活跃事件: {summary['total_active']}")
    print(f"  全国事件: {summary['national_events']}")
    print(f"  省份事件: {summary['province_events']}")
    print(f"  Agent生成: {summary['agent_generated_events']}")
    print(f"  隐藏事件: {summary['hidden_events']}")

    # 测试5：事件过期清理
    print("\n[测试5] 事件生命周期管理")
    print("-" * 70)

    # 模拟时间推进
    expired = event_manager.cleanup_expired_events(5)
    print(f"清理过期事件: {len(expired)}个")

    # 重新加载
    active_events = event_manager.load_active_events(5)
    print(f"第5个月活跃事件: {len(active_events)}")

    print("\n" + "=" * 70)
    print("测试完成")
    print("=" * 70)


if __name__ == "__main__":
    asyncio.run(test_event_system())
