"""
测试 GameRepository (V4 API)
"""

import pytest
import aiosqlite
from decimal import Decimal

from simu_emperor.persistence.repositories import GameRepository
from simu_emperor.engine.models.base_data import NationData, ProvinceData


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
    """创建 GameRepository 实例"""
    return GameRepository(db_conn)


class TestGameRepository:
    """测试 GameRepository (V4 API)"""

    @pytest.mark.asyncio
    async def test_load_nation_data_empty(self, repo):
        """测试加载空状态 - 返回默认 NationData"""
        state = await repo.load_nation_data()
        assert state.turn == 0
        assert state.imperial_treasury == Decimal("0")
        assert state.provinces == {}

    @pytest.mark.asyncio
    async def test_save_and_load_nation_data(self, repo):
        """测试保存和加载 NationData"""
        province = ProvinceData(
            province_id="zhili",
            name="直隶",
            production_value=Decimal("100000"),
            population=Decimal("500000"),
            fixed_expenditure=Decimal("10000"),
            stockpile=Decimal("5000"),
        )
        test_nation = NationData(
            turn=5,
            imperial_treasury=Decimal("100000"),
            provinces={"zhili": province},
        )
        await repo.save_nation_data(test_nation)
        loaded = await repo.load_nation_data()
        assert loaded.turn == 5
        assert loaded.imperial_treasury == Decimal("100000")
        assert len(loaded.provinces) == 1
        assert "zhili" in loaded.provinces
        assert loaded.provinces["zhili"].name == "直隶"

    @pytest.mark.asyncio
    async def test_get_current_tick(self, repo):
        """测试获取当前 tick"""
        tick = await repo.get_current_tick()
        assert tick == 0

        # 保存一个新状态
        nation = NationData(turn=10)
        await repo.save_nation_data(nation)
        tick = await repo.get_current_tick()
        assert tick == 10

    @pytest.mark.asyncio
    async def test_load_state_deprecated(self, repo):
        """测试已废弃的 load_state 方法"""
        import warnings

        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            state = await repo.load_state()
            assert len(w) == 1
            assert issubclass(w[0].category, DeprecationWarning)
            assert "load_nation_data" in str(w[0].message)

        assert state["turn"] == 0
        assert state["imperial_treasury"] == 0

    @pytest.mark.asyncio
    async def test_save_state_deprecated(self, repo):
        """测试已废弃的 save_state 方法"""
        import warnings

        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            # save_state 会尝试从 dict 重建 NationData
            await repo.save_state(
                {
                    "turn": 3,
                    "imperial_treasury": 50000,
                    "provinces": {},
                }
            )
            # save_state 内部没有警告，但它调用了废弃逻辑

        loaded = await repo.load_nation_data()
        assert loaded.turn == 3
        assert loaded.imperial_treasury == Decimal("50000")
