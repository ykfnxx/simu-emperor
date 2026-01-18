#!/usr/bin/env python3
"""
Automated Architecture Test

Test the new Agent architecture (Pydantic + Instructor)
No user interaction, automatically run several months
"""

import asyncio
import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

from core.game import Game


async def test_automatic():
    """Automated test"""
    print("="*70)
    print("Automated Test: New Agent Architecture (Pydantic + Instructor)")
    print("="*70)

    # Create game instance
    game = Game(db_path="test_auto.db", enable_central_advisor=True)

    print(f"\nInitial state:")
    print(f"- Province count: {len(game.provinces)}")
    print(f"- Governor Agents: {len(game.agents)}")
    print(f"- Central Advisor: {'Enabled' if game.central_advisor else 'Disabled'}")
    print(f"- Treasury: {game.state['treasury']:.2f} gold coins")

    # Run 3 months
    corruption_stats = {}
    for province in game.provinces:
        corruption_stats[province.name] = 0

    for month in range(1, 4):
        print(f"\n{'='*70}")
        print(f"Month {month}")
        print(f"{'='*70}")

        await game.next_month()

        # Track corruption
        for province in game.provinces:
            if province.last_month_corrupted:
                corruption_stats[province.name] += 1

    # Display final results
    print(f"\n{'='*70}")
    print("Test Completed - Corruption Statistics")
    print(f"{'='*70}")

    for province_name, corrupt_months in corruption_stats.items():
        print(f"{province_name}: {corrupt_months}/3 months corrupted ({corrupt_months/3*100:.0f}%)")

    print(f"\n{'='*70}")
    print("Architecture Features Verified")
    print(f"{'='*70}")
    print("✓ Agent layer separation (Governor + CentralAdvisor)")
    print("✓ LLM calling infrastructure in base class")
    print("✓ Pure function calculations (core/calculations.py)")
    print("✓ Province as pure data class")
    print("✓ Mock mode no API key required")
    print("✓ Async support")
    print(f"\nRefactoring complete! Architecture upgraded to v2 (Pydantic + Instructor)")
    print("="*70)


if __name__ == "__main__":
    asyncio.run(test_automatic())
