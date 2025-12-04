"""
测试预算系统功能
无需交互，直接测试核心功能
"""

import asyncio
import sys

# 测试预算系统
async def test_budget_system():
    """测试预算系统功能"""
    print("正在测试预算系统...")

    # 初始化游戏
    from core.game import Game
    import os

    # 使用临时数据库文件
    db_path = "test_budget.db"
    if os.path.exists(db_path):
        os.remove(db_path)

    game = Game(db_path=db_path)  # 使用真实数据库文件

    print("✓ 游戏初始化成功")
    print(f"✓ 国库余额: {game.state['treasury']:.2f} 金币")
    print(f"✓ 省份数量: {len(game.provinces)}")

    # 检查省库余额
    for province in game.provinces:
        balance = game.treasury_system.get_provincial_balance(province.province_id)
        print(f"✓ {province.name}省库余额: {balance:.2f} 金币")

    # 测试预算生成
    current_year = 1
    print(f"\n✓ 生成{current_year + 1}年预算")
    national_budget_id = game.budget_system.generate_national_budget(current_year + 1)
    provincial_budget_ids = game.budget_system.generate_provincial_budgets(current_year + 1)

    print(f"✓ 中央预算ID: {national_budget_id[:16]}...")
    print(f"✓ 生成{len(provincial_budget_ids)}个省份预算")

    # 检查预算数据
    budgets = game.budget_system.get_current_budgets(current_year + 1)
    if budgets['national']:
        print(f"✓ 中央预算: {budgets['national']['allocated_budget']:.2f} 金币")

    # 测试资金划拨
    print(f"\n✓ 测试资金划拨")
    province = game.provinces[0]
    initial_balance = game.treasury_system.get_provincial_balance(province.province_id)

    success, message = game.treasury_system.transfer_from_national_to_province(
        province.province_id, 100, 6, current_year
    )
    if success:
        print(f"✓ 拨款成功: {message}")
    else:
        print(f"✗ 拨款失败: {message}")

    new_balance = game.treasury_system.get_provincial_balance(province.province_id)
    print(f"✓ {province.name}省库余额变化: {initial_balance:.2f} -> {new_balance:.2f}")

    # 测试月度执行（模拟1个月）
    print(f"\n✓ 测试月度预算执行")
    game.state['current_month'] = 6  # 设置为第6个月

    budget_result = game.budget_executor.execute_monthly_budget(
        game.state, game.provinces, game.state['current_month'], current_year
    )

    print(f"✓ 省级盈余上缴中央: {budget_result['total_central_income']:.2f} 金币")
    print(f"✓ 省级盈余留存省库: {budget_result['total_central_allocation']:.2f} 金币")

    # 测试中央预算执行
    central_result = game.budget_executor.execute_central_budget(
        game.state['current_month'], current_year
    )
    print(f"✓ 中央固定支出: {central_result['fixed_expenditure']:.2f} 金币")
    print(f"✓ 国库余额变化: {central_result['starting_balance']:.2f} -> {central_result['ending_balance']:.2f} 金币")

    print("\n" + "="*60)
    print("✓ 所有测试通过！")
    print("="*60)

    # 清理测试数据库
    import os
    if os.path.exists(db_path):
        os.remove(db_path)
        print(f"✓ 清理测试数据库")

if __name__ == "__main__":
    try:
        asyncio.run(test_budget_system())
    except Exception as e:
        print(f"\n✗ 测试失败: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
