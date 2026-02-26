"""
测试响应解析器
"""


from simu_emperor.agents.response_parser import (
    parse_chat_result,
    parse_execution_result,
    parse_query_result,
)


class TestParseExecutionResult:
    """测试 parse_execution_result"""

    def test_parse_valid_json(self):
        """测试解析有效 JSON"""
        response = '{"narrative": "Test narrative", "action": "test_action", "params": {"key": "value"}}'
        result = parse_execution_result(response)

        assert result["narrative"] == "Test narrative"
        assert result["action"] == "test_action"
        assert result["params"] == {"key": "value"}

    def test_parse_json_in_markdown(self):
        """测试解析 Markdown 代码块中的 JSON"""
        response = '```json\n{"narrative": "Test", "action": "test", "params": {}}\n```'
        result = parse_execution_result(response)

        assert result["narrative"] == "Test"
        assert result["action"] == "test"

    def test_parse_invalid_json(self):
        """测试解析无效 JSON（返回默认值）"""
        response = "This is not valid JSON"
        result = parse_execution_result(response)

        assert result["narrative"] == response
        assert result["action"] == "unknown"
        assert result["params"] == {}

    def test_parse_missing_fields(self):
        """测试缺少必需字段"""
        response = '{"narrative": "Test"}'
        result = parse_execution_result(response)

        # 应该返回默认值
        assert result["action"] == "unknown"

    def test_parse_action_pattern(self):
        """测试匹配简单动作模式"""
        response = "我要执行动作：adjust_tax"
        result = parse_execution_result(response)

        assert result["action"] == "adjust_tax"

    def test_parse_params_optional(self):
        """测试 params 是可选的"""
        response = '{"narrative": "Test", "action": "test"}'
        result = parse_execution_result(response)

        assert result["narrative"] == "Test"
        assert result["action"] == "test"
        assert result["params"] == {}


class TestParseQueryResult:
    """测试 parse_query_result"""

    def test_parse_json_with_result(self):
        """测试解析包含 result 字段的 JSON"""
        response = '{"result": "Query result"}'
        result = parse_query_result(response)

        assert result == "Query result"

    def test_parse_plain_text(self):
        """测试解析纯文本"""
        response = "This is a plain text response"
        result = parse_query_result(response)

        assert result == response


class TestParseChatResult:
    """测试 parse_chat_result"""

    def test_parse_json_with_narrative(self):
        """测试解析包含 narrative 字段的 JSON"""
        response = '```json\n{"narrative": "Hello there!"}\n```'
        result = parse_chat_result(response)

        assert result == "Hello there!"

    def test_parse_plain_text(self):
        """测试解析纯文本"""
        response = "Hello, how are you?"
        result = parse_chat_result(response)

        assert result == response
