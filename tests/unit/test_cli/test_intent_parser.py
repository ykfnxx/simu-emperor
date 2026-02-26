"""
测试 IntentParser
"""

import pytest

from simu_emperor.cli.intent_parser import IntentParser
from simu_emperor.llm.mock import MockProvider


@pytest.fixture
def mock_llm():
    """Mock LLM Provider"""
    llm = MockProvider(response='{"target_agent": "revenue_minister", "intent": "command", "action": "adjust_tax", "params": {"province": "zhili", "rate": 0.1}}')
    return llm


@pytest.fixture
def parser(mock_llm):
    """创建 IntentParser 实例"""
    return IntentParser(mock_llm)


class TestIntentParser:
    """测试 IntentParser 类"""

    def test_init(self, parser, mock_llm):
        """测试初始化"""
        assert parser.llm_provider == mock_llm
        assert parser.system_prompt is not None

    @pytest.mark.asyncio
    async def test_parse(self, parser):
        """测试解析意图"""
        result = await parser.parse("调整直隶的税率到 10%", ["revenue_minister"])

        assert result["target_agent"] == "revenue_minister"
        assert result["intent"] == "command"
        assert result["action"] == "adjust_tax"
        assert result["params"]["province"] == "zhili"
        assert result["params"]["rate"] == 0.1

    @pytest.mark.asyncio
    async def test_parse_invalid_json(self, parser):
        """测试解析无效 JSON"""
        parser.llm_provider.set_response("This is not JSON")

        result = await parser.parse("测试输入", [])

        # 应该返回默认值
        assert result["intent"] == "command"
        assert result["action"] == "unknown"
        assert "raw_input" in result["params"]

    @pytest.mark.asyncio
    async def test_parse_missing_fields(self, parser):
        """测试解析缺少字段"""
        parser.llm_provider.set_response('{"target_agent": "test"}')

        result = await parser.parse("测试输入", [])

        # 应该填充默认值
        assert result["target_agent"] == "test"
        assert result["intent"] == "command"
        assert result["action"] == "unknown"
        assert result["params"] == {}
