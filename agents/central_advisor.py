"""
Central Advisor Agent - Central Advisory Agent
Responsible for analyzing national data, identifying anomalous provinces, providing strategic advice
"""

from .base import BaseAgent, AgentMode
from typing import Dict, Any, List, Optional
from pydantic import BaseModel, Field
from enum import Enum


class CorruptionLevel(str, Enum):
    """Corruption risk level"""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class SuspiciousProvince(BaseModel):
    """Suspicious province information"""
    province_id: int
    name: str = Field(..., description="Province name")
    reason: str = Field(..., description="Reason for suspicion")
    severity: CorruptionLevel = Field(..., description="Risk level")
    confidence: float = Field(..., description="Confidence level (0-1)", ge=0, le=1)


class AnalysisReport(BaseModel):
    """Analysis report structure"""
    status: str = Field(..., description="Report status: normal/warning/critical")
    summary: str = Field(..., description="Summary")
    suspicious_provinces: List[SuspiciousProvince] = Field(default_factory=list)
    recommendations: List[str] = Field(default_factory=list)
    analysis_time: Optional[str] = None


class CentralAdvisorAgent(BaseAgent):
    """Central Advisor Agent - Analyze national data, identify anomalous provinces

    Responsibilities:
    - Analyze all provinces' reported data
    - Identify suspicious corruption behaviors
    - Provide investigation recommendations
    - Use LLM for in-depth analysis (if enabled)
    """

    def __init__(self, agent_id: str, config: Dict[str, Any]):
        """Initialize CentralAdvisorAgent

        Args:
            agent_id: Agent unique identifier (e.g., "central_advisor")
            config: Configuration dictionary containing LLM config
        """
        super().__init__(agent_id, config)

        # Configuration: In central analysis agent, LLM is enabled by default
        if 'llm_config' not in config:
            self.llm_config.enabled = True
            self.llm_config.mock_mode = config.get('mock_mode', True)

        # Historical data cache
        self.historical_reports: List[Dict[str, Any]] = []
        self.last_analysis: Optional[AnalysisReport] = None

    async def _mock_llm_response(self, response_model) -> Any:
        """Generate mock LLM response"""
        if response_model == AnalysisReport:
            # Mock analysis: based on capital province analysis
            return AnalysisReport(
                status="warning",
                summary="Found 1 medium-risk province",
                suspicious_provinces=[
                    SuspiciousProvince(
                        province_id=1,
                        name="Capital",
                        reason="Medium loyalty (85), requires continuous monitoring",
                        severity=CorruptionLevel.LOW,
                        confidence=0.7
                    )
                ],
                recommendations=[
                    "Recommend continued monitoring of capital's financial status",
                    "Consider investing in stability projects in the capital",
                    "Maintain continuous attention on single province"
                ]
            )
        return None

    async def _mock_llm_text_response(self, prompt: str) -> str:
        """Generate mock text response"""
        return "Based on current data, single province requires continuous monitoring of its financial and loyalty status."

    async def initialize(self, config: Dict[str, Any]) -> None:
        """Initialize (subclass implementation)"""
        pass

    async def on_month_start(self, game_state: Dict[str, Any],
                           provinces: List[Dict[str, Any]]) -> None:
        """Month start: analyze all province data

        Args:
            game_state: Game state
            provinces: All province data (includes reported and actual values)
        """
        # If using LLM assistance, call LLM analysis
        if self.mode == AgentMode.LLM_ASSISTED and self.llm_config.enabled:
            self.last_analysis = await self._llm_analysis(game_state, provinces)
        else:
            # Simple rule-driven analysis
            self.last_analysis = self._rule_based_analysis(provinces)

        # Save to historical records
        self.historical_reports.append({
            'month': game_state.get('current_month', 1),
            'analysis': self.last_analysis.model_dump() if self.last_analysis else None
        })

    async def _llm_analysis(self, game_state: Dict[str, Any],
                          provinces: List[Dict[str, Any]]) -> AnalysisReport:
        """Use LLM for analysis (structured output)"""
        # Build prompt
        prompt = self._build_analysis_prompt(game_state, provinces)

        system_prompt = """
        You are the imperial central advisor, responsible for analyzing provincial financial reports and identifying potential corruption or anomalies.

        You need to:
        1. Analyze each province's reported data
        2. Identify suspicious provinces (abnormal income, low loyalty, etc.)
        3. Assess risk levels (low/medium/high)
        4. Provide specific investigation recommendations

        Please return analysis results in JSON format, including:
        - status: normal/warning/critical
        - summary: brief summary
        - suspicious_provinces: suspicious province list (province_id, name, reason, severity, confidence)
        - recommendations: specific suggestions (3-5 items)
        """

        # Call LLM for structured analysis
        analysis = await self.call_llm_structured(
            prompt=prompt,
            response_model=AnalysisReport,
            system_prompt=system_prompt
        )

        return analysis or await self._mock_llm_response(AnalysisReport)

    def _rule_based_analysis(self, provinces: List[Dict[str, Any]]) -> AnalysisReport:
        """Rule-based analysis (no LLM needed)"""
        suspicious = []

        for province in provinces:
            loyalty = province.get('loyalty', 100)
            reported_income = province.get('reported_income', 0)
            actual_income = province.get('actual_income', 0)

            # Rule 1: Loyalty below 55, mark as suspicious
            if loyalty < 55:
                severity = CorruptionLevel.HIGH if loyalty < 40 else CorruptionLevel.MEDIUM
                suspicious.append(SuspiciousProvince(
                    province_id=province['province_id'],
                    name=province['name'],
                    reason=f"Low loyalty ({loyalty})",
                    severity=severity,
                    confidence=0.8
                ))

            # Rule 2: If reported income is much lower than actual income (indicates income was withheld)
            if actual_income > 0 and reported_income < actual_income * 0.85:
                suspicious.append(SuspiciousProvince(
                    province_id=province['province_id'],
                    name=province['name'],
                    reason=f"Large deviation between reported and calculated expected income",
                    severity=CorruptionLevel.MEDIUM,
                    confidence=0.6
                ))

        # Determine status
        if len(suspicious) == 0:
            status = "normal"
            summary = "All provinces show normal data, no obvious anomalies"
        elif len([s for s in suspicious if s.severity == CorruptionLevel.HIGH]) > 0:
            status = "critical"
            summary = f"Found {len(suspicious)} suspicious provinces including high-risk ones"
        else:
            status = "warning"
            summary = f"Found {len(suspicious)} medium-risk provinces"

        # Generate recommendations
        recommendations = []
        if suspicious:
            high_risk = [s for s in suspicious if s.severity == CorruptionLevel.HIGH]
            if high_risk:
                recommendations.append(
                    f"Prioritize investigation of {len(high_risk)} high-risk provinces: {', '.join([s.name for s in high_risk])}"
                )
            recommendations.append("Recommend launching anti-corruption investigation projects in suspicious provinces")
            recommendations.append("Strengthen monitoring of low-loyalty provinces")

        return AnalysisReport(
            status=status,
            summary=summary,
            suspicious_provinces=suspicious,
            recommendations=recommendations
        )

    def _build_analysis_prompt(self, game_state: Dict[str, Any],
                             provinces: List[Dict[str, Any]]) -> str:
        """Build analysis prompt"""
        prompt = f"""
        Current empire status (Month {game_state.get('current_month', 1)}):
        - Treasury balance: {game_state.get('treasury', 0):.2f} gold coins
        - Number of provinces: {len(provinces)}

        Detailed data for each province:
        """

        for province in provinces:
            is_corrupted = province.get('last_month_corrupted', False)
            corruption_mark = "⚠️" if is_corrupted else "✓"

            prompt += f"""
        {corruption_mark} {province['name']} (ID: {province['province_id']}):
           - Loyalty: {province.get('loyalty', 0):.0f}/100
           - Stability: {province.get('stability', 0):.0f}/100
           - Development level: {province.get('development_level', 0):.1f}/10
           - Reported income: {province.get('reported_income', 0):.2f} gold coins
           - Reported expenditure: {province.get('reported_expenditure', 0):.2f} gold coins
           - Status: {"Suspected corruption" if is_corrupted else "Data normal"}
            """

        prompt += """

        Please analyze the above data, identify suspicious provinces and provide specific recommendations.
        """

        return prompt

    async def take_action(self, context: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Execute action: return analysis report

        Returns:
            Analysis report dictionary
        """
        if not self.last_analysis:
            return None

        return {
            'agent_id': self.agent_id,
            'status': self.last_analysis.status,
            'summary': self.last_analysis.summary,
            'suspicious_provinces': [
                {
                    'province_id': sp.province_id,
                    'name': sp.name,
                    'reason': sp.reason,
                    'severity': sp.severity.value,
                    'confidence': sp.confidence
                }
                for sp in self.last_analysis.suspicious_provinces
            ],
            'recommendations': self.last_analysis.recommendations,
            'mode': self.mode.value
        }

    def get_state(self) -> Dict[str, Any]:
        """Get Agent current state"""
        return {
            'agent_id': self.agent_id,
            'mode': self.mode.value,
            'llm_enabled': self.llm_config.enabled,
            'llm_mock_mode': self.llm_config.mock_mode,
            'last_analysis_summary': self.last_analysis.summary if self.last_analysis else None,
            'suspicious_count': len(self.last_analysis.suspicious_provinces) if self.last_analysis else 0,
            'historical_reports_count': len(self.historical_reports)
        }
