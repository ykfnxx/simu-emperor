"""Tests for AgentConfigRepository."""

import pytest

from simu_emperor.persistence.repositories.agent_config import AgentConfigRepository


@pytest.fixture
def agent_config_repo(mock_client):
    return AgentConfigRepository(mock_client)


class TestAgentConfigRepository:
    @pytest.mark.asyncio
    async def test_get_returns_active_agent(
        self, agent_config_repo, mock_client, sample_agent_config
    ):
        mock_client.fetch_one.return_value = sample_agent_config

        result = await agent_config_repo.get("governor_zhili")

        assert result["agent_id"] == "governor_zhili"
        mock_client.fetch_one.assert_called_once()
        sql = mock_client.fetch_one.call_args[0][0]
        assert "is_active = TRUE" in sql

    @pytest.mark.asyncio
    async def test_get_returns_none_if_not_found(self, agent_config_repo, mock_client):
        mock_client.fetch_one.return_value = None

        result = await agent_config_repo.get("nonexistent")

        assert result is None

    @pytest.mark.asyncio
    async def test_get_all_returns_active_agents(
        self, agent_config_repo, mock_client, sample_agent_config
    ):
        mock_client.fetch_all.return_value = [sample_agent_config]

        results = await agent_config_repo.get_all()

        assert len(results) == 1
        assert results[0]["agent_id"] == "governor_zhili"

    @pytest.mark.asyncio
    async def test_get_all_returns_empty_list_if_none(self, agent_config_repo, mock_client):
        mock_client.fetch_all.return_value = []

        results = await agent_config_repo.get_all()

        assert results == []

    @pytest.mark.asyncio
    async def test_save_inserts_new_config(self, agent_config_repo, mock_client):
        await agent_config_repo.save(
            agent_id="governor_shanxi",
            role_name="山西巡抚",
            soul_text="# 山西巡抚\n\n负责山西事务",
            skills=["query_province"],
            permissions={"provinces": ["shanxi"]},
        )

        mock_client.execute.assert_called_once()
        call_args = mock_client.execute.call_args[0]
        assert "INSERT INTO agent_config" in call_args[0]
        assert "ON DUPLICATE KEY UPDATE" in call_args[0]

    @pytest.mark.asyncio
    async def test_save_handles_none_skills_and_permissions(self, agent_config_repo, mock_client):
        await agent_config_repo.save(
            agent_id="simple_agent",
            role_name="简单官员",
            soul_text="简单配置",
        )

        call_args = mock_client.execute.call_args[0]
        assert call_args[4] is None
        assert call_args[5] is None

    @pytest.mark.asyncio
    async def test_update_permissions_calls_execute(self, agent_config_repo, mock_client):
        new_permissions = {"provinces": ["*"], "tools": ["query_all"]}

        await agent_config_repo.update_permissions("governor_zhili", new_permissions)

        mock_client.execute.assert_called_once()
        call_args = mock_client.execute.call_args[0]
        assert "UPDATE agent_config" in call_args[0]
        assert "permissions = ?" in call_args[0]
