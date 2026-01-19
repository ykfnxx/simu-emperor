"""
Province Agent Tests

This directory contains test files for the Province Agent system.
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

# Test imports
print("Province Agent Test Suite")
print("=" * 70)

print("\nAvailable test files:")
print("  - test_perception_agent.py")
print("      Standalone PerceptionAgent test with mock mode")
print("      Usage: python -m tests.province.test_perception_agent")
print("")
print("  - test_perception_agent_with_api.py")
print("      PerceptionAgent test with real LLM API support")
print("      Usage: python -m tests.province.test_perception_agent_with_api")
print("      Options: --config <path>, --api-key <key>, --mock")
print("")

print("\nConfiguration:")
print("  Copy config.yaml.example to config.yaml")
print("  Set your ANTHROPIC_API_KEY environment variable")
print("  Enable LLM in config.yaml (set llm.enabled: true)")
print("")

print("For detailed documentation, see: ../../API_TEST_GUIDE.md")
print("=" * 70)
