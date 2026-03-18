"""Game Service - Game lifecycle and state management."""

import logging
from pathlib import Path
from typing import TYPE_CHECKING

from simu_emperor.common.utils import FileOperationsHelper
from simu_emperor.config import GameConfig

if TYPE_CHECKING:
    from simu_emperor.persistence.repositories import GameRepository, IncidentRepository
    from simu_emperor.event_bus.core import EventBus
    from simu_emperor.llm.base import LLMProvider
    from simu_emperor.engine.engine import Engine
    from simu_emperor.engine.tick_coordinator import TickCoordinator
    from simu_emperor.engine.models.base_data import NationData


logger = logging.getLogger(__name__)


class GameService:
    """Game business service.

    Responsibilities:
    - Game instance lifecycle management
    - Game state initialization and loading
    - Engine and TickCoordinator coordination
    """

    def __init__(
        self,
        settings: GameConfig,
        repository: "GameRepository",
        event_bus: "EventBus",
        llm_provider: "LLMProvider",
        memory_dir: Path,
        incident_repo: "IncidentRepository | None" = None,
    ) -> None:
        """Initialize GameService.

        Args:
            settings: Game configuration
            repository: Game state repository
            event_bus: Event bus for pub/sub
            llm_provider: LLM provider for AI
            memory_dir: Memory storage directory
            incident_repo: Incident persistence repository (optional)
        """
        self.settings = settings
        self.repository = repository
        self.event_bus = event_bus
        self.llm_provider = llm_provider
        self.memory_dir = memory_dir
        self.incident_repo = incident_repo

        # Core components (lazy initialized)
        self._engine: "Engine | None" = None
        self._tick_coordinator: "TickCoordinator | None" = None
        self._running: bool = False

    async def initialize(self) -> None:
        """Initialize the game engine and start tick progression.

        Loads initial state and starts the tick coordinator.
        """
        if self._running:
            logger.warning("GameService already running")
            return

        logger.info("Initializing GameService...")

        # Load initial game state
        initial_state = await self._load_initial_state()

        # Initialize Engine
        from simu_emperor.engine.engine import Engine
        self._engine = Engine(initial_state, self.event_bus)
        logger.info("Engine initialized")

        # Load active incidents from persistence
        if self.incident_repo:
            active_incidents = await self.incident_repo.load_active_incidents()
            for inc in active_incidents:
                self._engine.add_incident(inc)
            if active_incidents:
                logger.info(f"Loaded {len(active_incidents)} active incidents from DB")

        # Initialize and start TickCoordinator
        from simu_emperor.engine.tick_coordinator import TickCoordinator
        self._tick_coordinator = TickCoordinator(
            self.event_bus, self._engine, self.repository,
            incident_repo=self.incident_repo,
        )
        await self._tick_coordinator.start()
        logger.info("TickCoordinator started")

        self._running = True
        logger.info("GameService initialized successfully")

    async def shutdown(self) -> None:
        """Shutdown the game service.

        Stops the tick coordinator.
        """
        if not self._running:
            return

        logger.info("Shutting down GameService...")

        if self._tick_coordinator:
            await self._tick_coordinator.stop()

        self._running = False
        logger.info("GameService shut down")

    async def get_state(self) -> "NationData":
        """Get current game state.

        Returns:
            Current nation data
        """
        if self._engine:
            return self._engine.get_state()
        return await self._load_state_from_repository()

    async def get_overview(self) -> dict:
        """Get empire overview summary (V4 design).

        Returns:
            Dict with turn, treasury, population, province_count, treasury_delta, population_delta
        """
        if not self.repository:
            return {
                "turn": 0,
                "treasury": 0,
                "population": 0,
                "province_count": 0,
                "treasury_delta": 0,
                "population_delta": 0,
            }

        # V4: 使用 load_nation_data() 获取 NationData 对象
        from dataclasses import asdict
        from simu_emperor.persistence.serialization import _decimal_to_str

        nation = await self.repository.load_nation_data()
        state = _decimal_to_str(asdict(nation))
        return self._calculate_overview(state)

    def _calculate_overview(self, state: dict) -> dict:
        """Calculate overview from state dict (V4 format)."""

        def _to_number(value, default: float = 0.0) -> float:
            if value is None:
                return default
            if isinstance(value, (int, float)):
                return float(value)
            try:
                return float(str(value))
            except (TypeError, ValueError):
                return default

        def _get_provinces_dict(state_dict: dict) -> dict:
            """获取 provinces 字典（V4 格式）"""
            provinces = state_dict.get("provinces")
            if isinstance(provinces, dict):
                return provinces
            base_data = state_dict.get("base_data", {})
            if isinstance(base_data, dict):
                provinces = base_data.get("provinces")
                if isinstance(provinces, dict):
                    return provinces
            return {}

        # Get turn
        turn = int(_to_number(state.get("turn", 0)))
        if turn == 0:
            base_data = state.get("base_data", {})
            if isinstance(base_data, dict):
                turn = int(_to_number(base_data.get("turn", 0)))

        # Get treasury
        treasury = _to_number(state.get("imperial_treasury", 0))
        if treasury == 0:
            base_data = state.get("base_data", {})
            if isinstance(base_data, dict):
                treasury = _to_number(base_data.get("imperial_treasury", 0))

        # Calculate totals from provinces (V4 扁平结构)
        provinces_dict = _get_provinces_dict(state)
        population_total = 0.0

        for province_id, province in provinces_dict.items():
            if not isinstance(province, dict):
                continue
            # V4: province.population 直接是数字，不是嵌套对象
            population_total += _to_number(province.get("population", 0))

        # Calculate deltas using engine
        treasury_delta = 0
        population_delta = 0
        if self._engine:
            try:
                treasury_delta = float(self._engine.get_province_delta("_nation", "imperial_treasury"))
                population_delta = float(self._engine.get_province_delta("_nation", "population"))
            except Exception as e:
                logger.debug(f"Failed to get deltas from engine: {e}")

        return {
            "turn": turn,
            "treasury": int(treasury),
            "population": int(population_total),
            "province_count": len(provinces_dict),
            "treasury_delta": treasury_delta,
            "population_delta": population_delta,
        }

    async def _load_initial_state(self) -> "NationData":
        """Load initial game state from JSON config.

        Returns:
            Initial NationData
        """
        from decimal import Decimal
        from simu_emperor.engine.models.base_data import NationData, ProvinceData

        config_path = self.settings.data_dir / "initial_state_v4.json"
        logger.info(f"Loading initial state from {config_path}")

        config_data = await FileOperationsHelper.read_json_file(config_path)
        if not config_data:
            logger.warning("Failed to load initial state, using fallback defaults")
            return self._get_fallback_state()

        # Load from config
        nation_config = config_data.get("nation", {})
        provinces_config = config_data.get("provinces", {})

        provinces_data = {}
        for province_id, province_config in provinces_config.items():
            provinces_data[province_id] = ProvinceData(
                province_id=province_config.get("province_id", province_id),
                name=province_config.get("name", province_id),
                production_value=Decimal(province_config.get("production_value", "100000")),
                population=Decimal(province_config.get("population", "1000000")),
                fixed_expenditure=Decimal(province_config.get("fixed_expenditure", "0")),
                stockpile=Decimal(province_config.get("stockpile", "0")),
                base_production_growth=Decimal(province_config.get("base_production_growth", "0.01")),
                base_population_growth=Decimal(province_config.get("base_population_growth", "0.005")),
                tax_modifier=Decimal(province_config.get("tax_modifier", "0.0")),
            )

        return NationData(
            turn=int(nation_config.get("turn", 0)),
            base_tax_rate=Decimal(nation_config.get("base_tax_rate", "0.10")),
            tribute_rate=Decimal(nation_config.get("tribute_rate", "0.8")),
            fixed_expenditure=Decimal(nation_config.get("fixed_expenditure", "0")),
            imperial_treasury=Decimal(nation_config.get("imperial_treasury", "100000")),
            provinces=provinces_data,
        )

    def _get_fallback_state(self) -> "NationData":
        """Get hardcoded fallback state."""
        from decimal import Decimal
        from simu_emperor.engine.models.base_data import NationData, ProvinceData

        provinces_data = {
            "zhili": ProvinceData(
                province_id="zhili",
                name="直隶",
                production_value=Decimal("100000"),
                population=Decimal("2600000"),
                fixed_expenditure=Decimal("50000"),
                stockpile=Decimal("1200000"),
            )
        }
        return NationData(
            turn=0,
            base_tax_rate=Decimal("0.10"),
            tribute_rate=Decimal("0.8"),
            fixed_expenditure=Decimal("0"),
            imperial_treasury=Decimal("100000"),
            provinces=provinces_data,
        )

    async def _load_state_from_repository(self) -> "NationData":
        """Load state from repository when engine not available.

        Returns:
            NationData from repository or fallback empty state
        """
        from decimal import Decimal
        from simu_emperor.engine.models.base_data import NationData

        try:
            # V4: 直接使用 load_nation_data() 返回 NationData
            return await self.repository.load_nation_data()
        except Exception as e:
            logger.error(f"Failed to load state from repository: {e}")
            return NationData(
                turn=0,
                base_tax_rate=Decimal("0.10"),
                imperial_treasury=Decimal("0"),
                provinces={},
            )

    @property
    def engine(self) -> "Engine | None":
        """Get the engine instance."""
        return self._engine

    @property
    def tick_coordinator(self) -> "TickCoordinator | None":
        """Get the tick coordinator instance."""
        return self._tick_coordinator

    @property
    def is_running(self) -> bool:
        """Check if the game service is running."""
        return self._running
