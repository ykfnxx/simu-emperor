#!/usr/bin/env python3
"""
演示事件系统在CLI中的显示

快速演示三层数据模型和事件显示逻辑
"""

import asyncio
import random
from typing import List, Dict, Any

# Mock数据
class MockProvince:
    def __init__(self, name, actual_income, actual_expenditure, reported_income, reported_expenditure):
        self.name = name
        self.actual_income = actual_income
        self.actual_expenditure = actual_expenditure
        self.reported_income = reported_income
        self.reported_expenditure = reported_expenditure
        self.actual_surplus = 0
        self.reported_surplus = 0
        self.last_month_corrupted = reported_income < actual_income * 0.95

    def update_surplus(self):
        """Update surplus"""
        actual_surplus = self.actual_income - self.actual_expenditure
        reported_surplus = self.reported_income - self.reported_expenditure
        self.actual_surplus += actual_surplus
        self.reported_surplus += reported_surplus

class MockEvent:
    def __init__(self, name, event_type, severity, is_fabricated=False, visibility='provincial', province_id=None):
        self.name = name
        self.event_type = event_type
        self.severity = severity
        self.is_fabricated = is_fabricated
        self.visibility = visibility
        self.province_id = province_id

class MockGame:
    def __init__(self, debug_mode=False):
        self.state = {'current_month': 1, 'treasury': 1000, 'debug_mode': debug_mode}

        # Initialize province (single province model)
        self.provinces = [
            MockProvince("Capital", 2000, 800, 1600, 1000),  # Capital: merged single province
        ]

        # Initialize events
        self.events = [
            MockEvent("Economic Prosperity", "national", 0.7),
            MockEvent("Harvest", "province", 0.5, province_id=1),
            MockEvent("Fiscal Shortage", "province", 0.6, is_fabricated=True, province_id=1),
            MockEvent("Rebellion", "province", 0.8, visibility='hidden', province_id=1),
        ]

        # Calculate surplus
        for province in self.provinces:
            province.update_surplus()

    def show_main_menu(self):
        """Display main menu"""
        print(f"\n{'='*60}")
        print(f"Month {self.state['current_month']} - Ruler Console")
        print(f"{'='*60}")
        print(f"Treasury Balance: {self.state['treasury']:.2f} gold")
        print(f"Debug Mode: {'ON' if self.state['debug_mode'] else 'OFF'}")

        # 显示活跃事件数量
        active_events = [e for e in self.events if e.event_type in ['national', 'province']]
        national_events = [e for e in active_events if e.event_type == 'national']
        province_events = [e for e in active_events if e.event_type == 'province']
        print(f"Active Events: National{len(national_events)}, Provincial{len(province_events)}个")
        print(f"\n1. View Financial Report")
        print(f"2. View Provincial Events")
        print(f"3. Toggle Debug Mode")
        print(f"4. Next Month")
        print(f"q. Quit")

    def show_financial_report(self):
        """Display financial report"""
        print(f"\n{'='*70}")
        print(f"Month {self.state['current_month']} Financial Report")
        print(f"{'='*70}\n")

        debug_mode = self.state['debug_mode']

        for province in self.provinces:
            print(f"【{province.name}】")

            # 显示盈余对比
            if debug_mode:
                print(f"  上报盈余: {province.reported_surplus:+.2f} gold")
                print(f"  真实盈余: {province.actual_surplus:+.2f} gold")

                difference = province.actual_surplus - province.reported_surplus
                if abs(difference) > 50:
                    print(f"  ⚠️  差异: {difference:+.2f} gold")
            else:
                print(f"  盈余: {province.reported_surplus:+.2f} gold")

            # 显示事件影响（Debug模式）
            if debug_mode:
                province_events = [e for e in self.events
                                 if e.event_type == 'province']
                if province_events:
                    print(f"  活跃Event: {len(province_events)}个")

            print()

    def show_province_events(self):
        """View provincial events"""
        print(f"\n{'='*70}")
        print("省级事件查看")
        print(f"{'='*70}\n")

        debug_mode = self.state['debug_mode']
        province_events = [e for e in self.events if e.event_type == 'province']

        if not province_events:
            print("暂无省级事件\n")
            return

        for event in province_events:
            # Debug模式显示所有事件，正常模式只显示非隐藏事件
            if event.visibility == 'hidden' and not debug_mode:
                continue

            print(f"Event: {event.name}")
            print(f"  严重程度: {event.severity:.1f}")
            print(f"  类型: {event.event_type}")

            if debug_mode:
                print(f"  编造: {'是' if event.is_fabricated else '否'}")
                print(f"  可见性: {event.visibility}")

            print()

    def toggle_debug_mode(self):
        """Toggle debug mode"""
        self.state['debug_mode'] = not self.state['debug_mode']
        print(f"\nDebug Mode: {'开启' if self.state['debug_mode'] else 'OFF'}")

    async def next_month(self):
        """Advance to next month"""
        self.state['current_month'] += 1
        print(f"\nAdvancing to month {self.state['current_month']}")

        # 生成新事件（基于概率）
        if random.random() < 0.3:  # 30%概率生成事件
            new_events = [
                MockEvent("自然灾害", "national", random.uniform(0.6, 0.9)),
                MockEvent("商业繁荣", "province", random.uniform(0.3, 0.6)),
                MockEvent("官员调查", "province", random.uniform(0.5, 0.8), is_fabricated=True)
            ]
            self.events.extend(new_events)
            print(f"生成了 {len(new_events)} 个新事件")

        # 更新省份数据（随机变化模拟实际游戏）
        for province in self.provinces:
            # 随机变化收入和支出
            province.actual_income += random.uniform(-50, 50)
            province.actual_expenditure += random.uniform(-20, 20)

            # Agent调整上报值（模拟欺瞒）
            province.reported_income = province.actual_income * random.uniform(0.8, 1.2)
            province.reported_expenditure = province.actual_expenditure * random.uniform(0.9, 1.1)

            # 更新盈余
            province.update_surplus()

        self.state['treasury'] += sum([p.actual_income - p.actual_expenditure for p in self.provinces])


def main():
    """主函数"""
    game = MockGame(debug_mode=False)

    while True:
        game.show_main_menu()
        choice = input("\nSelect operation: ").strip()

        if choice == '1':
            game.show_financial_report()
        elif choice == '2':
            game.show_province_events()
        elif choice == '3':
            game.toggle_debug_mode()
        elif choice == '4':
            asyncio.run(game.next_month())
        elif choice.lower() == 'q':
            print("\nThanks for playing!")
            break
        else:
            print("\nInvalid choice")

        input("\nPress Enter to continue...")


if __name__ == '__main__':
    main()
