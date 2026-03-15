"""Test GameRepository (V4)."""

import pytest
from decimal import Decimal

from simu_emperor.persistence.repositories import GameRepository
from simu_emperor.engine.models.base_data import ProvinceData, NationData


@pytest.mark.asyncio
async def test_save_and_load_nation_data():
    """Test saving and loading NationData."""
    conn = await pytest.importorskip("aiosqlite").connect(":memory:")

    # 创建表
    await conn.execute("""
        CREATE TABLE game_state (
            id INTEGER PRIMARY KEY,
            state_json TEXT,
            created_at TIMESTAMP,
            updated_at TIMESTAMP
        )
    """)
    await conn.commit()

    # 创建测试数据
    nation = NationData(
        turn=5,
        base_tax_rate=Decimal("0.15"),
        imperial_treasury=Decimal("10000"),
        provinces={
            "zhili": ProvinceData(
                province_id="zhili",
                name="直隶",
                production_value=Decimal("100000"),
                population=Decimal("50000"),
                fixed_expenditure=Decimal("5000"),
                stockpile=Decimal("20000"),
            )
        },
    )

    # 保存
    repo = GameRepository(conn)
    await repo.save_nation_data(nation)

    # 加载
    loaded_nation = await repo.load_nation_data()

    assert loaded_nation.turn == 5
    assert loaded_nation.base_tax_rate == Decimal("0.15")
    assert loaded_nation.imperial_treasury == Decimal("10000")
    assert "zhili" in loaded_nation.provinces
    assert loaded_nation.provinces["zhili"].production_value == Decimal("100000")

    await conn.close()


@pytest.mark.asyncio
async def test_get_current_tick():
    """Test getting current tick number."""
    conn = await pytest.importorskip("aiosqlite").connect(":memory:")

    # 创建表
    await conn.execute("""
        CREATE TABLE game_state (
            id INTEGER PRIMARY KEY,
            state_json TEXT,
            created_at TIMESTAMP,
            updated_at TIMESTAMP
        )
    """)

    # 插入初始状态
    import json

    initial_state = {"turn": 10, "imperial_treasury": "50000"}
    await conn.execute(
        "INSERT INTO game_state (id, state_json, created_at, updated_at) VALUES (?, ?, datetime('now'), datetime('now'))",
        (1, json.dumps(initial_state)),
    )
    await conn.commit()

    repo = GameRepository(conn)
    tick = await repo.get_current_tick()

    assert tick == 10

    await conn.close()


@pytest.mark.asyncio
async def test_load_empty_state_returns_default():
    """Test loading when no state exists returns default NationData."""
    conn = await pytest.importorskip("aiosqlite").connect(":memory:")

    # 创建表但不插入数据
    await conn.execute("""
        CREATE TABLE game_state (
            id INTEGER PRIMARY KEY,
            state_json TEXT,
            created_at TIMESTAMP,
            updated_at TIMESTAMP
        )
    """)
    await conn.commit()

    repo = GameRepository(conn)
    nation = await repo.load_nation_data()

    assert nation.turn == 0
    assert nation.provinces == {}

    await conn.close()


@pytest.mark.asyncio
async def test_initialize_default_state():
    """Test initializing default state when none exists."""
    conn = await pytest.importorskip("aiosqlite").connect(":memory:")

    # 创建表
    await conn.execute("""
        CREATE TABLE game_state (
            id INTEGER PRIMARY KEY,
            state_json TEXT,
            created_at TIMESTAMP,
            updated_at TIMESTAMP
        )
    """)
    await conn.commit()

    repo = GameRepository(conn)
    await repo.initialize_default_state()

    # 验证状态已创建
    nation = await repo.load_nation_data()
    assert nation.turn == 0
    assert nation.provinces == {}

    await conn.close()


@pytest.mark.asyncio
async def test_save_state_backward_compat():
    """Test backward compatible save_state method with dict input."""
    conn = await pytest.importorskip("aiosqlite").connect(":memory:")

    # 创建表
    await conn.execute("""
        CREATE TABLE game_state (
            id INTEGER PRIMARY KEY,
            state_json TEXT,
            created_at TIMESTAMP,
            updated_at TIMESTAMP
        )
    """)
    await conn.commit()

    repo = GameRepository(conn)

    # 使用旧的 dict 格式保存
    state_dict = {
        "turn": 3,
        "base_tax_rate": "0.12",
        "imperial_treasury": "8000",
        "provinces": {
            "zhili": {
                "province_id": "zhili",
                "name": "直隶",
                "production_value": "100000",
                "population": "50000",
                "fixed_expenditure": "5000",
                "stockpile": "20000",
            }
        },
    }
    await repo.save_state(state_dict)

    # 验证可以加载
    loaded_nation = await repo.load_nation_data()
    assert loaded_nation.turn == 3
    assert loaded_nation.base_tax_rate == Decimal("0.12")
    assert "zhili" in loaded_nation.provinces

    await conn.close()
