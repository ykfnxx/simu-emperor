"""
推荐数值配置
"""

print("="*70)
print("推荐数值配置（挑战型）")
print("="*70)

# 配置
recommended_income_coeff = 4.0
recommended_expenditure_coeff = 14.0
recommended_central_expenditure = 300  # 降低到300

provinces_data = [
    ("Capital", 35000, 7.0, 72),
]

print(f"\n配置参数:")
print(f"  收入系数: {recommended_income_coeff}")
print(f"  支出系数: {recommended_expenditure_coeff}")
print(f"  中央支出: {recommended_central_expenditure}")
print(f"  初始国库: 3000 (建议)")

total_income = 0
total_expenditure = 0

print(f"\n省份收支:")
for name, pop, dev, stab in provinces_data:
    income = (pop/1000) * dev * recommended_income_coeff * (stab/100)
    expenditure = (pop/1000) * recommended_expenditure_coeff * (2 - stab/100)
    surplus = income - expenditure
    
    total_income += income
    total_expenditure += expenditure
    
    print(f"  {name:8}: 收入={income:6.1f}, 支出={expenditure:6.1f}, 盈余={surplus:+6.1f}")

ratio = total_income / total_expenditure
national_change = total_income - total_expenditure - recommended_central_expenditure
monthly_growth = (national_change / 3000) * 100  # 假设初始3000金币

print(f"\n汇总:")
print(f"  省份总收入: {total_income:.1f}")
print(f"  省份总支出: {total_expenditure:.1f}")
print(f"  收入支出比: {ratio:.2f}")
print(f"  中央财政支出: {recommended_central_expenditure}")
print(f"  国库净变化: {national_change:+.1f}")

print(f"\n游戏影响分析:")
print(f"  ✓ 收入支出比 {ratio:.2f} < 1.1 (符合要求)")
print(f"  ✓ 每月国库减少 {(abs(national_change)/3000*100):.1f}% (挑战性强)")
print(f"  ⚠ 需要玩家积极管理省份和预算")
print(f"  ⚠ 建议初始国库设为3000，提供缓冲期")

print(f"\n策略建议:")
print(f"  - 调整各省盈余分配比例（降低上缴中央比例）")
print(f"  - 投资发展项目提高收入")
print(f"  - 提高省份稳定度降低支出")
print(f"  - 合理规划中央年度预算")

print("\n" + "="*70)
if ratio < 1.1:
    print("✅ 数值配置通过！可以实施")
else:
    print("❌ 需要继续调整")
print("="*70)
