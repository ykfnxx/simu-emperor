"""Tests for PermissionChecker."""

import pytest

from simu_emperor.persistence.permissions import PermissionChecker


@pytest.fixture
def permission_checker(mock_client):
    return PermissionChecker(mock_client)


class TestPermissionChecker:
    @pytest.mark.asyncio
    async def test_check_province_access_granted_for_specific(
        self, permission_checker, mock_client
    ):
        mock_client.fetch_one.return_value = {
            "permissions": {"provinces": ["zhili", "shanxi"], "tools": []}
        }

        result = await permission_checker.check_province_access("governor_zhili", "zhili")

        assert result is True

    @pytest.mark.asyncio
    async def test_check_province_access_granted_for_wildcard(
        self, permission_checker, mock_client
    ):
        mock_client.fetch_one.return_value = {"permissions": {"provinces": ["*"], "tools": []}}

        result = await permission_checker.check_province_access("governor_zhili", "any_province")

        assert result is True

    @pytest.mark.asyncio
    async def test_check_province_access_denied(self, permission_checker, mock_client):
        mock_client.fetch_one.return_value = {"permissions": {"provinces": ["zhili"], "tools": []}}

        result = await permission_checker.check_province_access("governor_zhili", "shanxi")

        assert result is False

    @pytest.mark.asyncio
    async def test_check_province_access_denied_if_no_config(self, permission_checker, mock_client):
        mock_client.fetch_one.return_value = None

        result = await permission_checker.check_province_access("unknown_agent", "zhili")

        assert result is False

    @pytest.mark.asyncio
    async def test_check_province_access_denied_if_no_permissions_key(
        self, permission_checker, mock_client
    ):
        mock_client.fetch_one.return_value = {}

        result = await permission_checker.check_province_access("agent_001", "zhili")

        assert result is False

    @pytest.mark.asyncio
    async def test_check_tool_permission_granted_for_specific(
        self, permission_checker, mock_client
    ):
        mock_client.fetch_one.return_value = {
            "permissions": {"provinces": [], "tools": ["query_province", "set_tax"]}
        }

        result = await permission_checker.check_tool_permission("governor_zhili", "query_province")

        assert result is True

    @pytest.mark.asyncio
    async def test_check_tool_permission_granted_for_wildcard(
        self, permission_checker, mock_client
    ):
        mock_client.fetch_one.return_value = {"permissions": {"provinces": [], "tools": ["*"]}}

        result = await permission_checker.check_tool_permission("governor_zhili", "any_tool")

        assert result is True

    @pytest.mark.asyncio
    async def test_check_tool_permission_denied(self, permission_checker, mock_client):
        mock_client.fetch_one.return_value = {
            "permissions": {"provinces": [], "tools": ["query_province"]}
        }

        result = await permission_checker.check_tool_permission("governor_zhili", "delete_all")

        assert result is False

    @pytest.mark.asyncio
    async def test_check_tool_permission_denied_if_no_config(self, permission_checker, mock_client):
        mock_client.fetch_one.return_value = None

        result = await permission_checker.check_tool_permission("unknown_agent", "query")

        assert result is False

    @pytest.mark.asyncio
    async def test_get_permissions_returns_dict(self, permission_checker, mock_client):
        mock_client.fetch_one.return_value = {
            "permissions": {"provinces": ["zhili"], "tools": ["query"]}
        }

        result = await permission_checker.get_permissions("governor_zhili")

        assert result["provinces"] == ["zhili"]
        assert result["tools"] == ["query"]

    @pytest.mark.asyncio
    async def test_get_permissions_returns_empty_if_no_config(
        self, permission_checker, mock_client
    ):
        mock_client.fetch_one.return_value = None

        result = await permission_checker.get_permissions("unknown_agent")

        assert result == {}

    @pytest.mark.asyncio
    async def test_get_permissions_returns_empty_if_no_permissions_key(
        self, permission_checker, mock_client
    ):
        mock_client.fetch_one.return_value = {}

        result = await permission_checker.get_permissions("agent_001")

        assert result == {}
