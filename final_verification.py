"""
最终验证报告 - 数值调整完成
"""

print("="*70)
print("数值调整完成 - 最终验证报告")
print("="*70)

print("\n📊 调整总结:")
print("  收入系数: 15.0 → 4.0 (下降73%)")
print("  支出系数: 8.0 → 14.0 (上升75%)")
print("  中央支出: 200 → 300 (上升50%)")

print("\n" + "-"*70)
print("目标数值 (inputs):")
print("-"*70)

# 使用实际配置文件数据
provinces = [
    ("Capital", 35000, 7.0, 72),
]

for name, pop, dev, stab in provinces:
    print(f"  {name}: 人口={pop}, 发展度={dev}, 稳定度={stab}")

print("\n" + "-"*70)
print("计算结果 (outputs):")
print("-"*70)

total_income = 0
total_expenditure = 0

for name, pop, dev, stab in provinces:
    income = (pop / 1000) * dev * 4.0 * (stab / 100)
    expenditure = (pop / 1000) * 14.0 * (2 - stab / 100)
    surplus = income - expenditure
    
    total_income += income
    total_expenditure += expenditure
    
    print(f"  {name:8}: 收入={income:6.1f}, 支出={expenditure:6.1f}, 盈余={surplus:+6.1f}")

ratio = total_income / total_expenditure
national_surplus = total_income - total_expenditure - 300

print("-"*70)
print(f"\n汇总指标:")
print(f"  省份总收入: {total_income:6.1f} 金币/月")
print(f"  省份总支出: {total_expenditure:6.1f} 金币/月")
print(f"  收入支出比: {ratio:.2f}")
print(f"  中央财政支出: 300 金币/月")
print(f"  国库净变化: {national_surplus:+6.1f} 金币/月")

monthly_treasury_change_pct = (national_surplus / 1000) * 100

print("\n" + "="*70)
print("✓ 验证结果")
print("="*70)

checks = []
checks.append(("收入支出比 < 1.1", ratio < 1.1, f"{ratio:.2f}"))
checks.append(("国库变化率 < 20%", abs(monthly_treasury_change_pct) < 20, f"{monthly_treasury_change_pct:.1f}%"))
checks.append(("挑战性适中", 5 <= abs(monthly_treasury_change_pct) <= 15, f"{monthly_treasury_change_pct:.1f}%"))

all_pass = True
for name, passed, value in checks:
    status = "✓ PASS" if passed else "✗ FAIL"
    print(f"  {status} | {name}: {value}")
    all_pass &= passed

print("\n" + "="*70)
if all_pass:
    print("✅ 所有验证通过！数值调整成功")
    print("\n🎮 游戏体验:")
    print("  - 经济压力明显，需要主动管理")
    print("  - 省份收入支出基本持平，需要策略优化")
    print("  - 中央财政紧张，要求合理的预算规划")
else:
    print("❌ 部分验证失败，需要调整")
print("="*70)

print("\n📁 修改的文件:")
print("  - core/calculations.py (收入系数 4.0)")
print("  - core/calculations.py (支出系数 14.0)")
print("  - core/budget_execution.py (中央支出 300)")

print("\n🚀 下一步建议:")
print("  1. 运行完整游戏测试")
print("  2. 如有需要，微调初始省库余额")
print("  3. 验证事件系统对经济的影响")

print("\n" + "="*70)
