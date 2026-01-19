"""
简单的配置使用示例

演示如何使用配置system和TestPerceptionAgent
"""

import asyncio
import os
from config_loader import get_config, init_config, setup_config_from_args


def example_basic_usage():
    """基础配置使用示例"""
    print("="*70)
    print("示例1: 基础配置使用")
    print("="*70)

    # Load配置
    config = get_config()

    # 读取配置值
    print(f"\nconfig file: {config.config_path}")
    print(f"LLM 启用: {config.get('llm.enabled')}")
    print(f"LLM model: {config.get('llm.model')}")
    print(f"Mock 模式: {config.get('llm.mock_mode')}")

    # 检查LLM状态
    if config.is_llm_enabled():
        print("\n✓ LLM已启用并配置")
    else:
        print("\nℹ LLM未启用或使用mock模式")

    # 修改配置
    print("\n修改配置...")
    config.set('llm.temperature', 0.7)
    print(f"温度settings为: {config.get('llm.temperature')}")

    # GetAgent配置
    print("\nGetAgent配置:")
    llm_config = config.get_llm_config()
    print(f"  LLM配置: {llm_config}")

    agent_config = config.get_province_agent_config(province_id=1)
    print(f"  Agent配置: mode={agent_config['mode']}")


def example_from_args():
    """从command lineparameterLoad配置"""
    print("\n" + "="*70)
    print("示例2: 从command lineparameterLoad配置")
    print("="*70)

    print("\nUsage:")
    print("  python config_example.py --config config.yaml --api-key your-key")
    print("  python config_example.py --mock")

    # 如果有command lineparameter
    import sys
    if len(sys.argv) > 1:
        config = setup_config_from_args()
        print(f"\n从command lineLoad配置: {config.config_path}")
    else:
        print("\n(无command lineparameter，使用默认配置)")


def example_environment_variable():
    """environment variable使用示例"""
    print("\n" + "="*70)
    print("示例3: 使用environment variable")
    print("="*70)

    print("\n方式1: settingsenvironment variable")
    print("  export ANTHROPIC_API_KEY=sk-ant-api03-...")
    print("  python your_script.py")

    print("\n方式2: 在config.yaml中使用environment variable")
    print("  llm:")
    print("    api_key: \"${ANTHROPIC_API_KEY}\"")

    print("\n方式3: 在Python中settings")
    print("  os.environ['ANTHROPIC_API_KEY'] = 'sk-ant-api03-...'")

    # 演示读取environment variable
    api_key = os.getenv('ANTHROPIC_API_KEY')
    if api_key:
        print(f"\n✓ environment variable已settings: {api_key[:20]}...")
    else:
        print("\nℹ environment variable未settings")


def example_with_agent():
    """在Agent中使用配置"""
    print("\n" + "="*70)
    print("示例4: 在Agent中使用配置")
    print("="*70)

    config = get_config()

    # GetPerceptionAgent配置
    perception_config = config.get_perception_config()
    print("\nPerceptionAgent配置:")
    print(f"  historical月数: {perception_config['history_months']}")
    print(f"  quarter数: {perception_config['quarterly_quarters']}")
    print(f"  年数: {perception_config['annual_years']}")
    print(f"  使用LLMsummary: {perception_config['use_llm_summary']}")

    # GetDecisionAgent配置
    decision_config = config.get_decision_config()
    print("\nDecisionAgent配置:")
    print(f"  允许指令: {decision_config['allow_instructions']}")
    print(f"  自主decision: {decision_config['autonomous_enabled']}")
    print(f"  策略: {decision_config['strategy']}")

    # GetExecutionAgent配置
    execution_config = config.get_execution_config()
    print("\nExecutionAgent配置:")
    print(f"  validateparameter: {execution_config['validate_params']}")
    print(f"  generateevent: {execution_config['generate_events']}")


def example_check_llm_status():
    """检查LLM配置状态"""
    print("\n" + "="*70)
    print("示例5: 检查LLM配置状态")
    print("="*70)

    config = get_config()

    print("\nLLM配置检查:")
    print(f"  ✓ enabled: {config.get('llm.enabled')}")
    print(f"  ✓ api_key: {'已settings' if config.get('llm.api_key') else '未settings'}")
    print(f"  ✓ model: {config.get('llm.model')}")
    print(f"  ✓ mock_mode: {config.get('llm.mock_mode')}")

    if config.is_llm_enabled():
        print("\n✓ LLM已完全配置，可以使用真实API")
        print("\nRun真实APITest:")
        print("  python test_perception_agent_with_api.py")
    else:
        print("\n⚠️  LLM未完全配置:")
        if not config.get('llm.enabled'):
            print("  - 在config.yaml中settings llm.enabled: true")
        if not config.get('llm.api_key'):
            print("  - settingsANTHROPIC_API_KEYenvironment variable")
            print("  - 或在config.yaml中settingsllm.api_key")
        if config.get('llm.mock_mode'):
            print("  - 在config.yaml中settingsllm.mock_mode: false")


def example_test_with_mock():
    """使用mock模式Test"""
    print("\n" + "="*70)
    print("示例6: 使用Mock模式Test")
    print("="*70)

    print("\nMock模式不需要API key，适合开发Test")

    print("\n确保config.yaml中:")
    print("  llm:")
    print("    mock_mode: true")
    print("    enabled: true  # 可选")

    print("\n然后Run:")
    print("  python test_perception_agent.py")
    print("  python test_perception_agent_with_api.py --mock")


if __name__ == "__main__":
    print("\n" + "="*70)
    print("Province Agent 配置system使用示例")
    print("="*70)

    # Run所有示例
    example_basic_usage()
    example_from_args()
    example_environment_variable()
    example_with_agent()
    example_check_llm_status()
    example_test_with_mock()

    print("\n" + "="*70)
    print("更多信息请参考: API_TEST_GUIDE.md")
    print("="*70)
