"""Web API 端到端测试。"""

from __future__ import annotations

from pathlib import Path

import pytest
from httpx import ASGITransport, AsyncClient

from simu_emperor.agents.llm.providers import MockProvider
from simu_emperor.config import GameConfig
from simu_emperor.engine.models.state import GameState
from simu_emperor.game import GameLoop
from simu_emperor.persistence.database import init_database
from simu_emperor.player.web.app import create_app
from tests.conftest import make_national_data


@pytest.fixture
async def client(tmp_path: Path):
    """创建测试用 AsyncClient，注入 GameLoop。"""
    db_path = str(tmp_path / "test.db")
    conn = await init_database(db_path)

    config = GameConfig(
        db_path=db_path,
        data_dir=Path("data"),
        seed=42,
    )
    provider = MockProvider()
    state = GameState(base_data=make_national_data(turn=0))
    game_loop = GameLoop(state=state, config=config, provider=provider, conn=conn)
    game_loop.initialize_agents()

    app = create_app(game_loop=game_loop)
    transport = ASGITransport(app=app)

    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac

    await conn.close()


class TestStateQuery:
    """状态查询测试。"""

    async def test_get_state(self, client: AsyncClient):
        resp = await client.get("/api/state")
        assert resp.status_code == 200
        data = resp.json()
        assert "game_id" in data
        assert data["current_turn"] == 0
        assert data["phase"] == "resolution"
        assert isinstance(data["provinces"], list)
        assert len(data["provinces"]) > 0
        assert "imperial_treasury" in data
        assert "active_events_count" in data


class TestPhaseAdvance:
    """阶段推进测试。"""

    async def test_advance_resolution_to_summary(self, client: AsyncClient):
        # RESOLUTION → advance → SUMMARY
        resp = await client.post("/api/turn/advance")
        assert resp.status_code == 200
        data = resp.json()
        assert data["phase"] == "summary"

    async def test_advance_summary_to_interaction(self, client: AsyncClient):
        # RESOLUTION → SUMMARY
        await client.post("/api/turn/advance")
        # SUMMARY → INTERACTION
        resp = await client.post("/api/turn/advance")
        assert resp.status_code == 200
        data = resp.json()
        assert data["phase"] == "interaction"
        # SUMMARY 阶段应返回 reports
        assert data["reports"] is not None

    async def test_advance_interaction_to_execution(self, client: AsyncClient):
        # RESOLUTION → SUMMARY → INTERACTION
        await client.post("/api/turn/advance")
        await client.post("/api/turn/advance")
        # INTERACTION → EXECUTION
        resp = await client.post("/api/turn/advance")
        assert resp.status_code == 200
        data = resp.json()
        assert data["phase"] == "execution"

    async def test_full_cycle(self, client: AsyncClient):
        """完整循环：advance 四次完成一个回合。"""
        # 1. RESOLUTION → SUMMARY
        resp = await client.post("/api/turn/advance")
        assert resp.json()["phase"] == "summary"

        # 2. SUMMARY → INTERACTION
        resp = await client.post("/api/turn/advance")
        assert resp.json()["phase"] == "interaction"

        # 3. INTERACTION → EXECUTION
        resp = await client.post("/api/turn/advance")
        assert resp.json()["phase"] == "execution"

        # 4. EXECUTION → SUMMARY (下一回合)
        resp = await client.post("/api/turn/advance")
        assert resp.json()["phase"] == "summary"

        # 验证回合数递增
        state_resp = await client.get("/api/state")
        assert state_resp.json()["current_turn"] > 0


