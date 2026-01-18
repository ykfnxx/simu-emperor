"""
简单的配置使用示例

演示如何使用配置系统和测试PerceptionAgent
"""

import asyncio
import os
from config_loader import get_config, init_config, setup_config_from_args


def example_basic_usage():
    """基础配置使用示例"""
    print("="*70)
    print("示例1: 基础配置使用")
    print("="*70)

    # 加载配置
    config = get_config()

    # 读取配置值
    print(f"\n配置文件: {config.config_path}")
    print(f"LLM 启用: {config.get('llm.enabled')}")
    print(f"LLM 模型: {config.get('llm.model')}")
    print(f"Mock 模式: {config.get('llm.mock_mode')}")

    # 检查LLM状态
    if config.is_llm_enabled():
        print("\n✓ LLM已启用并配置")
    else:
        print("\nℹ LLM未启用或使用mock模式")

    # 修改配置
    print("\n修改配置...")
    config.set('llm.temperature', 0.7)
    print(f"温度设置为: {config.get('llm.temperature')}")

    # 获取Agent配置
    print("\n获取Agent配置:")
    llm_config = config.get_llm_config()
    print(f"  LLM配置: {llm_config}")

    agent_config = config.get_province_agent_config(province_id=1)
    print(f"  Agent配置: mode={agent_config['mode']}")


def example_from_args():
    """从命令行参数加载配置"""
    print("\n" + "="*70)
    print("示例2: 从命令行参数加载配置")
    print("="*70)

    print("\n使用方法:")
    print("  python config_example.py --config config.yaml --api-key your-key")
    print("  python config_example.py --mock")

    # 如果有命令行参数
    import sys
    if len(sys.argv) > 1:
        config = setup_config_from_args()
        print(f"\n从命令行加载配置: {config.config_path}")
    else:
        print("\n(无命令行参数，使用默认配置)")


def example_environment_variable():
    """环境变量使用示例"""
    print("\n" + "="*70)
    print("示例3: 使用环境变量")
    print("="*70)

    print("\n方式1: 设置环境变量")
    print("  export ANTHROPIC_API_KEY=sk-ant-api03-...")
    print("  python your_script.py")

    print("\n方式2: 在config.yaml中使用环境变量")
    print("  llm:")
    print("    api_key: \"${ANTHROPIC_API_KEY}\"")

    print("\n方式3: 在Python中设置")
    print("  os.environ['ANTHROPIC_API_KEY'] = 'sk-ant-api03-...'")

    # 演示读取环境变量
    api_key = os.getenv('ANTHROPIC_API_KEY')
    if api_key:
        print(f"\n✓ 环境变量已设置: {api_key[:20]}...")
    else:
        print("\nℹ 环境变量未设置")


def example_with_agent():
    """在Agent中使用配置"""
    print("\n" + "="*70)
    print("示例4: 在Agent中使用配置")
    print("="*70)

    config = get_config()

    # 获取PerceptionAgent配置
    perception_config = config.get_perception_config()
    print("\nPerceptionAgent配置:")
    print(f"  历史月数: {perception_config['history_months']}")
    print(f"  季度数: {perception_config['quarterly_quarters']}")
    print(f"  年数: {perception_config['annual_years']}")
    print(f"  使用LLM摘要: {perception_config['use_llm_summary']}")

    # 获取DecisionAgent配置
    decision_config = config.get_decision_config()
    print("\nDecisionAgent配置:")
    print(f"  允许指令: {decision_config['allow_instructions']}")
    print(f"  自主决策: {decision_config['autonomous_enabled']}")
    print(f"  策略: {decision_config['strategy']}")

    # 获取ExecutionAgent配置
    execution_config = config.get_execution_config()
    print("\nExecutionAgent配置:")
    print(f"  验证参数: {execution_config['validate_params']}")
    print(f"  生成事件: {execution_config['generate_events']}")


def example_check_llm_status():
    """检查LLM配置状态"""
    print("\n" + "="*70)
    print("示例5: 检查LLM配置状态")
    print("="*70)

    config = get_config()

    print("\nLLM配置检查:")
    print(f"  ✓ enabled: {config.get('llm.enabled')}")
    print(f"  ✓ api_key: {'已设置' if config.get('llm.api_key') else '未设置'}")
    print(f"  ✓ model: {config.get('llm.model')}")
    print(f"  ✓ mock_mode: {config.get('llm.mock_mode')}")

    if config.is_llm_enabled():
        print("\n✓ LLM已完全配置，可以使用真实API")
        print("\n运行真实API测试:")
        print("  python test_perception_agent_with_api.py")
    else:
        print("\n⚠️  LLM未完全配置:")
        if not config.get('llm.enabled'):
            print("  - 在config.yaml中设置 llm.enabled: true")
        if not config.get('llm.api_key'):
            print("  - 设置ANTHROPIC_API_KEY环境变量")
            print("  - 或在config.yaml中设置llm.api_key")
        if config.get('llm.mock_mode'):
            print("  - 在config.yaml中设置llm.mock_mode: false")


def example_test_with_mock():
    """使用mock模式测试"""
    print("\n" + "="*70)
    print("示例6: 使用Mock模式测试")
    print("="*70)

    print("\nMock模式不需要API key，适合开发测试")

    print("\n确保config.yaml中:")
    print("  llm:")
    print("    mock_mode: true")
    print("    enabled: true  # 可选")

    print("\n然后运行:")
    print("  python test_perception_agent.py")
    print("  python test_perception_agent_with_api.py --mock")


if __name__ == "__main__":
    print("\n" + "="*70)
    print("Province Agent 配置系统使用示例")
    print("="*70)

    # 运行所有示例
    example_basic_usage()
    example_from_args()
    example_environment_variable()
    example_with_agent()
    example_check_llm_status()
    example_test_with_mock()

    print("\n" + "="*70)
    print("更多信息请参考: API_TEST_GUIDE.md")
    print("="*70)
