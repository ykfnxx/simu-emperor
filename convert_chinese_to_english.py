"""
Chinese to English Converter for EU4 Strategy Game
Converts all Chinese text in source files to English while preserving functionality
"""

import os
import re
import sys

# Mapping of Chinese terms to English equivalents in UI
UI_MAPPING = {
    '国库': 'National Treasury',
    '国库余额': 'Treasury Balance',
    '国库流水': 'National Transaction History',
    '国库流水（最近10条）': 'National Transaction History (Last 10)',
    'Debug模式': 'Debug Mode',
    '活跃事件': 'Active Events',
    '预算执行情况': 'Budget Execution',
    '省份概况': 'Provincial Overview',
    '省份': 'Province',
    '忠诚度': 'Loyalty',
    '稳定度': 'Stability',
    '省库': 'Provincial Treasury',
    '省库流水': 'Provincial Transaction History',
    '省库流水（最近10条）': 'Provincial Transaction History (Last 10)',
    '省库余额': 'Provincial Balance',
    '状态': 'Status',
    '瞒报中': 'Concealing',
    '忠诚度低': 'Low Loyalty',
    '稳定度低': 'Low Stability',
    '正常': 'Normal',
    '操作菜单': 'Action Menu',
    '财务报告': 'Financial Report',
    '项目管理': 'Project Management',
    '切换Debug': 'Toggle Debug',
    '下一月': 'Next Month',
    '省级事件': 'Provincial Events',
    '全国状态': 'National Status',
    '资金管理': 'Fund Management',
    '预算执行': 'Budget Execution',
    '刷新': 'Refresh',
    '最后更新': 'Last Updated',
    '按Enter继续': 'Press Enter to continue',
    '按Enter返回仪表盘': 'Press Enter to return to dashboard',
    '收入': 'Income',
    '支出': 'Expenditure',
    '个月': 'months',
    '月份': 'Month',
    '财政': 'Financial',
    '异常': 'Abnormal',
    '中央预算': 'Central Budget',
    '预算总额': 'Total Budget',
    '已执行': 'Executed',
    '剩余': 'Remaining',
    '执行率': 'Execution Rate',
    '各省预算': 'Provincial Budgets',
    '日期': 'Date',
    '类型': 'Type',
    '金额': 'Amount',
    '余额': 'Balance',
    '描述': 'Description',
    '中央拨款给省份': 'Transfer to Province',
    '省份上缴给中央': 'Transfer to National',
    '设置各省盈余分配比例': 'Set Surplus Allocation Ratios',
    '查看分配比例': 'View Allocation Ratios',
    '查看国库流水': 'View National Transactions',
    '查看省库流水': 'View Provincial Transactions',
    '返回主菜单': 'Return to Main Menu',
    '请选择操作': 'Select operation',
    '分配比例': 'Allocation Ratios',
    '退出': 'Exit',
    '启用': 'Enabled',
    '关闭': 'Disabled',
    '全国': 'national',
    '省级': 'provincial',
    '省份编号': 'Province Number',
    '无效编号': 'Invalid number',
    '请输入数字': 'Please enter a number',
    '请输入省份编号': 'Enter province number',
    '取消': 'Cancel',
    '项目类型': 'Project Type',
    '农业改革': 'Agricultural Reform',
    '基础收入': 'Base Income',
    '基础设施建设': 'Infrastructure Development',
    '发展度': 'Development Level',
    '税收优惠': 'Tax Relief',
    '法律法规': 'Tax Relief',
    '治安强化': 'Security Enhancement',
    '项目编号': 'Project Number',
    '项目效果': 'Project Effect',
    '成本': 'Cost',
    '金币': 'gold',
    '中央财政': 'National Treasury',
    '省份财政': 'Provincial Treasury',
    '盈余分配': 'Surplus Allocation',
    '比例': 'Ratio',
    '上缴': 'Transfer to National',
    '留存': 'Keep Local',
    '分配': 'Allocation',
    '查看': 'View',
    '输入': 'Enter',
    '国库': 'National Treasury',
    '省库': 'Provincial Treasury',
    '当前': 'Current',
    '选择省份': 'Select Province',
    '省份': 'Province',
    '资金': 'Funds',
    '拨款': 'Allocation',
    '比例范围': 'Ratio Range',
    '直接回车': 'Press Enter',
    '保持当前': 'Keep Current',
    '回车': 'Enter',
    '设置': 'Set',
    '完成': 'Completed',
    '继续': 'Continue',
    '查看分配': 'View Allocation',
    '输入拨款': 'Enter Allocation',
    '请输入拨款金额': 'Please enter allocation amount',
    '请输入上缴金额': 'Please enter remittance amount',
    '请输入有效数字': 'Please enter a valid number',
    '金额必须为正数': 'Amount must be positive',
    '必须为正数': 'Must be positive',
    '有效数字': 'Valid number',
    '成功': 'Success',
    '失败': 'Failed',
    '已设置为': 'Set to',
    '输入数字': 'Enter a number',
    '无效选择': 'Invalid choice',
    '未能': 'Failed to',
    '选择': 'Select',
    '请输入': 'Please enter',
    '地区': 'Region',
    '国库余额': 'National Treasury Balance',
    '省份状态': 'Provincial Status',
    '数据': 'Data',
    '无效': 'Invalid',
    '编号': 'Number',
    '拨': 'Transfer',
    '款': 'Funds',
    '总额': 'Total',
    '预算': 'Budget',
    '中央': 'Central',
    '各省': 'Provincial',
    '执行': 'Execution',
    '率': 'Rate',
    '显示': 'Display',
    '选择操作': 'Choose operation',
    '记录': 'Record',
    '菜单': 'Menu',
    '主菜单': 'Main Menu',
    '项目': 'Project',
    '启动': 'Start',
    '返回': 'Return',
    '现在': 'Now',
    '确认': 'Confirm',
    '交易': 'Transaction',
    '历史': 'History',
    '结余转入': 'Surplus Rollover',
    '中央拨款': 'Central Allocation',
    '拨款给省': 'Transfer to Province',
    '盈余分配': 'Surplus Allocation',
    '上缴中央': 'Transfer to National',
    '收款': 'Receipt',
    '付款': 'Payment',
    '项': 'Item',
    '异常': 'Abnormal',
    '信号': 'Signal',
    '异常信号': 'Abnormal Signal',
    '瞒报了': 'concealed',
    '瞒报': 'Concealing',
    '官员': 'Official',
    '选择项目类型': 'Select Project Type',
    '成本的': 'costs',
    '开发度': 'development level',
    '按号': 'by number',
    '不在': 'not in',
    '范围': 'range',
    '请输入': 'Please enter',
    '选择功能': 'Select function',
    '功能': 'Function',
    '必须': 'must',
    '启动项目': 'Start project',
    '中央拨款给': 'Central transfer to',
    '浏览': 'Browse',
    '浏览流水': 'Browse transactions',
    '小结': 'Summary',
    '净变化': 'Net change',
    '从': 'From',
    '到': 'To',
    '合法': 'Valid',
    '暂时': 'Temporarily',
    '预算执行': 'Budget execution'
}

