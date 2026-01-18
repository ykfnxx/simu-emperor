"""
Verification script for Chinese to English conversion
Tests that functionality remains intact after conversion
"""

import sys
import os

def verify_data_structures():
    """Verify that data structures are intact"""
    print("Testing data structures...")

    # Test Province class
    from core.province import Province

    province_data = {
        'province_id': 1,
        'name': 'Test Province',
        'population': 1000000,
        'development_level': 3.0,
        'loyalty': 75,
        'stability': 80,
        'base_income': 100.0,
        'actual_income': 110.0,
        'actual_expenditure': 95.0,
        'adjusted_income': 110.0,
        'adjusted_expenditure': 95.0,
        'reported_income': 105.0,
        'reported_expenditure': 100.0
    }

    province = Province(province_data)
    assert province.province_id == 1
    assert province.name == 'Test Province'
    assert hasattr(province, 'actual_income')
    assert hasattr(province, 'reported_income')

    dict_result = province.to_dict()
    assert 'actual_income' in dict_result
    assert 'reported_income' in dict_result

    print("✓ Province class works correctly")

    # Test Project class
    from core.project import Project

    project = Project(1, 'agriculture', 1)
    assert project.cost == 50
    assert project.project_type == 'agriculture'

    project_dict = project.to_dict()
    assert 'project_type' in project_dict

    print("✓ Project class works correctly")

    return True

def verify_cli_integration():
    """Verify CLI integration"""
    print("\nTesting CLI integration...")

    # Only test import, as CLI requires game setup
    try:
        from ui.cli import GameCLI
        from ui.cli_realtime import RealtimeGameCLI
        print("✓ CLI modules imported successfully")
        return True
    except Exception as e:
        print(f"✗ CLI import failed: {e}")
        return False

def verify_core_modules():
    """Verify core modules can be imported"""
    print("\nTesting core module imports...")

    try:
        from core.game import Game
        from core.calculations import calculate_province_income, apply_event_effects
        from core.budget_system import BudgetSystem
        from core.budget_execution import BudgetExecution
        from core.treasury_system import TreasurySystem

        print("✓ All core modules imported successfully")
        return True
    except Exception as e:
        print(f"✗ Core module import failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def verify_no_chinese_in_data():
    """Verify no Chinese characters in data field names"""
    print("\nChecking for Chinese in data field names...")

    from core.province import Province
    from core.project import Project

    # Check Province attributes
    test_province = Province({'province_id': 1, 'name': 'Test', 'population': 1000, 'development_level': 1})
    province_attrs = dir(test_province)
    data_attrs = [attr for attr in province_attrs if not attr.startswith('_') and not callable(getattr(test_province, attr))]

    for attr in data_attrs:
        for char in attr:
            if '\u4e00' <= char <= '\u9fff':
                print(f"✗ Found Chinese character in attribute: {attr}")
                return False

    # Check Project attributes
    test_project = Project(1, 'agriculture', 1)
    project_attrs = vars(test_project).keys()

    for attr in project_attrs:
        for char in attr:
            if '\u4e00' <= char <= '\u9fff':
                print(f"✗ Found Chinese character in attribute: {attr}")
                return False

    print("✓ No Chinese characters found in data field names")
    return True

def verify_string_contents():
    """Verify no Chinese in string literals (except translations)"""
    print("\nChecking for Chinese in string literals...")

    import re

    core_files = [
        'core/province.py',
        'core/project.py',
        'core/calculations.py',
        'core/budget_system.py',
        'core/budget_execution.py',
        'core/treasury_system.py'
    ]

    for file_path in core_files:
        if os.path.exists(file_path):
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()

            # Check for Chinese characters (skip comments)
            lines = content.split('\n')
            for i, line in enumerate(lines, 1):
                # Skip comments
                if line.strip().startswith('#'):
                    continue
                # Check for Chinese in strings
                matches = re.findall(r"f?['\"]([^'\"]*)['\"]", line)
                for match in matches:
                    for char in match:
                        if '\u4e00' <= char <= '\u9fff':
                            print(f"✗ Found Chinese in string (line {i}): {match}")
                            return False

    print("✓ No Chinese characters found in data field strings")
    return True

def verify_cli_text():
    """Verify CLI text is in English"""
    print("\nVerifying CLI text is English...")

    cli_files = [
        'ui/cli.py',
        'ui/cli_realtime.py'
    ]

    common_phrases = [
        'Select operation:',
        'Press Enter',
        'Main Menu',
        'Treasury',
        'Province',
        'Project'
    ]

    for file_path in cli_files:
        if os.path.exists(file_path):
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()

            # Should contain English phrases
            if not any(phrase in content for phrase in common_phrases):
                print(f"✗ CLI file {file_path} doesn't contain expected English phrases")
                return False

            # Should not contain common ChineseUI phrases
            chinese_phrases = ['请选择', '按Enter', '国库', '省份', '项目']
            for phrase in chinese_phrases:
                if phrase in content:
                    print(f"✗ Found Chinese phrase '{phrase}' in {file_path}")
                    return False

    print("✓ CLI text appears to be in English")
    return True

def main():
    """Run all verification tests"""
    print("Starting verification of Chinese to English conversion...")
    print("=" * 60)

    tests = [
        verify_data_structures,
        verify_cli_integration,
        verify_core_modules,
        verify_no_chinese_in_data,
        verify_string_contents,
        verify_cli_text
    ]

    passed = 0
    failed = 0

    for test in tests:
        try:
            if test():
                passed += 1
            else:
                failed += 1
        except Exception as e:
            print(f"✗ Test {test.__name__} failed with exception: {e}")
            failed += 1
            import traceback
            traceback.print_exc()

    print("\n" + "=" * 60)
    print(f"Verification complete: {passed} passed, {failed} failed")

    if failed == 0:
        print("\n✅ All verification tests passed! Conversion successful.")
        return 0
    else:
        print(f"\n❌ {failed} verification test(s) failed. Please review.")
        return 1

if __name__ == '__main__':
    sys.exit(main())
