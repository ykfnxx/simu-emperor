"""
Test PerceptionAgent with real LLM API

Usage:
1. Copy config.yaml.example to config.yaml
2. Set your Anthropic API key in config.yaml
3. Or set environment variable: export ANTHROPIC_API_KEY=your-key-here
4. Run: python tests/province/test_perception_agent_with_api.py

Command-line arguments:
    --config <path>    # Specify config file
    --api-key <key>    # Provide API key directly
    --mock             # Force mock mode
"""

import asyncio
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from db.database import Database
from agents.province.perception_agent import PerceptionAgent
from config_loader import setup_config_from_args


TEST_DB_PATH = "test_perception_api.db"


def setup_test_data(db: Database):
    """Create test data"""
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
            loyalty = 70.0 + month * 0.5
            stability = 65.0 + month * 0.3
        elif month == 6:
            loyalty = 45.0  # Rebellion
            stability = 40.0
        else:
            # Recovery period
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

        # Add events
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
    """Test PerceptionAgent with real LLM API"""
    print("="*70)
    print("Testing PerceptionAgent with Real LLM API")
    print("="*70)
    print()

    # 1. Load configuration
    config = setup_config_from_args()

    # Check if force mock mode
    force_mock = '--mock' in sys.argv
    if force_mock:
        print("⚠️  Force mock mode enabled")
        config.set('llm.mock_mode', True)

    # 2. Create test database
    if os.path.exists(TEST_DB_PATH):
        os.remove(TEST_DB_PATH)

    print("\n1. Creating test database...")
    db = Database(TEST_DB_PATH)

    # 3. Run migrations
    print("\n2. Running database migrations...")
    from db.migrations.add_province_agent_tables import migrate
    migrate(TEST_DB_PATH)

    # 4. Create test data
    print("\n3. Creating test data...")
    setup_test_data(db)

    # 5. Initialize PerceptionAgent (with config)
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

    # 6. Run perceive
    print("\n5. Running perceive() with LLM...")
    print("   (This may take a few seconds if using real API...)")

    perception_context = await perception_agent.perceive(
        province_id=1,
        current_month=13,
        current_year=2
    )

    # 7. Output results
    print("\n" + "="*70)
    print("RESULTS")
    print("="*70)

    # Show LLM-generated summaries
    print("\nLLM-Generated Summaries:")
    print("-" * 70)

    for q in perception_context.quarterly_summaries:
        print(f"\nQ{q.quarter} Year {q.year}:")
        print(f"  {q.summary}")

    for a in perception_context.annual_summaries:
        print(f"\nYear {a.year}:")
        print(f"  {a.summary}")

    # Show trend analysis
    print("\nTrend Analysis:")
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

    # Show critical events
    print(f"\nCritical Events: {len(perception_context.critical_events)}")
    for event in perception_context.critical_events:
        status = "Active" if not event.is_resolved else "Resolved"
        print(f"  [{status}] {event.event_name} (severity: {event.severity})")

    # 8. Save full JSON
    print("\n" + "="*70)
    print("Saving full results to JSON...")
    print("="*70)

    output_file = "perception_context_api_test.json"
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(perception_context.model_dump_json(indent=2))

    print(f"✓ Full results saved to: {output_file}")

    # 9. Cleanup
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

        # Cleanup
        if os.path.exists(TEST_DB_PATH):
            os.remove(TEST_DB_PATH)
            print(f"Cleaned up test database")

    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        import traceback
        traceback.print_exc()

        # Cleanup
        if os.path.exists(TEST_DB_PATH):
            os.remove(TEST_DB_PATH)
            print(f"\nCleaned up test database after error")
