"""
Standalone test module for PerceptionAgent

This script will:
1. Create a test database file (test_perception.db)
2. Generate 12 months of test data
3. Run PerceptionAgent
4. Output detailed PerceptionContext results
5. Clean up test database
"""

import asyncio
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from db.database import Database
from agents.province.perception_agent import PerceptionAgent


TEST_DB_PATH = "test_perception.db"


def setup_test_data(db: Database):
    """Create test data: 12 months of historical data with events"""
    print("Setting up test data...")

    conn = db.get_connection()
    cursor = conn.cursor()

    # Delete existing data
    cursor.execute("DELETE FROM provinces")
    cursor.execute("DELETE FROM monthly_reports")
    cursor.execute("DELETE FROM events")
    cursor.execute("DELETE FROM special_events_index")

    # Insert test province
    cursor.execute("""
        INSERT INTO provinces (province_id, name, population, development_level,
                               loyalty, stability, base_income, corruption_tendency)
        VALUES (1, 'Test Province', 50000, 7.5, 70.0, 65.0, 800, 0.3)
    """)

    # Insert 12 months of historical data
    for month in range(1, 13):
        # Simulate gradual growth trend
        income = 800 + month * 10  # 800 → 920
        expenditure = 600 + month * 5  # 600 → 655

        # Loyalty and stability changes (rebellion in month 6)
        if month < 6:
            loyalty = 70.0 + month * 0.5  # Gradual growth to 73
            stability = 65.0 + month * 0.3  # Gradual growth to 66.8
        elif month == 6:
            loyalty = 45.0  # Sharp drop due to rebellion
            stability = 40.0
        else:
            # Recovery period
            loyalty = 45.0 + (month - 6) * 5  # 45 → 75
            stability = 40.0 + (month - 6) * 4.5  # 40 → 67.5

        # Calculate population and development changes
        population = 50000 + month * 100  # Gradual population growth
        development = 7.5 + month * 0.05  # Gradual improvement

        cursor.execute("""
            INSERT INTO monthly_reports (
                month, year, province_id,
                population, development_level, loyalty, stability,
                actual_income, actual_expenditure,
                reported_income, reported_expenditure,
                treasury_change
            ) VALUES (?, 1, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            month, 1,
            population, development, loyalty, stability,
            income, expenditure,
            income, expenditure,  # Assume honest reporting
            income - expenditure
        ))

        # Add events
        if month == 3:
            # Minor disaster
            cursor.execute("""
                INSERT INTO events (event_id, province_id, start_month, end_month,
                                   name, severity, event_type, description)
                VALUES (?, 1, ?, ?, 'Minor Flood', 0.4, 'disaster',
                        'Heavy rains caused minor flooding in agricultural areas')
            """, (f"evt_{month}", month, month))

        elif month == 6:
            # Rebellion
            cursor.execute("""
                INSERT INTO events (event_id, province_id, start_month, end_month,
                                   name, severity, event_type, description)
                VALUES (?, 1, ?, ?, 'Peasant Uprising', 0.7, 'rebellion',
                        'Large-scale unrest in northern territory over tax policies')
            """, (f"evt_{month}", month, month))

            # Index in special events
            cursor.execute("""
                INSERT INTO special_events_index (
                    event_id, province_id, event_category, month, year,
                    event_name, severity, impact_description, is_resolved
                ) VALUES (?, 1, 'rebellion', ?, 1, 'Peasant Uprising', 0.7,
                        'Large-scale unrest in northern territory', 0)
            """, (f"evt_{month}", month))

        elif month == 9:
            # Celebration event (boosts loyalty)
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
    """Test PerceptionAgent"""
    print("="*70)
    print("Testing PerceptionAgent")
    print("="*70)
    print()

    # Clean up old test database
    if os.path.exists(TEST_DB_PATH):
        os.remove(TEST_DB_PATH)
        print("Old test database removed")

    # 1. Create test database
    print("1. Creating test database...")
    db = Database(TEST_DB_PATH)
    print("   ✓ Base tables created")

    # 2. Create Province Agent tables
    print("\n2. Running Province Agent migrations...")
    from db.migrations.add_province_agent_tables import migrate
    migrate(TEST_DB_PATH)
    print("   ✓ Province Agent tables created")

    # 3. Create test data
    print("\n3. Creating test data...")
    setup_test_data(db)

    # 4. Initialize PerceptionAgent
    print("\n4. Initializing PerceptionAgent...")
    perception_agent = PerceptionAgent(
        agent_id="test_perception",
        config={
            'province_id': 1,
            'llm_config': {
                'enabled': True,
                'mock_mode': True  # Use mock mode, no API required
            }
        },
        db=db
    )
    print("✓ PerceptionAgent initialized")

    # 5. Run perceive method
    print("\n5. Running perceive() method...")
    print("   Analyzing data for month 13, year 2...")

    perception_context = await perception_agent.perceive(
        province_id=1,
        current_month=13,  # Month 1 of year 2
        current_year=2
    )

    # 6. Output results
    print("\n" + "="*70)
    print("PERCEPTION CONTEXT OUTPUT")
    print("="*70)

    print(f"\nLocation: {perception_context.province_name} (ID: {perception_context.province_id})")
    print(f"Current: Month {perception_context.current_month}, Year {perception_context.current_year}")
    print(f"Data Quality: {perception_context.data_quality}")

    # Warnings
    if perception_context.warnings:
        print(f"\nWarnings:")
        for warning in perception_context.warnings:
            print(f"   - {warning}")

    # Recent Data
    print(f"\nRecent Month Data (Month {perception_context.recent_data.month}):")
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
    print(f"\nQuarterly Summaries ({len(perception_context.quarterly_summaries)} quarters):")
    for i, q in enumerate(perception_context.quarterly_summaries):
        print(f"\n   Q{q.quarter} Year {q.year}:")
        print(f"      Avg Income: {q.avg_income:.2f}")
        print(f"      Total Surplus: {q.total_surplus:.2f}")
        print(f"      Income Trend: {q.income_trend.value}")
        print(f"      Loyalty Change: {q.loyalty_change:+.1f}")
        print(f"      Stability Change: {q.stability_change:+.1f}")
        if q.major_events:
            print(f"      Major Events: {', '.join(q.major_events[:3])}")
        print(f"      Summary: {q.summary}")

    # Annual Summaries
    print(f"\nAnnual Summaries ({len(perception_context.annual_summaries)} years):")
    for a in perception_context.annual_summaries:
        print(f"\n   Year {a.year}:")
        print(f"      Total Income: {a.total_income:.2f}")
        print(f"      Total Surplus: {a.total_surplus:.2f}")
        print(f"      Loyalty Change: {a.loyalty_change:+.1f}")
        print(f"      Disasters: {a.disaster_count}, Rebellions: {a.rebellion_count}")
        print(f"      Performance: {a.performance_rating}")
        print(f"      Summary: {a.summary}")

    # Critical Events
    print(f"\nCritical Events ({len(perception_context.critical_events)} events):")
    for event in perception_context.critical_events:
        status = "Resolved" if event.is_resolved else "Active"
        print(f"   [{status}] {event.event_name}")
        print(f"      Category: {event.event_category}")
        print(f"      Severity: {event.severity}")
        print(f"      Time: Month {event.month}, Year {event.year}")
        print(f"      Impact: {event.impact_description}")

    # Trend Analysis
    print(f"\nTrend Analysis:")
    trends = perception_context.trends
    print(f"   Income: {trends.income_trend.value} ({trends.income_change_rate:+.1f}%)")
    print(f"   Expenditure: {trends.expenditure_trend.value} ({trends.expenditure_change_rate:+.1f}%)")
    print(f"   Loyalty: {trends.loyalty_trend.value} ({trends.loyalty_change_rate:+.1f})")
    print(f"   Stability: {trends.stability_trend.value} ({trends.stability_change_rate:+.1f})")
    print(f"   Risk Level: {trends.risk_level.value.upper()}")

    if trends.risk_factors:
        print(f"\n   Risk Factors:")
        for factor in trends.risk_factors:
            print(f"      - {factor}")

    if trends.opportunities:
        print(f"\n   Opportunities:")
        for opp in trends.opportunities:
            print(f"      - {opp}")

    # 7. Output JSON format
    print("\n" + "="*70)
    print("JSON OUTPUT (for integration)")
    print("="*70)
    print(perception_context.model_dump_json(indent=2))

    print("\n" + "="*70)
    print("✓ PerceptionAgent test completed successfully!")
    print("="*70)

    # 8. Clean up test database
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

        # Clean up test database
        if os.path.exists(TEST_DB_PATH):
            os.remove(TEST_DB_PATH)
            print(f"\nCleaned up test database after error")