# Mapping for database field names and technical terms
def normalize_whitespace(text):
    """Normalize whitespace to handle multiple spaces"""
    return ' '.join(text.split())

def translate_chinese_content(content, file_path):
    """Translate Chinese content based on context"""
    original_content = content

    # Skip certain files that shouldn't be modified
    if '.venv/' in file_path or 'site-packages/' in file_path:
        return content

    # Replace Chinese text in comments and print statements
    for chinese, english in UI_MAPPING.items():
        # In print statements
        content = re.sub(r'print\([f\'"]([^\'"]*)' + re.escape(chinese) + r'([^\'"]*)[\'"]',
                        lambda m: 'print(' + m.group(1) + english + m.group(2) + ')', content)

        # In f-strings specifically
        content = re.sub(r'f[\'"]([^\'"]*)' + re.escape(chinese) + r'([^\'"]*)[\'"]',
                        lambda m: 'f\'' + m.group(1) + english + m.group(2) + '\'', content)

        # In regular strings
        content = re.sub(r'[\'"]' + re.escape(chinese) + r'[\'"]',
                        lambda m: '\'' + english + '\'', content)

        # In comments (Python syntax)
        content = re.sub(r'#\s*([^#\n\r]*)' + re.escape(chinese) + r'([^#\n\r]*)$',
                        lambda m: '# ' + m.group(1) + english + m.group(2), content, flags=re.MULTILINE)

        # For multi-line Chinese comments
        content = re.sub(r'#' + re.escape(chinese) + r'$',
                        '# ' + english, content, flags=re.MULTILINE)

    return content

