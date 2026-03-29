"""Tests for GameStateRepository."""

import pytest

from simu_emperor.persistence.repositories.game_state import GameStateRepository


@pytest.fixture
def game_state_repo(mock_client):
    return GameStateRepository(mock_client)


class TestGameStateRepository:
    @pytest.mark.asyncio
    async def test_get_tick_returns_current_tick(self, game_state_repo, mock_client):
        mock_client.fetch_one.return_value = {"tick": 42}

        result = await game_state_repo.get_tick()

        assert result == 42

    @pytest.mark.asyncio
    async def test_get_tick_returns_zero_if_no_row(self, game_state_repo, mock_client):
        mock_client.fetch_one.return_value = None

        result = await game_state_repo.get_tick()

        assert result == 0

    @pytest.mark.asyncio
    async def test_get_province_returns_data(self, game_state_repo, mock_client):
        mock_client.fetch_one.return_value = {
            "province_id": "zhili",
            "population": 500000,
            "treasury": 10000,
            "tax_rate": 0.03,
            "stability": 0.8,
        }

        result = await game_state_repo.get_province("zhili")

        assert result["province_id"] == "zhili"
        assert result["population"] == 500000

    @pytest.mark.asyncio
    async def test_get_province_returns_none_if_not_found(self, game_state_repo, mock_client):
        mock_client.fetch_one.return_value = None

        result = await game_state_repo.get_province("nonexistent")

        assert result is None

    @pytest.mark.asyncio
    async def test_save_province_updates_fields(self, game_state_repo, mock_client):
        data = {
            "population": 600000,
            "treasury": 15000,
            "tax_rate": 0.05,
        }

        await game_state_repo.save_province("zhili", data)

        mock_client.execute.assert_called_once()
        call_args = mock_client.execute.call_args[0]
        sql = call_args[0]
        assert "UPDATE provinces" in sql
        assert "population = ?" in sql
        assert "treasury = ?" in sql
        assert "tax_rate = ?" in sql

    @pytest.mark.asyncio
    async def test_save_province_skips_if_no_valid_fields(self, game_state_repo, mock_client):
        data = {"invalid_field": "value"}

        await game_state_repo.save_province("zhili", data)

        mock_client.execute.assert_not_called()

    @pytest.mark.asyncio
    async def test_save_province_handles_partial_data(self, game_state_repo, mock_client):
        data = {"population": 700000}

        await game_state_repo.save_province("zhili", data)

        call_args = mock_client.execute.call_args[0]
        sql = call_args[0]
        assert "population = ?" in sql
        assert "treasury" not in sql

    @pytest.mark.asyncio
    async def test_get_national_treasury_returns_data(self, game_state_repo, mock_client):
        mock_client.fetch_one.return_value = {
            "id": 1,
            "total_silver": 500000,
            "monthly_income": 10000,
            "monthly_expense": 8000,
            "base_tax_rate": 0.03,
        }

        result = await game_state_repo.get_national_treasury()

        assert result["total_silver"] == 500000

    @pytest.mark.asyncio
    async def test_get_national_treasury_returns_none_if_not_found(
        self, game_state_repo, mock_client
    ):
        mock_client.fetch_one.return_value = None

        result = await game_state_repo.get_national_treasury()

        assert result is None

    @pytest.mark.asyncio
    async def test_save_national_treasury_updates_fields(self, game_state_repo, mock_client):
        data = {
            "total_silver": 600000,
            "monthly_income": 12000,
        }

        await game_state_repo.save_national_treasury(data)

        mock_client.execute.assert_called_once()
        call_args = mock_client.execute.call_args[0]
        sql = call_args[0]
        assert "UPDATE national_treasury" in sql
        assert "total_silver = ?" in sql
        assert "monthly_income = ?" in sql

    @pytest.mark.asyncio
    async def test_save_national_treasury_skips_if_no_valid_fields(
        self, game_state_repo, mock_client
    ):
        data = {"invalid_field": "value"}

        await game_state_repo.save_national_treasury(data)

        mock_client.execute.assert_not_called()

    @pytest.mark.asyncio
    async def test_increment_tick_calls_execute(self, game_state_repo, mock_client):
        await game_state_repo.increment_tick()

        mock_client.execute.assert_called_once()
        call_args = mock_client.execute.call_args[0]
        assert "UPDATE game_tick" in call_args[0]
        assert "tick = tick + 1" in call_args[0]
