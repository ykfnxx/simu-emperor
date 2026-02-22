"""Router 单元测试。"""

import asyncio
from pathlib import Path

import pytest

from simu_emperor.agents.router import (
    RouterAgent,
    RouterTimeoutError,
    update_role_map,
)


class MockLLMClient:
    """Mock LLM Client for testing."""

    def __init__(self, response: str = "governor_zhili"):
        self._response = response

    async def generate(self, context):
        return self._response


@pytest.fixture
def role_map_path(tmp_path: Path) -> Path:
    """创建临时 role_map.md 文件。"""
    role_map = tmp_path / "role_map.md"
    role_map.write_text(
        """# 大庆帝国官员职责表

## 直隶巡抚 (governor_zhili)
- 职责：直隶省民政、农桑、商贸、治安
- 适用命令：地方治理、粮食调度、商税征收、民情上报

## 户部尚书 (minister_of_revenue)
- 职责：全国财政、税收、粮储
- 适用命令：国库调拨、税率调整、赈灾拨款、财政报告
""",
        encoding="utf-8",
    )
    return role_map


class TestRouterAgent:
    """测试 RouterAgent。"""

    @pytest.mark.asyncio
    async def test_route_command_success(self, role_map_path: Path) -> None:
        """测试正常路由。"""
        client = MockLLMClient(response="governor_zhili")
        router = RouterAgent(client, timeout=5.0, role_map_path=role_map_path)

        agent_id = await router.route_command("赈济直隶灾民", {"turn": 1})
        assert agent_id == "governor_zhili"

    @pytest.mark.asyncio
    async def test_route_command_minister(self, role_map_path: Path) -> None:
        """测试路由到户部尚书。"""
        client = MockLLMClient(response="minister_of_revenue")
        router = RouterAgent(client, timeout=5.0, role_map_path=role_map_path)

        agent_id = await router.route_command("调整全国税率", {"turn": 1})
        assert agent_id == "minister_of_revenue"

    @pytest.mark.asyncio
    async def test_route_command_timeout(self, role_map_path: Path) -> None:
        """测试超时后抛出 RouterTimeoutError。"""

        class SlowClient:
            async def generate(self, context):
                await asyncio.sleep(10)
                return "governor_zhili"

        router = RouterAgent(SlowClient(), timeout=0.1, role_map_path=role_map_path)

        with pytest.raises(RouterTimeoutError, match="timeout"):
            await router.route_command("测试命令", {"turn": 1})

    @pytest.mark.asyncio
    async def test_route_command_invalid_agent(self, role_map_path: Path) -> None:
        """测试无效 agent_id 时抛出 ValueError。"""
        client = MockLLMClient(response="invalid_agent")
        router = RouterAgent(client, timeout=5.0, role_map_path=role_map_path)

        with pytest.raises(ValueError, match="Invalid agent_id"):
            await router.route_command("测试命令", {"turn": 1})

    @pytest.mark.asyncio
    async def test_route_command_ambiguous(self, role_map_path: Path) -> None:
        """测试模糊命令的路由行为 - LLM 返回有效 agent 时应该成功。"""
        # 模糊命令可能返回任意有效 agent
        client = MockLLMClient(response="governor_zhili")
        router = RouterAgent(client, timeout=5.0, role_map_path=role_map_path)

        # 模糊命令如"处理事务"
        agent_id = await router.route_command("处理事务", {"turn": 1})
        # 只要返回的是有效 agent_id 就应该成功
        assert agent_id in ["governor_zhili", "minister_of_revenue"]

    @pytest.mark.asyncio
    async def test_route_command_with_extra_whitespace(self, role_map_path: Path) -> None:
        """测试 LLM 返回带额外空白的结果能正确解析。"""
        client = MockLLMClient(response="  governor_zhili  ")
        router = RouterAgent(client, timeout=5.0, role_map_path=role_map_path)

        agent_id = await router.route_command("测试命令", {"turn": 1})
        assert agent_id == "governor_zhili"

    @pytest.mark.asyncio
    async def test_route_command_no_valid_agents_in_map(self, tmp_path: Path) -> None:
        """测试 role_map 中没有有效 agent 时的行为。"""
        empty_map = tmp_path / "empty.md"
        empty_map.write_text("# 空职责表\n", encoding="utf-8")

        client = MockLLMClient(response="any_agent")
        router = RouterAgent(client, timeout=5.0, role_map_path=empty_map)

        # 当没有有效 agent 列表时，任何 agent_id 都应该被接受
        agent_id = await router.route_command("测试命令", {"turn": 1})
        assert agent_id == "any_agent"

    def test_get_valid_agents(self, role_map_path: Path) -> None:
        """测试提取有效 agent 列表。"""
        client = MockLLMClient()
        router = RouterAgent(client, role_map_path=role_map_path)

        agents = router._get_valid_agents()
        assert "governor_zhili" in agents
        assert "minister_of_revenue" in agents

    def test_load_role_map_caching(self, role_map_path: Path) -> None:
        """测试 role_map 缓存。"""
        client = MockLLMClient()
        router = RouterAgent(client, role_map_path=role_map_path)

        # 第一次加载
        content1 = router._load_role_map()
        assert "直隶巡抚" in content1

        # 第二次应该返回缓存
        content2 = router._load_role_map()
        assert content1 is content2

    def test_load_role_map_not_exists(self, tmp_path: Path) -> None:
        """测试 role_map 文件不存在时返回空字符串。"""
        non_existent = tmp_path / "not_exists.md"
        client = MockLLMClient()
        router = RouterAgent(client, role_map_path=non_existent)

        content = router._load_role_map()
        assert content == ""

    def test_parse_agent_id_plain(self) -> None:
        """测试解析纯文本 agent_id。"""
        client = MockLLMClient()
        router = RouterAgent(client)

        assert router._parse_agent_id("governor_zhili") == "governor_zhili"

    def test_parse_agent_id_with_parens(self) -> None:
        """测试解析带括号的 agent_id。"""
        client = MockLLMClient()
        router = RouterAgent(client)

        assert router._parse_agent_id("选择 (minister_of_revenue)") == "minister_of_revenue"

    def test_parse_agent_id_with_spaces(self) -> None:
        """测试解析带空格的响应。"""
        client = MockLLMClient()
        router = RouterAgent(client)

        assert router._parse_agent_id("建议选择 governor_zhili") == "governor_zhili"


