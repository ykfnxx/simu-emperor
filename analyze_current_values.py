"""
分析当前数值系统
评估收入和支出的合理性
"""

from db.database import Database
from core.calculations import calculate_province_income, calculate_province_expenditure, generate_random_factor

# 创建数据库实例
db = Database("game.db")
conn = db.get_connection()
cursor = conn.cursor()

# 获取省份数据
cursor.execute("""
    SELECT province_id, name, population, development_level, stability, base_income
    FROM provinces
""")
provinces = cursor.fetchall()

print("="*80)
print("当前数值系统分析")
print("="*80)

print("\n省份基础数据：")
print(f"{'省份':<10} {'人口':<8} {'发展度':<8} {'稳定度':<8} {'基础收入':<10}")
print("-"*50)

for province in provinces:
    province_id, name, population, dev_level, stability, base_income = province
    print(f"{name:<10} {population:<8} {dev_level:<8.1f} {stability:<8.1f} {base_income:<10.1f}")

print("\n" + "="*80)
print("月度收支计算（使用当前公式）")
print("="*80)

print("\n收入公式: (人口/1000) × 发展度 × 15 × (稳定度/100) × 随机因子(0.9-1.1)")
print("支出公式: (人口/1000) × 8 × (2 - 稳定度/100)")

print("\n计算结果：")
print(f"{'省份':<10} {'收入':<10} {'支出':<10} {'盈余':<10} {'收入/支出比':<12}")
print("-"*70)

total_income = 0
total_expenditure = 0

for province in provinces:
    province_id, name, population, dev_level, stability, base_income = province

    # 计算收入和支出（使用当前公式）
    random_factor = generate_random_factor()
    income = calculate_province_income(population, dev_level, stability, random_factor=random_factor)
    expenditure = calculate_province_expenditure(population, stability)
    surplus = income - expenditure

    total_income += income
    total_expenditure += expenditure

    ratio = income / expenditure if expenditure > 0 else 999

    print(f"{name:<10} {income:<10.2f} {expenditure:<10.2f} {surplus:<10.2f} {ratio:<12.2f}")

print("-"*70)
print(f"{'总计':<10} {total_income:<10.2f} {total_expenditure:<10.2f} {total_income-total_expenditure:<10.2f}")

print("\n" + "="*80)
print("问题分析")
print("="*80)

print(f"\n1. 总收入: {total_income:.2f} 金币/月")
print(f"2. 总支出: {total_expenditure:.2f} 金币/月")
print(f"3. 总盈余: {total_income-total_expenditure:.2f} 金币/月")
print(f"4. 平均收入支出比: {total_income/total_expenditure:.2f}")

print("\n5. 问题识别:")
print("   - 收入远高于支出，盈余过大")
print("   - 经济系统缺乏挑战性")
print("   - 中央国库增长过快")

# 关闭连接
conn.close()
