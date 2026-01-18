"""
手动验证新公式计算
"""

print("="*70)
print("数值计算公式验证 (调整后的新系数)")
print("="*70)

# 省份数据
provinces = [
    {"name": "Capital", "population": 35000, "dev": 7.0, "stability": 72},
]

print("\n使用新系数:")
print("  收入系数: 5.0 (原15.0)")
print("  支出系数: 14.0 (原8.0)")
print("  中央支出: 450 (原200)")

print("\n" + "-"*70)
print(f"{'省份':<8} {'人口':<8} {'发展度':<8} {'稳定度':<8}")
print("-"*70)

for p in provinces:
    print(f"{p['name']:<8} {p['population']:<8} {p['dev']:<8.1f} {p['stability']:<8.0f}")

print("\n" + "="*70)
print("月度收支计算结果")
print("="*70)

total_income = 0
total_expenditure = 0

for p in provinces:
    # 收入公式: (人口/1000) × 发展度 × 5 × (稳定度/100)
    income = (p['population'] / 1000.0) * p['dev'] * 5.0 * (p['stability'] / 100.0)
    
    # 支出公式: (人口/1000) × 14 × (2 - 稳定度/100)
    expenditure = (p['population'] / 1000.0) * 14.0 * (2.0 - p['stability'] / 100.0)
    
    surplus = income - expenditure
    total_income += income
    total_expenditure += expenditure
    
    print(f"{p['name']:<8}: 收入={income:6.1f}, 支出={expenditure:6.1f}, 盈余={surplus:+6.1f}")

print("-"*70)
ratio = total_income / total_expenditure
national_surplus = total_income - total_expenditure - 450  # 减去中央支出

print(f"\n总计:")
print(f"  省份总收入: {total_income:6.1f}")
print(f"  省份总支出: {total_expenditure:6.1f}")
print(f"  收入支出比: {ratio:.2f}")
print(f"  中央财政支出: 450.0")
print(f"  国库净变化: {national_surplus:+6.1f}")

print("\n" + "="*70)
print("验证标准")
print("="*70)

print(f"\n✓ 收入支出比 < 1.1: {'PASS' if ratio < 1.1 else 'FAIL'} ({ratio:.2f})")
print(f"✓ 国库适度增长/减少: {'PASS' if abs(national_surplus) < 200 else 'FAIL'} ({abs(national_surplus):.1f})")

expected_treasury_growth = (national_surplus / 1000) * 100  # 初始1000金币
print(f"✓ 国库增长率 < 20%: {'PASS' if abs(expected_treasury_growth) < 20 else 'FAIL'} ({expected_treasury_growth:.1f}%)")

if ratio < 1.1 and abs(national_surplus) < 200:
    print("\n✅ 数值调整成功！")
else:
    print("\n❌ 需要进一步调整")

print("="*70)
