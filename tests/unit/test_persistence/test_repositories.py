"""Test GameRepository"""

import pytest
from aiosqlite import Connection

from simu_emperor.persistence.repositories import GameRepository


@pytest.mark.asyncio
async def test_update_province_data_with_dict():
    """Test updating province data with dict value"""
    # 创建内存数据库
    conn = await pytest.importorskip("aiosqlite").connect(":memory:")

    # 创建表
    await conn.execute("""
        CREATE TABLE game_state (
            id INTEGER PRIMARY KEY,
            turn INTEGER,
            state_json TEXT,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # 插入初始状态
    import json

    initial_state = {
        "turn": 1,
        "imperial_treasury": 100000,
        "provinces": [{"province_id": "zhili", "name": "直隶", "taxation": {"land_tax_rate": 0.1}}],
    }
    await conn.execute(
        "INSERT INTO game_state (turn, state_json) VALUES (?, ?)", (1, json.dumps(initial_state))
    )
    await conn.commit()

    # 测试更新
    repo = GameRepository(conn)
    await repo.update_province_data("zhili", "taxation", {"land_tax_rate": 0.05})

    # 验证更新
    state = await repo.load_state()
    zhili = next(p for p in state["provinces"] if p["province_id"] == "zhili")
    assert zhili["taxation"]["land_tax_rate"] == 0.05

    await conn.close()


@pytest.mark.asyncio
async def test_update_province_data_nested():
    """Test updating nested province data"""
    conn = await pytest.importorskip("aiosqlite").connect(":memory:")

    # 创建表
    await conn.execute("""
        CREATE TABLE game_state (
            id INTEGER PRIMARY KEY,
            turn INTEGER,
            state_json TEXT,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # 插入初始状态
    import json

    initial_state = {
        "turn": 1,
        "provinces": [{"province_id": "zhili", "name": "直隶", "taxation": {}}],
    }
    await conn.execute(
        "INSERT INTO game_state (turn, state_json) VALUES (?, ?)", (1, json.dumps(initial_state))
    )
    await conn.commit()

    # 测试更新
    repo = GameRepository(conn)
    await repo.update_province_data("zhili", "taxation.land_tax_rate", 0.08)

    # 验证更新
    state = await repo.load_state()
    zhili = next(p for p in state["provinces"] if p["province_id"] == "zhili")
    assert zhili["taxation"]["land_tax_rate"] == 0.08

    await conn.close()
