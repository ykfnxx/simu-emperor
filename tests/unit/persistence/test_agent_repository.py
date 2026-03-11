"""
测试 AgentRepository
"""

import pytest
import aiosqlite

from simu_emperor.persistence.repositories import AgentRepository


@pytest.fixture
async def db_conn():
    """创建内存数据库连接"""
    conn = await aiosqlite.connect(":memory:")
    from simu_emperor.persistence.database import _create_schema
    await _create_schema(conn)
    yield conn
    await conn.close()


@pytest.fixture
def repo(db_conn):
    """创建 AgentRepository 实例"""
    return AgentRepository(db_conn)


class TestAgentRepository:
    """测试 AgentRepository"""

    @pytest.mark.asyncio
    async def test_get_active_agents_empty(self, repo):
        """测试获取活跃 Agent（空）"""
        agents = await repo.get_active_agents()
        assert agents == []

    @pytest.mark.asyncio
    async def test_set_agent_active(self, repo):
        """测试设置 Agent 活跃状态"""
        await repo.set_agent_active("test_agent", True)
        agents = await repo.get_active_agents()
        assert "test_agent" in agents

    @pytest.mark.asyncio
    async def test_set_agent_inactive(self, repo):
        """测试设置 Agent 非活跃状态"""
        await repo.set_agent_active("test_agent", True)
        await repo.set_agent_active("test_agent", False)
        agents = await repo.get_active_agents()
        assert "test_agent" not in agents

    @pytest.mark.asyncio
    async def test_save_and_load_agent_config(self, repo):
        """测试保存和加载 Agent 配置"""
        soul = "# Test Soul"
        scope = "query: []"
        await repo.save_agent_config("test_agent", soul, scope)
        loaded = await repo.load_agent_config("test_agent")
        assert loaded["soul_markdown"] == soul
        assert loaded["data_scope_yaml"] == scope
