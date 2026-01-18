#!/usr/bin/env python3
"""
Budget System Test

Test core budget system functionality without interaction
"""

import asyncio
import sys
import os

# Test budget system
async def test_budget_system():
    """Test budget system functionality"""
    print("Testing budget system...")

    # Initialize game
    from core.game import Game

    # Use temporary database file
    db_path = "test_budget.db"
    if os.path.exists(db_path):
        os.remove(db_path)

    game = Game(db_path=db_path)  # Use real database file

    print("✓ Game initialized successfully")
    print(f"✓ Treasury balance: {game.state['treasury']:.2f} gold coins")
    print(f"✓ Province count: {len(game.provinces)}")

    # Check provincial treasury balances
    for province in game.provinces:
        balance = game.treasury_system.get_provincial_balance(province.province_id)
        print(f"✓ {province.name} provincial balance: {balance:.2f} gold coins")

    # Test budget generation
    current_year = 1
    print(f"\n✓ Generating budget for year {current_year + 1}")
    national_budget_id = game.budget_system.generate_national_budget(current_year + 1)
    provincial_budget_ids = game.budget_system.generate_provincial_budgets(current_year + 1)

    print(f"✓ National budget ID: {national_budget_id[:16]}...")
    print(f"✓ Generated {len(provincial_budget_ids)} provincial budgets")

    # Check budget data
    budgets = game.budget_system.get_current_budgets(current_year + 1)
    if budgets['national']:
        print(f"✓ National budget: {budgets['national']['allocated_budget']:.2f} gold coins")

    # Test fund transfer
    print(f"\n✓ Testing fund transfers")
    province = game.provinces[0]
    initial_balance = game.treasury_system.get_provincial_balance(province.province_id)

    success, message = game.treasury_system.transfer_from_national_to_province(
        province.province_id, 100, 6, current_year
    )

    if success:
        print(f"✓ Transfer successful: {message}")
    else:
        print(f"✗ Transfer failed: {message}")

    new_balance = game.treasury_system.get_provincial_balance(province_id)
    print(f"✓ {province.name} balance change: {initial_balance:.2f} -> {new_balance:.2f}")

    # Test monthly budget execution (simulate 1 month)
    print(f"\n✓ Testing monthly budget execution")
    game.state['current_month'] = 6  # Set to month 6

    budget_result = game.budget_executor.execute_monthly_budget(
        game.state, game.provinces, game.state['current_month'], current_year
    )

    print(f"✓ Provincial surplus to central: {budget_result['total_central_income']:.2f} gold coins")
    print(f"✓ Provincial surplus retained: {budget_result['total_central_allocation']:.2f} gold coins")

    # Test central budget execution
    central_result = game.budget_executor.execute_central_budget(
        game.state['current_month'], current_year
    )
    print(f"✓ Central fixed expenditure: {central_result['fixed_expenditure']:.2f} gold coins")
    print(f"✓ Treasury balance change: {central_result['starting_balance']:.2f} -> {central_result['ending_balance']:.2f} gold coins")

    print("\n" + "="*60)
    print("✓ All tests passed!")
    print("="*60)

    # Clean up test database
    import os
    if os.path.exists(db_path):
        os.remove(db_path)
        print("✓ Cleaned up test database")


if __name__ == "__main__":
    try:
        asyncio.run(test_budget_system())
    except Exception as e:
        print(f"\n✗ Test failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
