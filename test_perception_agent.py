"""
独立测试PerceptionAgent模块

这个脚本会：
1. 创建一个测试数据库文件（test_perception.db）
2. 生成12个月的测试数据
3. 运行PerceptionAgent
4. 输出详细的PerceptionContext结果
5. 清理测试数据库
"""

import asyncio
import sys
import os
import sqlite3
sys.path.insert(0, os.path.dirname(__file__))

from db.database import Database
from agents.province.perception_agent import PerceptionAgent


TEST_DB_PATH = "test_perception.db"


def setup_test_data(db: Database):
    """创建测试数据：12个月的历史数据，包含一些事件"""
    print("Setting up test data...")

    conn = db.get_connection()
    cursor = conn.cursor()

    # 删除现有数据
    cursor.execute("DELETE FROM provinces")
    cursor.execute("DELETE FROM monthly_reports")
    cursor.execute("DELETE FROM events")
    cursor.execute("DELETE FROM special_events_index")

    # 插入测试省份
    cursor.execute("""
        INSERT INTO provinces (province_id, name, population, development_level,
                               loyalty, stability, base_income, corruption_tendency)
        VALUES (1, 'Test Province', 50000, 7.5, 70.0, 65.0, 800, 0.3)
    """)

    # 插入12个月的历史数据
    for month in range(1, 13):
        # 模拟逐渐增长的趋势
        income = 800 + month * 10  # 800 → 920
        expenditure = 600 + month * 5  # 600 → 655

        # 忠诚度和稳定性的变化（第6个月有叛乱）
        if month < 6:
            loyalty = 70.0 + month * 0.5  # 逐渐增长到73
            stability = 65.0 + month * 0.3  # 逐渐增长到66.8
        elif month == 6:
            loyalty = 45.0  # 叛乱导致骤降
            stability = 40.0
        else:
            # 恢复期
            loyalty = 45.0 + (month - 6) * 5  # 45 → 75
            stability = 40.0 + (month - 6) * 4.5  # 40 → 67.5

        cursor.execute("""
            INSERT INTO monthly_reports (
                month, year, province_id,
                actual_income, actual_expenditure,
                reported_income, reported_expenditure,
                treasury_change
            ) VALUES (?, 1, ?, ?, ?, ?, ?, ?)
        """, (
            month, 1,
            income, expenditure,
            income, expenditure,  # 假设诚实报告
            income - expenditure
        ))

        # 添加事件
        if month == 3:
            # 轻度灾害
            cursor.execute("""
                INSERT INTO events (event_id, province_id, start_month, end_month,
                                   name, severity, event_type, description)
                VALUES (?, 1, ?, ?, 'Minor Flood', 0.4, 'disaster',
                        'Heavy rains caused minor flooding in agricultural areas')
            """, (f"evt_{month}", month, month))

        elif month == 6:
            # 叛乱
            cursor.execute("""
                INSERT INTO events (event_id, province_id, start_month, end_month,
                                   name, severity, event_type, description)
                VALUES (?, 1, ?, ?, 'Peasant Uprising', 0.7, 'rebellion',
                        'Large-scale unrest in northern territory over tax policies')
            """, (f"evt_{month}", month, month))

            # 在特殊事件索引中记录
            cursor.execute("""
                INSERT INTO special_events_index (
                    event_id, province_id, event_category, month, year,
                    event_name, severity, impact_description, is_resolved
                ) VALUES (?, 1, 'rebellion', ?, 1, 'Peasant Uprising', 0.7,
                        'Large-scale unrest in northern territory', 0)
            """, (f"evt_{month}", month))

        elif month == 9:
            # 庆祝活动（提升忠诚度）
            cursor.execute("""
                INSERT INTO events (event_id, province_id, start_month, end_month,
                                   name, severity, event_type, description)
                VALUES (?, 1, ?, ?, 'Harvest Festival', 0.2, 'celebration',
                        'Annual harvest celebration boosted morale')
            """, (f"evt_{month}", month, month))

    conn.commit()
    conn.close()

    print("✓ Created 12 months of test data")
    print("  - Income: 800 → 920 (gradual growth)")
    print("  - Month 3: Minor flood (severity 0.4)")
    print("  - Month 6: Peasant uprising (severity 0.7)")
    print("  - Month 9: Harvest festival (severity 0.2)")
    print("  - Loyalty: 70 → 73 → 45 (rebellion) → 75 (recovery)")
    print()


