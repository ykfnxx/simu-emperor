"""
使用真实LLM API测试PerceptionAgent

使用方法：
1. 复制 config.yaml.example 为 config.yaml
2. 在 config.yaml 中设置你的 Anthropic API key
3. 或者设置环境变量：export ANTHROPIC_API_KEY=your-key-here
4. 运行脚本：python test_perception_agent_with_api.py

命令行参数：
    --config <path>    # 指定配置文件
    --api-key <key>    # 直接提供API key
    --mock             # 强制使用mock模式
"""

import asyncio
import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

from db.database import Database
from agents.province.perception_agent import PerceptionAgent
from config_loader import setup_config_from_args


TEST_DB_PATH = "test_perception_api.db"


def setup_test_data(db: Database):
    """创建测试数据"""
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
            loyalty = 70.0 + month * 0.5
            stability = 65.0 + month * 0.3
        elif month == 6:
            loyalty = 45.0  # 叛乱
            stability = 40.0
        else:
            # 恢复期
            loyalty = 45.0 + (month - 6) * 5
            stability = 40.0 + (month - 6) * 4.5

        cursor.execute("""
            INSERT INTO monthly_reports (
                month, year, province_id,
                actual_income, actual_expenditure,
                reported_income, reported_expenditure,
                treasury_change
            ) VALUES (?, 1, ?, ?, ?, ?, ?, ?)
        """, (month, 1, income, expenditure, income, expenditure, income - expenditure))

        # 添加事件
        if month == 3:
            cursor.execute("""
                INSERT INTO events (event_id, province_id, start_month, end_month,
                                   name, severity, event_type, description)
                VALUES (?, 1, ?, ?, 'Minor Flood', 0.4, 'disaster',
                        'Heavy rains caused minor flooding')
            """, (f"evt_{month}", month, month))

        elif month == 6:
            cursor.execute("""
                INSERT INTO events (event_id, province_id, start_month, end_month,
                                   name, severity, event_type, description)
                VALUES (?, 1, ?, ?, 'Peasant Uprising', 0.7, 'rebellion',
                        'Large-scale unrest over tax policies')
            """, (f"evt_{month}", month, month))

            cursor.execute("""
                INSERT INTO special_events_index (
                    event_id, province_id, event_category, month, year,
                    event_name, severity, impact_description, is_resolved
                ) VALUES (?, 1, 'rebellion', ?, 1, 'Peasant Uprising', 0.7,
                        'Large-scale unrest', 0)
            """, (f"evt_{month}", month))

        elif month == 9:
            cursor.execute("""
                INSERT INTO events (event_id, province_id, start_month, end_month,
                                   name, severity, event_type, description)
                VALUES (?, 1, ?, ?, 'Harvest Festival', 0.2, 'celebration',
                        'Annual celebration boosted morale')
            """, (f"evt_{month}", month, month))

    conn.commit()
    conn.close()

    print("✓ Created 12 months of test data")


async def test_with_real_api():
    """使用真实API测试PerceptionAgent"""
    print("="*70)
    print("Testing PerceptionAgent with Real LLM API")
    print("="*70)
    print()

    # 1. 加载配置
    config = setup_config_from_args()

    # 检查是否强制mock模式
    force_mock = '--mock' in sys.argv
    if force_mock:
        print("⚠️  Force mock mode enabled")
        config.set('llm.mock_mode', True)

    # 2. 创建测试数据库
    if os.path.exists(TEST_DB_PATH):
        os.remove(TEST_DB_PATH)

    print("\n1. Creating test database...")
    db = Database(TEST_DB_PATH)

    # 3. 运行迁移
    print("\n2. Running database migrations...")
    from db.migrations.add_province_agent_tables import migrate
    migrate(TEST_DB_PATH)

    # 4. 创建测试数据
    print("\n3. Creating test data...")
    setup_test_data(db)

    # 5. 初始化PerceptionAgent（使用配置）
    print("\n4. Initializing PerceptionAgent...")
    llm_config = config.get_llm_config()

    print(f"   LLM enabled: {llm_config['enabled']}")
    print(f"   LLM model: {llm_config['model']}")
    print(f"   Mock mode: {llm_config['mock_mode']}")

    perception_agent = PerceptionAgent(
        agent_id="test_perception",
        config={
            'province_id': 1,
            'llm_config': llm_config
        },
        db=db
    )

    # 6. 运行perceive
    print("\n5. Running perceive() with LLM...")
    print("   (This may take a few seconds if using real API...)")

    perception_context = await perception_agent.perceive(
        province_id=1,
        current_month=13,
        current_year=2
    )

    # 7. 输出结果
    print("\n" + "="*70)
    print("RESULTS")
    print("="*70)

    # 显示LLM生成的摘要
    print("\n📝 LLM-Generated Summaries:")
    print("-" * 70)

    for q in perception_context.quarterly_summaries:
        print(f"\nQ{q.quarter} Year {q.year}:")
        print(f"  {q.summary}")

    for a in perception_context.annual_summaries:
        print(f"\nYear {a.year}:")
        print(f"  {a.summary}")

    # 显示趋势分析
    print("\n📈 Trend Analysis:")
    print("-" * 70)
    trends = perception_context.trends
    print(f"Income: {trends.income_trend.value} ({trends.income_change_rate:+.1f}%)")
    print(f"Loyalty: {trends.loyalty_trend.value} ({trends.loyalty_change_rate:+.1f}%)")
    print(f"Stability: {trends.stability_trend.value} ({trends.stability_change_rate:+.1f}%)")
    print(f"Risk Level: {trends.risk_level.value}")

    if trends.risk_factors:
        print("\nRisk Factors:")
        for factor in trends.risk_factors:
            print(f"  - {factor}")

    if trends.opportunities:
        print("\nOpportunities:")
        for opp in trends.opportunities:
            print(f"  - {opp}")

    # 显示关键事件
    print(f"\n🚨 Critical Events: {len(perception_context.critical_events)}")
    for event in perception_context.critical_events:
        status = "Active" if not event.is_resolved else "Resolved"
        print(f"  [{status}] {event.event_name} (severity: {event.severity})")

    # 8. 保存完整JSON
    print("\n" + "="*70)
    print("Saving full results to JSON...")
    print("="*70)

    output_file = "perception_context_api_test.json"
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(perception_context.model_dump_json(indent=2))

    print(f"✓ Full results saved to: {output_file}")

    # 9. 清理
    print(f"\nCleaning up test database: {TEST_DB_PATH}")
    if os.path.exists(TEST_DB_PATH):
        os.remove(TEST_DB_PATH)
        print("✓ Test database removed")

    print("\n" + "="*70)
    print("✓ Test completed successfully!")
    print("="*70)


if __name__ == "__main__":
    try:
        asyncio.run(test_with_real_api())
    except KeyboardInterrupt:
        print("\n\n⚠️  Test interrupted by user")

        # 清理
        if os.path.exists(TEST_DB_PATH):
            os.remove(TEST_DB_PATH)
            print(f"Cleaned up test database")

    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        import traceback
        traceback.print_exc()

        # 清理
        if os.path.exists(TEST_DB_PATH):
            os.remove(TEST_DB_PATH)
            print(f"\nCleaned up test database after error")
