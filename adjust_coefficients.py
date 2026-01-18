"""
重新计算系数以达到目标
"""

print("="*70)
print("系数微调 - 第二次迭代")
print("="*70)

# 当前数据（使用5.0/14.0系数）
provinces = [
    {"name": "Capital", "population": 35000, "dev": 7.0, "stability": 72},
]

# 计算当前值（5.0系数）
total_expenditure = sum((p['population']/1000) * 14.0 * (2.0 - p['stability']/100) for p in provinces)
total_income_5 = sum((p['population']/1000) * p['dev'] * 5.0 * (p['stability']/100) for p in provinces)

current_ratio = total_income_5 / total_expenditure
target_ratio = 1.08  # 目标比值，留出缓冲

# 计算新系数
new_coefficient = (target_ratio * total_expenditure) / sum((p['population']/1000) * p['dev'] * (p['stability']/100) for p in provinces)

print(f"\n当前状态:")
print(f"  收入: {total_income_5:.1f} (系数5.0)")
print(f"  支出: {total_expenditure:.1f}")
print(f"  比值: {current_ratio:.2f}")
print(f"  目标比值: {target_ratio}")
print(f"\n推荐新系数: {new_coefficient:.2f}")

# 使用新系数计算
income_4 = sum((p['population']/1000) * p['dev'] * 4.0 * (p['stability']/100) for p in provinces)
income_35 = sum((p['population']/1000) * p['dev'] * 3.5 * (p['stability']/100) for p in provinces)

print(f"\n测试不同系数:")
for coeff, inc in [(5.0, total_income_5), (4.0, income_4), (3.5, income_35)]:
    ratio = inc / total_expenditure
    print(f"  系数{coeff:.1f}: 收入={inc:.1f}, 比值={ratio:.2f}")

# 推荐中央支出
for central in [300, 350, 400, 450]:
    surplus = income_4 - total_expenditure - central
    growth = (surplus / 1000) * 100
    print(f"\n中央支出={central}: 国库变化={surplus:.1f}, 增长率={growth:.1f}%")

print("\n" + "="*70)
print("推荐配置:")
print("  收入系数: 4.0")
print("  支出系数: 14.0") 
print("  中央支出: 350")
print("="*70)
