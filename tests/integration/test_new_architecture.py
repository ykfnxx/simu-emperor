#!/usr/bin/env python3
"""
New Architecture Test

Test the new Agent architecture
"""

import asyncio
import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

from core.game import Game


async def test_game_with_agents():
    """Test game with Agents"""
    print("="*70)
    print("Testing New Agent Architecture")
    print("="*70)

    # Create game instance (with central advisor enabled)
    game = Game(db_path="test_new_arch.db", enable_central_advisor=True)

    print(f"\nInitial state:")
    print(f"- Province count: {len(game.provinces)}")
    print(f"- Governor Agents: {len(game.agents)}")
    print(f"- Central Advisor: {'Enabled' if game.central_advisor else 'Disabled'}")
    print(f"- Treasury: {game.state['treasury']:.2f} gold coins")

    # Run a few months
    for month in range(1, 4):
        print(f"\n{'='*70}")
        print(f"Month {month}")
        print(f"{'='*70}")

        # Move to next month (async)
        await game.next_month()

        # Display each province status
        print("\n[Province Status]")
        for province in game.provinces:
            status = "🔴 Hid report" if province.last_month_corrupted else "✅ Honest"
            diff = province.actual_income - province.reported_income
            print(f"  {province.name}: {status}")
            print(f"    Income: {province.reported_income:.0f}/{province.actual_income:.0f} "
                  f"({diff:+.0f}) | Honesty: {province.loyalty:.0f}")

        input("\nPress Enter to continue...")

    print("\n" + "="*70)
    print("Test completed!")
    print("="*70)


if __name__ == "__main__":
    # Run async test
    asyncio.run(test_game_with_agents())
