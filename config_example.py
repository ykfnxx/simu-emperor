"""
Simple configuration usage examples

Demonstrates how to use the configuration system and test PerceptionAgent
"""

import asyncio
import os
from config_loader import get_config, init_config, setup_config_from_args


def example_basic_usage():
    """Basic configuration usage example"""
    print("="*70)
    print("Example 1: Basic configuration usage")
    print("="*70)

    # Load configuration
    config = get_config()

    # Read configuration values
    print(f"\nconfig file: {config.config_path}")
    print(f"LLM enabled: {config.get('llm.enabled')}")
    print(f"LLM model: {config.get('llm.model')}")
    print(f"Mock mode: {config.get('llm.mock_mode')}")

    # 检查LLM状态
    if config.is_llm_enabled():
        print("\n✓ LLM enabled and configured")
    else:
        print("\nℹ LLM not enabled or using mock mode")

    # Modify configuration
    print("\n修改配置...")
    config.set('llm.temperature', 0.7)
    print(f"Temperature set to: {config.get('llm.temperature')}")

    # GetAgent配置
    print("\nGet Agent configuration:")
    llm_config = config.get_llm_config()
    print(f"  LLM配置: {llm_config}")

    agent_config = config.get_province_agent_config(province_id=1)
    print(f"  Agent configuration: mode={agent_config['mode']}")


def example_from_args():
    """Load configuration from command line parameters"""
    print("\n" + "="*70)
    print("Example 2: Load configuration from command line parameters")
    print("="*70)

    print("\nUsage:")
    print("  python config_example.py --config config.yaml --api-key your-key")
    print("  python config_example.py --mock")

    # 如果有command lineparameter
    import sys
    if len(sys.argv) > 1:
        config = setup_config_from_args()
        print(f"\nLoaded configuration from command line: {config.config_path}")
    else:
        print("\n(No command line parameters, using default configuration)")


def example_environment_variable():
    """Environment variable usage example"""
    print("\n" + "="*70)
    print("Example 3: Use environment variables")
    print("="*70)

    print("\nMethod 1: Set environment variable")
    print("  export ANTHROPIC_API_KEY=sk-ant-api03-...")
    print("  python your_script.py")

    print("\nMethod 2: Use environment variable in config.yaml")
    print("  llm:")
    print("    api_key: \"${ANTHROPIC_API_KEY}\"")

    print("\nMethod 3: Set in Python")
    print("  os.environ['ANTHROPIC_API_KEY'] = 'sk-ant-api03-...'")

    # 演示读取environment variable
    api_key = os.getenv('ANTHROPIC_API_KEY')
    if api_key:
        print(f"\n✓ Environment variable set: {api_key[:20]}...")
    else:
        print("\nℹ Environment variable not set")


def example_with_agent():
    """Use configuration in Agent"""
    print("\n" + "="*70)
    print("Example 4: Use configuration in Agent")
    print("="*70)

    config = get_config()

    # GetPerceptionAgent配置
    perception_config = config.get_perception_config()
    print("\nPerceptionAgent configuration:")
    print(f"  Historical months: {perception_config['history_months']}")
    print(f"  Quarterly quarters: {perception_config['quarterly_quarters']}")
    print(f"  Annual years: {perception_config['annual_years']}")
    print(f"  Use LLM summary: {perception_config['use_llm_summary']}")

    # GetDecisionAgent配置
    decision_config = config.get_decision_config()
    print("\nDecisionAgent configuration:")
    print(f"  Allow instructions: {decision_config['allow_instructions']}")
    print(f"  Autonomous decision: {decision_config['autonomous_enabled']}")
    print(f"  Strategy: {decision_config['strategy']}")

    # GetExecutionAgent配置
    execution_config = config.get_execution_config()
    print("\nExecutionAgent配置:")
    print(f"  Validate parameters: {execution_config['validate_params']}")
    print(f"  Generate events: {execution_config['generate_events']}")


def example_check_llm_status():
    """Check LLM configuration status"""
    print("\n" + "="*70)
    print("Example 5: Check LLM configuration status")
    print("="*70)

    config = get_config()

    print("\nLLM配置检查:")
    print(f"  ✓ enabled: {config.get('llm.enabled')}")
    print(f"  ✓ api_key: {'Set' if config.get('llm.api_key') else 'Not set'}")
    print(f"  ✓ model: {config.get('llm.model')}")
    print(f"  ✓ mock_mode: {config.get('llm.mock_mode')}")

    if config.is_llm_enabled():
        print("\n✓ LLM fully configured, can use real API")
        print("\nRun real API test:")
        print("  python test_perception_agent_with_api.py")
    else:
        print("\n⚠️  LLM not fully configured:")
        if not config.get('llm.enabled'):
            print("  - Set llm.enabled: true in config.yaml")
        if not config.get('llm.api_key'):
            print("  - Set ANTHROPIC_API_KEY environment variable")
            print("  - Or set llm.api_key in config.yaml")
        if config.get('llm.mock_mode'):
            print("  - Set llm.mock_mode: false in config.yaml")


def example_test_with_mock():
    """Test with mock mode"""
    print("\n" + "="*70)
    print("Example 6: Test with Mock mode")
    print("="*70)

    print("\nMock mode doesn't need API key, suitable for development testing")

    print("\nEnsure in config.yaml:")
    print("  llm:")
    print("    mock_mode: true")
    print("    enabled: true  # Optional")

    print("\nThen run:")
    print("  python test_perception_agent.py")
    print("  python test_perception_agent_with_api.py --mock")


if __name__ == "__main__":
    print("\n" + "="*70)
    print("Province Agent Configuration System Usage Examples")
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