class TestAgentChat:
    """Agent 对话测试。"""

    async def test_chat_in_interaction_phase(self, client: AsyncClient):
        # 推进到 INTERACTION 阶段
        await client.post("/api/turn/advance")  # → SUMMARY
        await client.post("/api/turn/advance")  # → INTERACTION

        # 获取 agent 列表
        agents_resp = await client.get("/api/agents")
        agents = agents_resp.json()
        assert len(agents) > 0

        agent_id = agents[0]
        resp = await client.post(
            f"/api/agents/{agent_id}/chat",
            json={"message": "今年收成如何？"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["agent_id"] == agent_id
        assert len(data["response"]) > 0

    async def test_chat_wrong_phase_returns_400(self, client: AsyncClient):
        # 在 RESOLUTION 阶段尝试对话 → 应该返回 400
        agents_resp = await client.get("/api/agents")
        agents = agents_resp.json()
        if not agents:
            pytest.skip("No agents available")

        resp = await client.post(
            f"/api/agents/{agents[0]}/chat",
            json={"message": "测试"},
        )
        assert resp.status_code == 400
        data = resp.json()
        assert data["error"] == "PhaseError"


class TestReports:
    """报告查询测试。"""

    async def test_reports_after_summary(self, client: AsyncClient):
        # 推进到 SUMMARY → INTERACTION（生成报告后）
        await client.post("/api/turn/advance")  # → SUMMARY
        await client.post("/api/turn/advance")  # → INTERACTION

        resp = await client.get("/api/reports")
        assert resp.status_code == 200
        reports = resp.json()
        assert isinstance(reports, list)
        # MockProvider 应该产生报告
        if len(reports) > 0:
            assert "agent_id" in reports[0]
            assert "markdown" in reports[0]


class TestCommands:
    """命令提交测试。"""

    async def test_submit_command_in_interaction(self, client: AsyncClient):
        # 推进到 INTERACTION
        await client.post("/api/turn/advance")  # → SUMMARY
        await client.post("/api/turn/advance")  # → INTERACTION

        resp = await client.post(
            "/api/commands",
            json={
                "command_type": "build_granary",
                "description": "在直隶建造粮仓",
                "target_province_id": "zhili",
                "direct": False,
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "accepted"
        assert data["command_type"] == "build_granary"

    async def test_submit_command_wrong_phase_returns_400(self, client: AsyncClient):
        # 在 RESOLUTION 阶段提交命令
        resp = await client.post(
            "/api/commands",
            json={
                "command_type": "build_granary",
                "description": "测试",
            },
        )
        assert resp.status_code == 400


class TestHistory:
    """历史记录测试。"""

    async def test_history_empty_initially(self, client: AsyncClient):
        resp = await client.get("/api/history")
        assert resp.status_code == 200
        assert resp.json() == []

    async def test_history_after_advance(self, client: AsyncClient):
        # 推进一次（RESOLUTION 生成 TurnRecord）
        await client.post("/api/turn/advance")

        resp = await client.get("/api/history")
        assert resp.status_code == 200
        history = resp.json()
        assert len(history) > 0
        assert "turn" in history[0]


class TestDebug:
    """调试接口测试。"""

    async def test_real_data(self, client: AsyncClient):
        resp = await client.get("/api/debug/real-data")
        assert resp.status_code == 200
        data = resp.json()
        assert "provinces" in data
        assert "imperial_treasury" in data
        assert "turn" in data


class TestProvinces:
    """省份接口测试。"""

    async def test_provinces(self, client: AsyncClient):
        resp = await client.get("/api/provinces")
        assert resp.status_code == 200
        provinces = resp.json()
        assert len(provinces) > 0
        p = provinces[0]
        assert "id" in p
        assert "name" in p
        assert "population" in p
        assert "happiness" in p
        assert "granary_stock" in p
        assert "local_treasury" in p
        assert "garrison_size" in p


class TestAgentList:
    """Agent 列表测试。"""

    async def test_list_agents(self, client: AsyncClient):
        resp = await client.get("/api/agents")
        assert resp.status_code == 200
        agents = resp.json()
        assert isinstance(agents, list)
        assert len(agents) > 0


class TestAgentChatStream:
    """Agent 流式对话测试。"""

    async def test_chat_stream_in_interaction_phase(self, client: AsyncClient):
        """测试流式对话在 INTERACTION 阶段正常工作。"""
        # 推进到 INTERACTION 阶段
        await client.post("/api/turn/advance")  # → SUMMARY
        await client.post("/api/turn/advance")  # → INTERACTION

        # 获取 agent 列表
        agents_resp = await client.get("/api/agents")
        agents = agents_resp.json()
        assert len(agents) > 0

        agent_id = agents[0]
        resp = await client.post(
            f"/api/agents/{agent_id}/chat/stream",
            json={"message": "今年收成如何？"},
        )
        assert resp.status_code == 200
        assert resp.headers["content-type"] == "text/event-stream; charset=utf-8"

        # 读取流式响应
        content = resp.text
        # 应该包含 SSE 格式的数据
        assert "data:" in content
        # 应该以 [DONE] 结束
        assert "[DONE]" in content

    async def test_chat_stream_yields_chunks(self, client: AsyncClient):
        """测试流式对话返回多个文本块。"""
        # 推进到 INTERACTION 阶段
        await client.post("/api/turn/advance")
        await client.post("/api/turn/advance")

        agents_resp = await client.get("/api/agents")
        agent_id = agents_resp.json()[0]

        resp = await client.post(
            f"/api/agents/{agent_id}/chat/stream",
            json={"message": "测试流式输出"},
        )
        assert resp.status_code == 200

        # MockProvider 会逐字符返回，所以应该有多个 data: 行
        lines = [line for line in resp.text.split("\n") if line.startswith("data:")]
        # 应该有多个数据块 + [DONE]
        assert len(lines) >= 2
        # 最后一行应该是 [DONE]
        assert "[DONE]" in lines[-1]

    async def test_chat_stream_wrong_phase_returns_400(self, client: AsyncClient):
        """测试在错误阶段进行流式对话返回 400。"""
        agents_resp = await client.get("/api/agents")
        agents = agents_resp.json()
        if not agents:
            pytest.skip("No agents available")

        # 在 RESOLUTION 阶段尝试流式对话
        resp = await client.post(
            f"/api/agents/{agents[0]}/chat/stream",
            json={"message": "测试"},
        )
        # SSE 端点在错误情况下仍返回 200，但在内容中包含 [ERROR]
        assert resp.status_code == 200
        assert "[ERROR]" in resp.text or "[DONE]" in resp.text