async def test_perception_agent():
    """测试PerceptionAgent"""
    print("="*70)
    print("Testing PerceptionAgent")
    print("="*70)
    print()

    # 清理旧的测试数据库
    if os.path.exists(TEST_DB_PATH):
        os.remove(TEST_DB_PATH)
        print("Old test database removed")

    # 1. 创建测试数据库
    print("1. Creating test database...")
    db = Database(TEST_DB_PATH)
    print("   ✓ Base tables created")

    # 2. 创建Province Agent表
    print("\n2. Running Province Agent migrations...")
    from db.migrations.add_province_agent_tables import migrate
    migrate(TEST_DB_PATH)
    print("   ✓ Province Agent tables created")

    # 3. 创建测试数据
    print("\n3. Creating test data...")
    setup_test_data(db)

    # 4. 初始化PerceptionAgent
    print("\n4. Initializing PerceptionAgent...")
    perception_agent = PerceptionAgent(
        agent_id="test_perception",
        config={
            'province_id': 1,
            'llm_config': {
                'enabled': True,
                'mock_mode': True  # 使用mock模式，不需要API
            }
        },
        db=db
    )
    print("✓ PerceptionAgent initialized")

    # 5. 运行perceive方法
    print("\n5. Running perceive() method...")
    print("   Analyzing data for month 13, year 2...")

    perception_context = await perception_agent.perceive(
        province_id=1,
        current_month=13,  # 第2年第1个月
        current_year=2
    )

    # 6. 输出结果
    print("\n" + "="*70)
    print("PERCEPTION CONTEXT OUTPUT")
    print("="*70)

    print(f"\n📍 Province: {perception_context.province_name} (ID: {perception_context.province_id})")
    print(f"📅 Current: Month {perception_context.current_month}, Year {perception_context.current_year}")
    print(f"📊 Data Quality: {perception_context.data_quality}")

    # Warnings
    if perception_context.warnings:
        print(f"\n⚠️  Warnings:")
        for warning in perception_context.warnings:
            print(f"   - {warning}")

    # Recent Data
    print(f"\n📈 Recent Month Data (Month {perception_context.recent_data.month}):")
    recent = perception_context.recent_data
    print(f"   Population: {recent.population:,}")
    print(f"   Development: {recent.development_level:.1f}/10")
    print(f"   Loyalty: {recent.loyalty:.1f}/100")
    print(f"   Stability: {recent.stability:.1f}/100")
    print(f"   Income: {recent.actual_income:.2f}")
    print(f"   Expenditure: {recent.actual_expenditure:.2f}")
    print(f"   Surplus: {recent.actual_surplus:.2f}")
    if recent.events:
        print(f"   Events: {len(recent.events)} event(s)")
        for event in recent.events:
            print(f"      - {event.name} (severity: {event.severity})")

    # Quarterly Summaries
    print(f"\n📊 Quarterly Summaries ({len(perception_context.quarterly_summaries)} quarters):")
    for i, q in enumerate(perception_context.quarterly_summaries):
        print(f"\n   Q{q.quarter} Year {q.year}:")
        print(f"      Avg Income: {q.avg_income:.2f}")
        print(f"      Total Surplus: {q.total_surplus:.2f}")
        print(f"      Income Trend: {q.income_trend.value}")
        print(f"      Loyalty Change: {q.loyalty_change:+.1f}")
        print(f"      Stability Change: {q.stability_change:+.1f}")
        if q.major_events:
            print(f"      Major Events: {', '.join(q.major_events[:3])}")
        print(f"      📝 Summary: {q.summary}")

    # Annual Summaries
    print(f"\n📊 Annual Summaries ({len(perception_context.annual_summaries)} years):")
    for a in perception_context.annual_summaries:
        print(f"\n   Year {a.year}:")
        print(f"      Total Income: {a.total_income:.2f}")
        print(f"      Total Surplus: {a.total_surplus:.2f}")
        print(f"      Loyalty Change: {a.loyalty_change:+.1f}")
        print(f"      Disasters: {a.disaster_count}, Rebellions: {a.rebellion_count}")
        print(f"      Performance: {a.performance_rating}")
        print(f"      📝 Summary: {a.summary}")

    # Critical Events
    print(f"\n🚨 Critical Events ({len(perception_context.critical_events)} events):")
    for event in perception_context.critical_events:
        status = "✓ Resolved" if event.is_resolved else "⚠️  Active"
        print(f"   [{status}] {event.event_name}")
        print(f"      Category: {event.event_category}")
        print(f"      Severity: {event.severity}")
        print(f"      Time: Month {event.month}, Year {event.year}")
        print(f"      Impact: {event.impact_description}")

    # Trend Analysis
    print(f"\n📈 Trend Analysis:")
    trends = perception_context.trends
    print(f"   Income: {trends.income_trend.value} ({trends.income_change_rate:+.1f}%)")
    print(f"   Expenditure: {trends.expenditure_trend.value} ({trends.expenditure_change_rate:+.1f}%)")
    print(f"   Loyalty: {trends.loyalty_trend.value} ({trends.loyalty_change_rate:+.1f})")
    print(f"   Stability: {trends.stability_trend.value} ({trends.stability_change_rate:+.1f})")
    print(f"   Risk Level: {trends.risk_level.value.upper()}")

    if trends.risk_factors:
        print(f"\n   ⚠️  Risk Factors:")
        for factor in trends.risk_factors:
            print(f"      - {factor}")

    if trends.opportunities:
        print(f"\n   💡 Opportunities:")
        for opp in trends.opportunities:
            print(f"      - {opp}")

    # 7. 输出JSON格式
    print("\n" + "="*70)
    print("JSON OUTPUT (for integration)")
    print("="*70)
    print(perception_context.model_dump_json(indent=2))

    print("\n" + "="*70)
    print("✓ PerceptionAgent test completed successfully!")
    print("="*70)

    # 8. 清理测试数据库
    print(f"\nCleaning up test database: {TEST_DB_PATH}")
    if os.path.exists(TEST_DB_PATH):
        os.remove(TEST_DB_PATH)
        print("✓ Test database removed")


if __name__ == "__main__":
    try:
        asyncio.run(test_perception_agent())
    except Exception as e:
        print(f"\n❌ Test failed with error: {e}")
        import traceback
        traceback.print_exc()

        # 清理测试数据库
        if os.path.exists(TEST_DB_PATH):
            os.remove(TEST_DB_PATH)
            print(f"\nCleaned up test database after error")