class TestUpdateRoleMap:
    """测试更新 role_map.md。"""

    def test_add_new_agent(self, tmp_path: Path) -> None:
        """测试添加新 agent。"""
        role_map = tmp_path / "role_map.md"
        role_map.write_text("# 大庆帝国官员职责表\n", encoding="utf-8")

        update_role_map(
            agent_id="minister_of_war",
            role_name="兵部尚书",
            role_description="全国军务、兵马调度",
            role_map_path=role_map,
        )

        content = role_map.read_text(encoding="utf-8")
        assert "兵部尚书 (minister_of_war)" in content
        assert "全国军务、兵马调度" in content

    def test_update_existing_agent(self, role_map_path: Path) -> None:
        """测试更新现有 agent。"""
        update_role_map(
            agent_id="governor_zhili",
            role_name="直隶巡抚",
            role_description="直隶省民政、农桑、商贸、治安、水利",
            role_map_path=role_map_path,
        )

        content = role_map_path.read_text(encoding="utf-8")
        # 新描述应该替换旧描述
        assert "水利" in content

    def test_concurrent_update_safety(self, tmp_path: Path) -> None:
        """测试并发更新安全性（基本测试）。"""
        role_map = tmp_path / "role_map.md"
        role_map.write_text("# 大庆帝国官员职责表\n", encoding="utf-8")

        # 顺序更新（filelock 保护）
        update_role_map("agent1", "角色1", "描述1", role_map_path=role_map)
        update_role_map("agent2", "角色2", "描述2", role_map_path=role_map)

        content = role_map.read_text(encoding="utf-8")
        assert "角色1 (agent1)" in content
        assert "角色2 (agent2)" in content
