"""
PerceptionAgent - First stage in Province Agent pipeline

Responsibilities:
- Read and organize historical data
- Build layered summaries (monthly/quarterly/annual)
- Index critical events
- Analyze trends and risks
- Generate LLM-powered summaries
"""

import json
from typing import List, Dict, Any, Optional
from agents.base import BaseAgent
from agents.province.models import (
    PerceptionContext, MonthlyDetailedData, QuarterlySummary,
    AnnualSummary, EventIndex, TrendAnalysis, TrendDirection, RiskLevel,
    EventSummary
)
from db.database import Database


class PerceptionAgent(BaseAgent):
    """
    PerceptionAgent - First stage in Province Agent pipeline

    Responsible for:
    - Reading and organizing historical data
    - Building layered summaries (monthly/quarterly/annual)
    - Indexing critical events
    - Analyzing trends and providing structured context to DecisionAgent
    """

    def __init__(self, agent_id: str, config: Dict[str, Any], db: Database):
        """
        Initialize PerceptionAgent

        Args:
            agent_id: Unique agent identifier
            config: Configuration dict with llm_config
            db: Database instance
        """
        super().__init__(agent_id, config)
        self.db = db
        self.province_id = config.get('province_id')

    async def initialize(self, config: Dict[str, Any]) -> None:
        """Initialize agent (called after creation)"""
        pass

    async def on_month_start(self, game_state: Dict[str, Any], provinces: List[Dict[str, Any]]) -> None:
        """Called at month start (not used in perception phase)"""
        pass

    async def take_action(self, context: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Execute action (not used in perception phase)"""
        return None

    def get_state(self) -> Dict[str, Any]:
        """Get agent state"""
        return {
            'agent_id': self.agent_id,
            'province_id': self.province_id,
            'mode': self.mode.value,
            'llm_enabled': self.llm_config.enabled
        }

    # ========== Main Perception Method ==========

    async def perceive(
        self,
        province_id: int,
        current_month: int,
        current_year: int
    ) -> PerceptionContext:
        """
        Main perception entry point

        Args:
            province_id: Province identifier
            current_month: Current game month (1-indexed)
            current_year: Current year

        Returns:
            PerceptionContext with layered historical data
        """
        # Step 1: Build monthly detailed data (last month)
        recent_data = await self._build_monthly_detailed(
            province_id, current_month - 1, current_year
        )

        # Step 2: Build quarterly summaries (last 4 quarters)
        quarterly_summaries = await self._build_quarterly_summaries(
            province_id, current_month, current_year
        )

        # Step 3: Build annual summaries (last 3 years)
        annual_summaries = await self._build_annual_summaries(
            province_id, current_year
        )

        # Step 4: Index critical events
        critical_events = await self._index_critical_events(
            province_id, months_lookback=12
        )

        # Step 5: Analyze trends
        trends = await self._analyze_trends(
            recent_data, quarterly_summaries, annual_summaries
        )

        # Step 6: Assess data quality
        data_quality, warnings = self._assess_data_quality(
            recent_data, quarterly_summaries, annual_summaries
        )

        return PerceptionContext(
            province_id=province_id,
            province_name=await self._get_province_name(province_id),
            current_month=current_month,
            current_year=current_year,
            recent_data=recent_data,
            quarterly_summaries=quarterly_summaries,
            annual_summaries=annual_summaries,
            critical_events=critical_events,
            trends=trends,
            data_quality=data_quality,
            warnings=warnings
        )

    # ========== Helper Methods ==========

    async def _get_province_name(self, province_id: int) -> str:
        """Get province name from database"""
        province = self.db.get_province(province_id)
        if province:
            return province['name']
        return f"Province {province_id}"

    # ========== Abstract Method Implementations ==========

    async def _mock_llm_response(self, response_model) -> Any:
        """Generate mock LLM response for structured output"""
        return None  # Not used in PerceptionAgent

    async def _mock_llm_text_response(self, prompt: str) -> str:
        """Generate mock text response for summary generation"""
        if "quarterly" in prompt.lower():
            return "Quarterly performance showed income growth with improving loyalty indicators."
        elif "annual" in prompt.lower():
            return "Annual performance demonstrated steady growth despite occasional challenges."
        return "Summary generated from provincial data."

    # ========== Placeholder methods (to be implemented in next step) ==========

    async def _build_monthly_detailed(
        self,
        province_id: int,
        target_month: int,
        target_year: int
    ) -> MonthlyDetailedData:
        """Build complete monthly data for the most recent month"""
        # Implementation in next step
        pass

    async def _build_quarterly_summaries(
        self,
        province_id: int,
        current_month: int,
        current_year: int
    ) -> List[QuarterlySummary]:
        """Build quarterly summaries for the last 4 quarters"""
        # Implementation in next step
        pass

    async def _build_annual_summaries(
        self,
        province_id: int,
        current_year: int
    ) -> List[AnnualSummary]:
        """Build annual summaries for the last 3 years"""
        # Implementation in next step
        pass

    async def _index_critical_events(
        self,
        province_id: int,
        months_lookback: int = 12
    ) -> List[EventIndex]:
        """Index critical events for quick reference"""
        # Implementation in next step
        pass

    async def _analyze_trends(
        self,
        recent_data: MonthlyDetailedData,
        quarterly_summaries: List[QuarterlySummary],
        annual_summaries: List[AnnualSummary]
    ) -> TrendAnalysis:
        """Analyze trends and identify risks/opportunities"""
        # Implementation in next step
        pass

    def _assess_data_quality(
        self,
        recent_data: MonthlyDetailedData,
        quarterly_summaries: List[QuarterlySummary],
        annual_summaries: List[AnnualSummary]
    ) -> tuple:
        """Assess data quality and generate warnings"""
        # Implementation in next step
        return "complete", []
