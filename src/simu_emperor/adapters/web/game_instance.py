"""
游戏实例管理

Web 模式的游戏实例管理器（单例，全局共享）。
"""

import logging
from datetime import datetime, timezone
from pathlib import Path
import uuid

from simu_emperor.common.file_utils import FileOperationsHelper
from simu_emperor.config import GameConfig
from simu_emperor.event_bus.core import EventBus
from simu_emperor.event_bus.event import Event
from simu_emperor.event_bus.event_types import EventType
from simu_emperor.event_bus.logger import FileEventLogger, DatabaseEventLogger
from simu_emperor.persistence import init_database, close_database
from simu_emperor.persistence.repositories import GameRepository
from simu_emperor.engine.coordinator import TurnCoordinator
from simu_emperor.agents.manager import AgentManager
from simu_emperor.memory.manifest_index import ManifestIndex
from simu_emperor.llm.base import LLMProvider
from simu_emperor.llm.anthropic import AnthropicProvider
from simu_emperor.llm.openai import OpenAIProvider
from simu_emperor.llm.mock import MockProvider


logger = logging.getLogger(__name__)


class WebGameInstance:
    """
    Web 模式的游戏实例管理器

    单例模式，所有 WebSocket 连接共享同一个游戏实例。

    职责：
    - 单例模式（全局共享，不同于 telegram 的多会话）
    - 参考 telegram adapter 的 GameSession 初始化逻辑
    - 生命周期管理

    Attributes:
        settings: 游戏配置
        player_id: 玩家 ID（"player:web"）
        session_id: 会话 ID（"session:web:main"）
        db_path: 数据库路径
        event_bus: 事件总线
        repository: 数据库仓储
        calculator: 游戏状态管理器
        agent_manager: Agent 管理器
        llm_provider: LLM 提供商
        _running: 运行状态标志
    """

    def __init__(self, settings: GameConfig) -> None:
        """
        初始化游戏实例管理器

        Args:
            settings: 游戏配置
        """
        self.settings = settings
        self.player_id = "player:web"
        self.session_id = "session:web:main"
        self.current_agent_id: str | None = "governor_zhili"
        self._session_ids: set[str] = {self.session_id}
        self._session_titles: dict[str, str] = {self.session_id: "主会话"}
        self._current_session_by_agent: dict[str, str] = {"governor_zhili": self.session_id}

        # 数据库路径（共享，而非每个会话独立）
        self.db_path = str(settings.data_dir / "game.db")
        self.memory_dir = self._resolve_memory_dir()
        self._manifest_index = ManifestIndex(self.memory_dir)

        # 延迟初始化的组件
        self.event_bus: EventBus | None = None
        self.repository: GameRepository | None = None
        self.calculator: TurnCoordinator | None = None
        self.agent_manager: AgentManager | None = None
        self.llm_provider: LLMProvider | None = None
        self.session_manager = None  # SessionManager for task sessions
        self._running: bool = False

        logger.info("WebGameInstance created")

    def _resolve_memory_dir(self) -> Path:
        """解析记忆目录路径（兼容测试 MockSettings）。"""
        configured = getattr(getattr(self.settings, "memory", None), "memory_dir", None)
        if configured:
            path = Path(configured)
            return path if path.is_absolute() else path.resolve()
        return self.settings.data_dir / "memory"

    def create_llm_provider(self) -> LLMProvider:
        """
        创建 LLM Provider（根据配置）

        Returns:
            LLM Provider 实例
        """
        config = self.settings.llm

        if config.provider == "anthropic":
            return AnthropicProvider(api_key=config.api_key)
        elif config.provider == "openai":
            return OpenAIProvider(
                api_key=config.api_key, model=config.get_model(), base_url=config.api_base
            )
        else:  # mock
            return MockProvider()

    async def start(self) -> None:
        """
        启动游戏实例

        初始化顺序（参考 telegram adapter 的 GameSession.start()）：
        1. LLM Provider
        2. Database + Repository
        3. EventBus（带日志）
        4. AgentManager
        5. Calculator
        """
        if self._running:
            logger.warning("WebGameInstance already running")
            return

        logger.info("Starting WebGameInstance...")

        # 1. 初始化 LLM Provider
        self.llm_provider = self.create_llm_provider()
        logger.info(f"LLM provider initialized: {self.settings.llm.provider}")

        # 2. 初始化数据库
        conn = await init_database(self.db_path)
        self.repository = GameRepository(conn)
        logger.info(f"Database initialized: {self.db_path}")

        # 2.5. 初始化游戏状态（如果为空）
        await self._initialize_game_state()

        # 3. 初始化 EventBus（带日志）
        log_dir = self.settings.log_dir / "events"
        log_dir.mkdir(parents=True, exist_ok=True)

        file_logger = FileEventLogger(log_dir)
        db_logger = DatabaseEventLogger(conn)

        self.event_bus = EventBus(file_logger=file_logger, db_logger=db_logger)

        # 订阅响应事件
        self.event_bus.subscribe(self.player_id, self._on_response)
        # 订阅回合结算完成事件
        self.event_bus.subscribe(self.player_id, self._on_turn_resolved)

        logger.info("EventBus initialized")

        # 3.5. 初始化 SessionManager (for task sessions)
        from simu_emperor.session.manager import SessionManager
        from simu_emperor.memory.tape_writer import TapeWriter

        tape_writer = TapeWriter(memory_dir=self.memory_dir)
        self.session_manager = SessionManager(
            memory_dir=self.memory_dir,
            llm_provider=self.llm_provider,
            manifest_index=self._manifest_index,
            tape_writer=tape_writer,
        )

        if not await self.session_manager.get_session(self.session_id):
            await self.session_manager.create_session(
                session_id=self.session_id,
                created_by="system:web",
                status="ACTIVE",
            )
        logger.info(f"SessionManager initialized with main session: {self.session_id}")

        # 4. 初始化 AgentManager（在 Calculator 之前）
        agent_dir = self.settings.data_dir / "agent" / "web"
        agent_dir.mkdir(parents=True, exist_ok=True)

        self.agent_manager = AgentManager(
            event_bus=self.event_bus,
            llm_provider=self.llm_provider,
            template_dir=self.settings.data_dir / "default_agents",
            agent_dir=str(agent_dir),
            repository=self.repository,
            session_id=self.session_id,
            session_manager=self.session_manager,
        )

        # 初始化并启动默认 agents
        default_agents = ["governor_zhili", "minister_of_revenue"]
        for agent_id in default_agents:
            if self.agent_manager.initialize_agent(agent_id):
                self.agent_manager.add_agent(agent_id)
                logger.info(f"Agent {agent_id} started")

        logger.info(f"AgentManager initialized with {len(default_agents)} agents")
        active_agents = self.agent_manager.get_active_agents()
        available_agents = self.get_available_agents()
        if available_agents:
            self.current_agent_id = available_agents[0]
            for agent_id in available_agents:
                self._current_session_by_agent.setdefault(agent_id, self.session_id)
        await self._ensure_session_registered(self.session_id, agent_ids=active_agents)

        # 5. 初始化 Calculator（传入 AgentManager）
        self.calculator = TurnCoordinator(self.event_bus, self.repository, self.agent_manager)
        self.calculator.start()
        logger.info("Calculator started")

        self._running = True
        logger.info("WebGameInstance started successfully")

    async def shutdown(self) -> None:
        """关闭游戏实例"""
        if not self._running:
            return

        logger.info("Shutting down WebGameInstance...")

        if self.agent_manager:
            self.agent_manager.stop_all()

        if self.calculator:
            self.calculator.stop()

        if self.repository:
            await close_database()

        self._running = False
        logger.info("WebGameInstance shut down")

    @staticmethod
    def _to_number(value, default: float = 0.0) -> float:
        """将状态字段转换为数值（兼容 str/Decimal/int/float）。"""
        if value is None:
            return default
        if isinstance(value, (int, float)):
            return float(value)
        try:
            return float(str(value))
        except (TypeError, ValueError):
            return default

    def _get_provinces(self, state: dict) -> list[dict]:
        """兼容不同状态结构，返回省份数组。"""
        provinces = state.get("provinces")
        if isinstance(provinces, list):
            return provinces
        base_data = state.get("base_data", {})
        if isinstance(base_data, dict):
            provinces = base_data.get("provinces")
            if isinstance(provinces, list):
                return provinces
        return []

    async def get_empire_overview(self) -> dict:
        """
        获取帝国概况（前端状态面板使用）。
        """
        if not self.repository:
            return {
                "turn": 0,
                "treasury": 0,
                "population": 0,
                "military": 0,
                "happiness": 0.0,
                "province_count": 0,
            }

        state = await self.repository.load_state()
        provinces = self._get_provinces(state)

        turn = int(self._to_number(state.get("turn", 0)))
        if turn == 0:
            base_data = state.get("base_data", {})
            if isinstance(base_data, dict):
                turn = int(self._to_number(base_data.get("turn", 0)))

        treasury = self._to_number(state.get("imperial_treasury", 0))
        if treasury == 0:
            base_data = state.get("base_data", {})
            if isinstance(base_data, dict):
                treasury = self._to_number(base_data.get("imperial_treasury", 0))

        population_total = 0.0
        military_total = 0.0
        happiness_values: list[float] = []

        for province in provinces:
            if not isinstance(province, dict):
                continue
            population = province.get("population", {})
            military = province.get("military", {})
            if isinstance(population, dict):
                population_total += self._to_number(population.get("total", 0))
                happiness = self._to_number(population.get("happiness", 0))
                # 数据源通常为 0~1，前端展示百分比
                if 0 < happiness <= 1:
                    happiness *= 100
                if happiness > 0:
                    happiness_values.append(happiness)
            if isinstance(military, dict):
                military_total += self._to_number(military.get("soldiers", 0))

        avg_happiness = sum(happiness_values) / len(happiness_values) if happiness_values else 0.0

        return {
            "turn": turn,
            "treasury": int(treasury),
            "population": int(population_total),
            "military": int(military_total),
            "happiness": round(avg_happiness, 1),
            "province_count": len(provinces),
        }

    @staticmethod
    def _get_agent_display_name(agent_id: str) -> str:
        mapping = {
            "governor_zhili": "直隶巡抚",
            "minister_of_revenue": "户部尚书",
        }
        return mapping.get(agent_id, agent_id)

    def get_active_agents(self) -> list[str]:
        """获取活跃 agent 列表。"""
        if self.agent_manager:
            return self.agent_manager.get_active_agents()
        return []

    def get_available_agents(self) -> list[str]:
        """获取所有可用 agent（活跃 + 工作目录 + 模板目录 + memory 目录）。"""
        available: set[str] = set(self.get_active_agents())

        if self.agent_manager:
            available.update(self.agent_manager.get_all_agents())

        template_root = self.settings.data_dir / "default_agents"
        if template_root.exists():
            for agent_dir in template_root.iterdir():
                if agent_dir.is_dir():
                    available.add(agent_dir.name)

        memory_agents = self.memory_dir / "agents"
        if memory_agents.exists():
            for agent_dir in memory_agents.iterdir():
                if agent_dir.is_dir():
                    available.add(agent_dir.name)

        available.update(self._current_session_by_agent.keys())
        return sorted(available)

    def _normalize_agent_id(self, agent_id: str | None) -> str:
        if agent_id:
            return agent_id.replace("agent:", "")
        if self.current_agent_id:
            return self.current_agent_id
        available_agents = self.get_available_agents()
        if available_agents:
            return available_agents[0]
        return "governor_zhili"

    def get_session_for_agent(self, agent_id: str | None) -> str:
        normalized = self._normalize_agent_id(agent_id)
        return self._current_session_by_agent.get(normalized, self.session_id)

    async def _ensure_session_registered(
        self, session_id: str, agent_ids: list[str] | None = None
    ) -> None:
        """
        在 manifest 中注册 session（仅缺失时注册，避免覆盖历史元数据）。
        """
        self._session_ids.add(session_id)

        target_agents = [self._normalize_agent_id(agent) for agent in (agent_ids or [])]
        if not target_agents:
            target_agents = self.get_available_agents()
        if not target_agents:
            return

        turn = 0
        if self.repository:
            turn = await self.repository.get_current_turn()

        manifest = (
            await FileOperationsHelper.read_json_file(self.memory_dir / "manifest.json") or {}
        )
        existing_agents = (
            manifest.get("sessions", {}).get(session_id, {}).get("agents", {})
            if isinstance(manifest, dict)
            else {}
        )

        for agent_id in target_agents:
            if agent_id in existing_agents:
                continue
            await self._manifest_index.register_session(session_id, agent_id, turn)

    def _set_current_context(self, agent_id: str, session_id: str) -> None:
        """切换当前会话上下文（agent + session）。"""
        normalized_agent = self._normalize_agent_id(agent_id)
        self.current_agent_id = normalized_agent
        self.session_id = session_id
        self._session_ids.add(session_id)
        self._current_session_by_agent[normalized_agent] = session_id

        if self.agent_manager:
            self.agent_manager.session_id = session_id
            agent = self.agent_manager.get_agent(normalized_agent)
            if agent is not None:
                setattr(agent, "session_id", session_id)

    def set_current_context(self, agent_id: str, session_id: str) -> None:
        """公开方法：切换当前会话上下文。"""
        self._set_current_context(agent_id, session_id)

    async def create_session(self, name: str | None = None, agent_id: str | None = None) -> dict:
        """为指定 agent 创建会话并切换。"""
        normalized_agent = self._normalize_agent_id(agent_id)
        now = datetime.now(timezone.utc)
        stamp = now.strftime("%Y%m%d%H%M%S")
        suffix = uuid.uuid4().hex[:6]
        session_id = f"session:web:{normalized_agent}:{stamp}:{suffix}"
        default_title = f"{self._get_agent_display_name(normalized_agent)}会话 {stamp}"
        title = name.strip() if name and name.strip() else default_title
        self._session_titles[session_id] = title

        await self._ensure_session_registered(session_id, agent_ids=[normalized_agent])
        self._set_current_context(normalized_agent, session_id)

        return {
            "session_id": session_id,
            "title": title,
            "created_at": now.isoformat(),
            "is_current": True,
            "event_count": 0,
            "agents": [normalized_agent],
            "agent_id": normalized_agent,
        }

    async def _find_agent_for_session(self, session_id: str) -> str | None:
        for group in await self.list_agent_sessions():
            for session in group["sessions"]:
                if session["session_id"] == session_id:
                    return group["agent_id"]
        return None

    async def select_session(self, session_id: str, agent_id: str | None = None) -> dict:
        """切换到指定 agent 的指定会话。"""
        normalized_agent = self._normalize_agent_id(agent_id)
        if not agent_id:
            detected_agent = await self._find_agent_for_session(session_id)
            if not detected_agent and session_id in self._session_ids and self.current_agent_id:
                detected_agent = self.current_agent_id
            if not detected_agent:
                raise ValueError(f"Session not found: {session_id}")
            normalized_agent = detected_agent

        agent_sessions = await self.list_agent_sessions()
        matched = False
        for group in agent_sessions:
            if group["agent_id"] != normalized_agent:
                continue
            matched = any(s["session_id"] == session_id for s in group["sessions"])
            break
        if not matched and session_id not in self._session_ids:
            raise ValueError(f"Session not found: {session_id} for agent {normalized_agent}")

        self._set_current_context(normalized_agent, session_id)
        return {"session_id": session_id, "is_current": True, "agent_id": normalized_agent}

    def _iter_session_tape_paths(self, session_id: str, agent_id: str | None = None) -> list[Path]:
        """获取 session 的 tape 路径。"""
        normalized_agent = self._normalize_agent_id(agent_id) if agent_id else None
        if normalized_agent:
            tape_path = (
                self.memory_dir
                / "agents"
                / normalized_agent
                / "sessions"
                / session_id
                / "tape.jsonl"
            )
            return [tape_path] if tape_path.exists() else []

        agent_root = self.memory_dir / "agents"
        if not agent_root.exists():
            return []

        paths: list[Path] = []
        for agent_dir in agent_root.iterdir():
            if not agent_dir.is_dir():
                continue
            tape_path = agent_dir / "sessions" / session_id / "tape.jsonl"
            if tape_path.exists():
                paths.append(tape_path)
        return paths

    async def get_current_tape(
        self,
        limit: int = 100,
        agent_id: str | None = None,
        session_id: str | None = None,
    ) -> dict:
        """读取当前（或指定）agent/session 的 tape 内容。"""
        normalized_agent = self._normalize_agent_id(agent_id) if agent_id else self.current_agent_id
        target_session_id = session_id or self.session_id
        events: list[dict] = []

        tape_paths = self._iter_session_tape_paths(target_session_id, normalized_agent)
        if not tape_paths and normalized_agent is None:
            tape_paths = self._iter_session_tape_paths(target_session_id)

        for tape_path in tape_paths:
            current_agent_id = tape_path.parent.parent.parent.name
            tape_events = await FileOperationsHelper.read_jsonl_file(tape_path)
            for event in tape_events:
                event["agent_id"] = current_agent_id
                events.append(event)

        events.sort(key=lambda item: item.get("timestamp", ""))
        total_events = len(events)
        if limit > 0:
            events = events[-limit:]

        return {
            "agent_id": normalized_agent,
            "session_id": target_session_id,
            "events": events,
            "total": total_events,
        }

    async def list_agent_sessions(self) -> list[dict]:
        """按 agent 列出会话。"""
        manifest = (
            await FileOperationsHelper.read_json_file(self.memory_dir / "manifest.json") or {}
        )
        manifest_sessions = manifest.get("sessions", {}) if isinstance(manifest, dict) else {}

        agent_ids = set(self.get_available_agents())
        agent_root = self.memory_dir / "agents"
        if agent_root.exists():
            for agent_dir in agent_root.iterdir():
                if agent_dir.is_dir():
                    agent_ids.add(agent_dir.name)
        agent_ids.update(self._current_session_by_agent.keys())

        grouped: list[dict] = []
        for agent_id in sorted(agent_ids):
            session_map: dict[str, dict] = {}

            for session_id, session_data in manifest_sessions.items():
                agent_data = session_data.get("agents", {}).get(agent_id)
                if not agent_data:
                    continue
                session_map[session_id] = {
                    "session_id": session_id,
                    "title": self._session_titles.get(session_id, session_id),
                    "created_at": agent_data.get("start_time"),
                    "updated_at": agent_data.get("end_time"),
                    "event_count": int(self._to_number(agent_data.get("event_count", 0))),
                    "agents": [agent_id],
                    "is_current": (
                        session_id == self.get_session_for_agent(agent_id)
                        and agent_id == self.current_agent_id
                    ),
                }

            sessions_dir = agent_root / agent_id / "sessions"
            if sessions_dir.exists():
                for session_dir in sessions_dir.iterdir():
                    if not session_dir.is_dir():
                        continue
                    session_id = session_dir.name
                    session_map.setdefault(
                        session_id,
                        {
                            "session_id": session_id,
                            "title": self._session_titles.get(session_id, session_id),
                            "created_at": None,
                            "updated_at": None,
                            "event_count": 0,
                            "agents": [agent_id],
                            "is_current": (
                                session_id == self.get_session_for_agent(agent_id)
                                and agent_id == self.current_agent_id
                            ),
                        },
                    )

            current_session = self._current_session_by_agent.get(agent_id)
            if current_session and current_session not in session_map:
                session_map[current_session] = {
                    "session_id": current_session,
                    "title": self._session_titles.get(current_session, current_session),
                    "created_at": None,
                    "updated_at": None,
                    "event_count": 0,
                    "agents": [agent_id],
                    "is_current": (
                        current_session == self.get_session_for_agent(agent_id)
                        and agent_id == self.current_agent_id
                    ),
                }

            sessions = list(session_map.values())
            sessions.sort(
                key=lambda item: (
                    item.get("updated_at") or item.get("created_at") or "",
                    item["session_id"],
                ),
                reverse=True,
            )

            grouped.append(
                {
                    "agent_id": agent_id,
                    "agent_name": self._get_agent_display_name(agent_id),
                    "sessions": sessions,
                }
            )

        return grouped

    async def list_sessions(self) -> list[dict]:
        """
        列出所有可选 session（扁平结构，兼容旧接口）。
        """
        grouped = await self.list_agent_sessions()
        sessions: dict[str, dict] = {}

        for group in grouped:
            agent_id = group["agent_id"]
            for session in group["sessions"]:
                session_id = session["session_id"]
                if session_id not in sessions:
                    sessions[session_id] = {
                        "session_id": session_id,
                        "title": session["title"],
                        "created_at": session.get("created_at"),
                        "updated_at": session.get("updated_at"),
                        "event_count": session.get("event_count", 0),
                        "agents": [],
                        "is_current": session_id == self.session_id,
                    }
                sessions[session_id]["agents"].append(agent_id)

        for session_id in self._session_ids:
            if session_id not in sessions:
                sessions[session_id] = {
                    "session_id": session_id,
                    "title": self._session_titles.get(session_id, session_id),
                    "created_at": None,
                    "updated_at": None,
                    "event_count": 0,
                    "agents": [],
                    "is_current": session_id == self.session_id,
                }

        session_list = list(sessions.values())
        session_list.sort(
            key=lambda item: (
                item.get("updated_at") or item.get("created_at") or "",
                item["session_id"],
            ),
            reverse=True,
        )
        return session_list

    async def _initialize_game_state(self) -> None:
        """
        初始化游戏状态（如果数据库为空）

        检查数据库中是否有游戏状态，如果没有则创建初始状态。
        参考 telegram adapter 的实现。
        """
        # 检查是否已有数据
        state = await self.repository.load_state()

        if state.get("provinces"):
            logger.info("Game state already initialized")
            return

        # 创建初始游戏状态
        from simu_emperor.engine.models.base_data import (
            ProvinceBaseData,
            NationalBaseData,
            PopulationData,
            AgricultureData,
            CommerceData,
            TradeData,
            MilitaryData,
            TaxationData,
            ConsumptionData,
            AdministrationData,
            CropData,
            CropType,
        )
        from decimal import Decimal

        # 创建直隶省
        zhili = ProvinceBaseData(
            province_id="zhili",
            name="直隶",
            population=PopulationData(
                total=Decimal("2600000"),
                happiness=Decimal("0.7"),
                growth_rate=Decimal("0.002"),
                labor_ratio=Decimal("0.55"),
            ),
            agriculture=AgricultureData(
                irrigation_level=Decimal("0.3"),
                crops=[
                    CropData(
                        crop_type=CropType.WHEAT,
                        area_mu=Decimal("300000"),
                        yield_per_mu=Decimal("1.3"),
                    ),
                    CropData(
                        crop_type=CropType.RICE,
                        area_mu=Decimal("100000"),
                        yield_per_mu=Decimal("3"),
                    ),
                ],
            ),
            commerce=CommerceData(
                merchant_households=Decimal("150000"),
                market_prosperity=Decimal("0.7"),
            ),
            trade=TradeData(
                trade_volume=Decimal("500000"),
                trade_route_quality=Decimal("0.6"),
            ),
            military=MilitaryData(
                soldiers=Decimal("50000"),
                morale=Decimal("0.7"),
                garrison_size=Decimal("30000"),
                equipment_level=Decimal("0.5"),
                upkeep_per_soldier=Decimal("3"),
            ),
            taxation=TaxationData(
                land_tax_rate=Decimal("0.03"),
                commercial_tax_rate=Decimal("0.05"),
                tariff_rate=Decimal("0.1"),
            ),
            consumption=ConsumptionData(
                civilian_grain_per_capita=Decimal("3"),
                military_grain_per_soldier=Decimal("5"),
            ),
            administration=AdministrationData(
                official_count=Decimal("5000"),
                official_salary=Decimal("20"),
                infrastructure_value=Decimal("0.5"),
            ),
            granary_stock=Decimal("1200000"),
            local_treasury=Decimal("80000"),
        )

        # 创建初始国家数据
        initial_state = NationalBaseData(
            turn=0,
            provinces=[zhili],
            imperial_treasury=Decimal("100000"),
            national_tax_modifier=Decimal("1.0"),
            tribute_rate=Decimal("0.1"),
        )

        # 保存到数据库（使用 JSON 序列化模式）
        state_dict = initial_state.model_dump(mode="json")
        await self.repository.save_state(state_dict)

        logger.info(f"Initialized game state with {len(initial_state.provinces)} province(s)")

    async def _on_response(self, event: Event) -> None:
        """
        处理 Agent 响应事件

        Args:
            event: 响应事件
        """
        if event.type != EventType.RESPONSE:
            return

        agent_name = event.src.replace("agent:", "")
        narrative = event.payload.get("narrative", "")

        logger.info(f"📨 Received response from {agent_name}: {narrative[:50]}...")
        # 注意：实际的 WebSocket 发送由 server.py 中的事件监听器处理

    async def _on_turn_resolved(self, event: Event) -> None:
        """
        回合结算事件处理器

        Args:
            event: 回合结算事件
        """
        turn = event.payload.get("turn")
        logger.info(f"🔄 Turn {turn} resolved")
        # 注意：实际的 WebSocket 发送由 server.py 中的事件监听器处理
