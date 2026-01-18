"""
Convert Chinese comments in core files to English
"""

import os
import re

# Mapping of Chinese to English translations for comments
comment_translations = {
    # Common terms
    '获取': 'Get',
    '设置': 'Set',
    '更新': 'Update',
    '创建': 'Create',
    '检查': 'Check',
    '处理': 'Process',
    '计算': 'Calculate',
    # Budget terms
    '中央建议': 'Central recommendation',
    '默认2000金币/年': 'Default 2000 gold/year',
    '各省建议': 'Provincial recommendations',
    '默认100金币/年': 'Default 100 gold/year',
    '获取中央预算': 'Get central budget',
    '获取各省预算': 'Get provincial budgets',
    '将草稿状态的预算激活': 'Activate draft budgets',
    # Execution terms
    '盈余处理': 'Surplus processing',
    '亏损处理': 'Deficit processing',
    '获取分配比例': 'Get allocation ratio',
    '计算分配金额': 'Calculate allocation amount',
    '上缴国库': 'Transfer to national treasury',
    '入省库': 'Transfer to provincial treasury',
    '记录流水': 'Record transaction',
    '省份': 'Province',
    '上缴': 'Transfer to national',
    '盈余留存': 'Surplus retention',
    '月度亏损扣款': 'Monthly deficit deduction',
    '获取当前省库余额': 'Get current provincial balance',
    '从省库扣款': 'Deduct from provincial treasury',
    '检查省库是否不足': 'Check if provincial treasury insufficient',
    '处理超支': 'Process overdraft',
    '获取省份盈余分配比例': 'Get provincial surplus allocation ratio',
    '省份ID': 'Province ID',
    '分配比例': 'Allocation ratio',
    '上缴金额必须为正数': 'Transfer amount must be positive',
    '省库余额不足': 'Insufficient provincial balance',
    '当前': 'Current',
    '需要': 'Need',
    '省份': 'Province',
    '成功上缴': 'Successfully transferred',
    '获取所有省份的省库余额': 'Get all provincial balances',
    '初始金额': 'Initial amount',
    '设置初始余额': 'Set initial balance',
    '固定支出': 'Fixed expenditure',
    '调整后': 'Adjusted',
    '计算事件支出': 'Calculate event expenditure',
    '事件': 'Event',
    '支出金额': 'Expenditure amount',
    '获取扣款前余额': 'Get balance before deduction',
    '从国库扣款': 'Deduct from national treasury',
    '计算': 'Calculate',
    '中央月度支出': 'Central monthly expenditure',
    '基本': 'Basic',
    '事件': 'Events',
    '获取扣款后余额': 'Get balance after deduction',
    '检查国库是否不足': 'Check if national treasury insufficient',
    '处理中央超支': 'Process central overdraft',
    '创建中央财政危机事件': 'Create central fiscal crisis event',
    '中央财政出现严重赤字': 'Central finance has severe deficit',
    '持续': 'Lasts',
    '个月': 'months',
    '年度结余结转': 'Annual surplus carried forward',
    '年度': 'Year',
    '结转结果': 'Carryforward result',
    '计算中央年度结余': 'Calculate central annual surplus',
    '记录结余转入': 'Record surplus carried forward to',
    '计算各省年度结余': 'Calculate provincial annual surplus',
    '标记已完成预算': 'Mark completed budgets'
}

def translate_comments(file_path):
    """Translate Chinese comments in a file"""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            lines = f.readlines()

        modified = False
        new_lines = []

        for line in lines:
            new_line = line

            # Find and translate Chinese comments (lines with #)
            if '#' in line and not line.strip().startswith('# coding'):
                parts = line.split('#', 1)
                comment_part = parts[1]

                # Look for Chinese phrases and translate them
                for chinese, english in comment_translations.items():
                    if chinese in comment_part:
                        # Keep the # symbol and replace Chinese with English
                        new_comment = comment_part.replace(chinese, english)
                        new_line = parts[0] + '#' + new_comment
                        modified = True

            new_lines.append(new_line)

        if modified:
            with open(file_path, 'w', encoding='utf-8') as f:
                f.writelines(new_lines)
            print(f'Updated: {file_path}')
            return True
        else:
            print(f'No changes: {file_path}')
            return False

    except Exception as e:
        print(f'Error processing {file_path}: {e}')
        return False

def main():
    # Define target files
    core_files = [
        'core/budget_system.py',
        'core/budget_execution.py',
        'core/treasury_system.py',
        'core/calculations.py',
        'core/province.py',
        'core/project.py',
        'core/game.py',
    ]

    # Process core files
    for file_path in core_files:
        if os.path.exists(file_path):
            translate_comments(file_path)
        else:
            print(f'File not found: {file_path}')

if __name__ == '__main__':
    main()
