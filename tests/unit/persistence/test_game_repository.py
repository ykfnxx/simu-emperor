"""
测试 GameRepository
"""

import pytest
import aiosqlite

from simu_emperor.persistence.database import init_database
from simu_emperor.persistence.repositories import GameRepository


@pytest.fixture
async def db_conn():
    """创建内存数据库连接"""
    conn = await aiosqlite.connect(":memory:")
    await init_database(":memory:")
    # 使用新的 schema
    from simu_emperor.persistence.database import _create_schema
    await _create_schema(conn)
    yield conn
    await conn.close()


@pytest.fixture
def repo(db_conn):
    """创建 GameRepository 实例"""
    return GameRepository(db_conn)


class TestGameRepository:
    """测试 GameRepository"""

    @pytest.mark.asyncio
    async def test_load_state_empty(self, repo):
        """测试加载空状态"""
        state = await repo.load_state()
        assert state == {}

    @pytest.mark.asyncio
    async def test_save_and_load_state(self, repo):
        """测试保存和加载状态"""
        test_state = {
            "turn": 5,
            "imperial_treasury": 100000,
            "provinces": [
                {
                    "province_id": "zhili",
                    "name": "直隶",
                    "taxation": {"land_tax_rate": 0.1}
                }
            ]
        }

        await repo.save_state(test_state)
        loaded = await repo.load_state()

        assert loaded["turn"] == 5
        assert len(loaded["provinces"]) == 1
        assert loaded["provinces"][0]["province_id"] == "zhili"

    @pytest.mark.asyncio
    async def test_save_turn_metrics(self, repo):
        """测试保存回合指标"""
        metrics = {
            "total_food_production": 1000,
            "total_food_consumption": 800,
        }

        await repo.save_turn_metrics(1, metrics)
        loaded = await repo.load_turn_metrics(1)

        assert loaded["total_food_production"] == 1000

    @pytest.mark.asyncio
    async def test_get_current_turn(self, repo):
        """测试获取当前回合"""
        # 初始回合应该是 0
        turn = await repo.get_current_turn()
        assert turn == 0

    @pytest.mark.asyncio
    async def test_increment_turn(self, repo):
        """测试增加回合"""
        new_turn = await repo.increment_turn()
        assert new_turn == 1

        turn = await repo.get_current_turn()
        assert turn == 1

    @pytest.mark.asyncio
    async def test_update_province_data(self, repo):
        """测试更新省份数据"""
        # 先保存一些状态
        state = {
            "turn": 1,
            "imperial_treasury": 100000,
            "provinces": [
                {
                    "province_id": "zhili",
                    "name": "直隶",
                    "taxation": {}
                }
            ]
        }
        await repo.save_state(state)

        # 更新省份数据
        await repo.update_province_data("zhili", "taxation.land_tax_rate", 0.15)

        # 加载并验证
        loaded = await repo.load_state()
        assert loaded["provinces"][0]["taxation"]["land_tax_rate"] == 0.15