def convert_files_in_directory(directory, extensions=['.py'], check_var_names=True):
    """Convert Chinese text to English in all files in a directory"""
    converted_files = []
    total_changes = 0

    for root, dirs, files in os.walk(directory):
        # Skip excluded directories
        if '.git' in root or '.venv' in root or 'site-packages' in root:
            continue

        for file in files:
            if any(file.endswith(ext) for ext in extensions):
                file_path = os.path.join(root, file)
                try:
                    # Read file
                    with open(file_path, 'r', encoding='utf-8') as f:
                        content = f.read()

                    # Check if file contains Chinese characters before conversion
                    import unicodedata
                    contains_chinese = any('\u4e00' <= c <= '\u9fff' for c in content)

                    if not contains_chinese:
                        continue

                    # Convert content
                    new_content = translate_chinese_content(content, file_path)

                    # Only write if content is different
                    if new_content != content:
                        with open(file_path, 'w', encoding='utf-8') as f:
                            f.write(new_content)

                        changes = sum(1 for i, (a, b) in enumerate(zip(content.split('\n'), new_content.split('\n')) if a != b)
                        converted_files.append((file_path, changes))
                        total_changes += changes

                    else:
                        print(f"No changes needed for {file_path}")

                except Exception as e:
                    print(f"Error processing {file_path}: {str(e)}")
                    continue

    return converted_files, total_changes

def main():
    """Main entry point"""
    print("Chinese to English Converter for EU4 Strategy Game")
    print("=" * 60)

    # Define directories to convert
    directories_to_convert = [
        'ui',
        'core',
        'agents',
        'events',
        'tests'
    ]

    all_converted = []
    total_changes = 0

    # Convert files in specified directories
    for directory in directories_to_convert:
        if os.path.exists(directory):
            print(f"\nConverting {directory}...")
            converted, changes = convert_files_in_directory(directory)
            print(f"  Found {len(converted)} files with changes, {changes} lines modified")
            all_converted.extend(converted)
            total_changes += changes
        else:
            print(f"  Directory {directory} not found, skipping...")

    print("\n" + "=" * 60)
    print(f"Conversion complete!")
    print(f"Total files modified: {len(all_converted)}")
    print(f"Total lines changed: {total_changes}")
    print("\nFiles with conversions:")
    for file_path, changes in all_converted:
        print(f"  {file_path} ({changes} changes)")

    # Generate a report
    report_path = 'conversion_report.txt'
    with open(report_path, 'w') as f:
        f.write("Chinese to English Conversion Report\n")
        f.write("=" * 60 + "\n\n")
        f.write(f"Total files converted: {len(all_converted)}\n")
        f.write(f"Total lines changed: {total_changes}\n\n")
        f.write("Detailed file changes:\n")
        f.write("-" * 60 + "\n")
        for file_path, changes in sorted(all_converted):
            f.write(f"{file_path}: {changes} changes\n")

    print(f"\nDetailed report saved to: {report_path}")

if __name__ == '__main__':
    if len(sys.argv) > 1 and '--do-convert' in sys.argv:
        main()
    else:
        print("This script will convert Chinese text to English in source files.")
        print("Run with --do-convert to proceed with conversion")
        print("\nUsage: python convert_chinese_to_english.py --do-convert")
