"""
Governor Agent - Local Governance Agent
Responsible for managing a single province, deciding governance strategies and reporting data
"""

from .base import BaseAgent, AgentMode
from agents.personality import GovernorPersonality, PersonalityTrait
from typing import Dict, Any, Optional, List
from pydantic import BaseModel
import random


class PolicyDecision(BaseModel):
    """Governor's policy decision"""
    should_corrupt: bool
    corruption_ratio: float = 0.0
    expenditure_inflation: float = 0.0
    reasoning: str = ""


class GovernorAgent(BaseAgent):
    """Local Governance Agent - Governor

    Responsibilities:
    - Decide whether to report honestly or conceal information this month
    - May use LLM for complex decisions (if enabled)
    - Manage governance strategy for a single province
    """

    def __init__(self, agent_id: str, config: Dict[str, Any]):
        """Initialize GovernorAgent

        Args:
            agent_id: Agent unique identifier (e.g., "governor_1")
            config: Configuration dictionary containing loyalty, corruption_tendency, etc.
        """
        super().__init__(agent_id, config)
        self.province_id = config.get('province_id')
        self.province_name = config.get('province_name', 'Unknown')
        self.corruption_tendency = config.get('corruption_tendency', 0.3)
        self.loyalty = config.get('loyalty', 70)
        self.stability = config.get('stability', 70)
        self.development_level = config.get('development_level', 5.0)
        # Set default personality
        default_personality = GovernorPersonality(
            primary_trait=PersonalityTrait.PRAGMATIC,
            loyalty_base=60.0,
            corruption_tendency=0.4
        )
        self.personality: GovernorPersonality = config.get('personality', default_personality)

        # Current decision state
        self.corruption_ratio = 0.0
        self.expenditure_inflation = 0.0
        self.last_month_corrupted = False
        self.last_reasoning = ""

    async def _mock_llm_response(self, response_model) -> Any:
        """Generate mock LLM response"""
        if response_model == PolicyDecision:
            # 50% chance of corruption (simplified rule)
            should_corrupt = random.random() < 0.5
            if should_corrupt:
                return PolicyDecision(
                    should_corrupt=True,
                    corruption_ratio=random.uniform(0.1, 0.3),
                    expenditure_inflation=random.uniform(0.05, 0.2),
                    reasoning="Based on current loyalty and development status, decided to conceal part of income for personal gain"
                )
            else:
                return PolicyDecision(
                    should_corrupt=False,
                    corruption_ratio=0.0,
                    expenditure_inflation=0.0,
                    reasoning="Loyal to the empire, decided to report all data truthfully"
                )
        return None

    async def _mock_llm_text_response(self, prompt: str) -> str:
        """Generate mock text response"""
        if "policy" in prompt.lower():
            return "As a local official, I should prioritize local development and balance personal interests."
        return "I have received the instruction and will execute it."

    async def initialize(self, config: Dict[str, Any]) -> None:
        """Initialize (subclass implementation)"""
        # Already initialized in __init__, additional initialization logic can be added here
        pass

    async def on_month_start(self, game_state: Dict[str, Any],
                           provinces: List[Dict[str, Any]]) -> None:
        """Month start: decide whether to conceal information

        Args:
            game_state: Game state (treasury, month, etc.)
            provinces: List of all provinces (for context)
        """
        # Calculate corruption probability (based on loyalty)
        corruption_chance = self._calculate_corruption_chance()

        # Make decision based on operation mode
        if self.mode == AgentMode.LLM_ASSISTED and self.llm_config.enabled:
            # LLM-assisted decision
            decision = await self._make_llm_decision(game_state, provinces)
        else:
            # Rule-driven
            decision = self._make_rule_based_decision(corruption_chance)

        # Apply decision
        self.corruption_ratio = decision.corruption_ratio
        self.expenditure_inflation = decision.expenditure_inflation
        self.last_month_corrupted = decision.should_corrupt
        self.last_reasoning = decision.reasoning

    def _calculate_corruption_chance(self) -> float:
        """Calculate corruption probability (based on loyalty)"""
        base_chance = 0.3
        loyalty_modifier = (100 - self.loyalty) / 200
        return min(base_chance + loyalty_modifier, 0.7)

    async def _make_llm_decision(self, game_state: Dict[str, Any],
                               provinces: List[Dict[str, Any]]) -> PolicyDecision:
        """Use LLM for decision making (structured output)"""
        # Build prompt
        prompt = f"""
        You are the local governor of {self.province_name}.

        Current situation:
        - Loyalty: {self.loyalty}/100
        - Stability: {self.stability}/100
        - Development level: {self.development_level}/10
        - Corruption tendency: {self.corruption_tendency}

        Empire overall status:
        - Current month: {game_state.get('current_month', 1)}
        - Treasury: {game_state.get('treasury', 0):.2f} gold coins

        As a local official, you need to decide whether to report this month's financial data honestly.
        If you choose to conceal, you can embezzle part of the income and inflate expenditures.

        Please make your decision based on your character (loyalty, corruption tendency) and current situation.
        """

        system_prompt = f"""
        You are a local governor AI (Governor Agent).
        Your role is to manage a province and decide monthly whether to report financial data honestly.

        Higher loyalty ({self.loyalty}) means more tendency to report honestly.
        Higher corruption tendency ({self.corruption_tendency}) means more likely to conceal.

        Please return your decision in structured JSON format, including:
        - should_corrupt: whether to conceal
        - corruption_ratio: concealment ratio (0-0.3)
        - expenditure_inflation: expenditure inflation ratio (0-0.2)
        - reasoning: decision rationale
        """

        # Call LLM (structured output)
        decision = await self.call_llm_structured(
            prompt=prompt,
            response_model=PolicyDecision,
            system_prompt=system_prompt
        )

        return decision or await self._mock_llm_response(PolicyDecision)

    def _make_rule_based_decision(self, corruption_chance: float) -> PolicyDecision:
        """Make decision based on rules"""
        if random.random() < corruption_chance:
            # Choose corruption
            return PolicyDecision(
                should_corrupt=True,
                corruption_ratio=random.uniform(0.1, 0.3),
                expenditure_inflation=random.uniform(0.05, 0.2),
                reasoning=f"Low loyalty ({self.loyalty}), decided to conceal part of income"
            )
        else:
            # Choose honesty
            return PolicyDecision(
                should_corrupt=False,
                corruption_ratio=0.0,
                expenditure_inflation=0.0,
                reasoning="Loyal to the empire, report truthfully"
            )

    async def take_action(self, context: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Execute action: generate reporting data

        Args:
            context: Contains actual_income, actual_expenditure

        Returns:
            Reporting data dictionary
        """
        actual_income = context.get('actual_income', 0.0)
        actual_expenditure = context.get('actual_expenditure', 0.0)

        # Apply corruption (if decided to corrupt)
        reported_income = actual_income * (1 - self.corruption_ratio)
        reported_expenditure = actual_expenditure * (1 + self.expenditure_inflation)

        return {
            'province_id': self.province_id,
            'province_name': self.province_name,
            'reported_income': reported_income,
            'reported_expenditure': reported_expenditure,
            'actual_income': actual_income,
            'actual_expenditure': actual_expenditure,
            'corruption_ratio': self.corruption_ratio,
            'expenditure_inflation': self.expenditure_inflation,
            'last_month_corrupted': self.last_month_corrupted,
            'reasoning': self.last_reasoning
        }

    async def decide_event_visibility(self, event: Any) -> bool:
        """
        Decide whether to hide events (conceal or not report)

        Args:
            event: Event object

        Returns:
            bool: Whether to hide the event
        """
        # For financial events, decide whether to hide based on character and loyalty
        if 'financial' in event.name or 'debt' in event.name or 'crisis' in event.name:
            # Calculate hide probability (lower loyalty and higher corruption tendency increase likelihood)
            hide_chance = (100 - self.loyalty) / 100 * self.corruption_tendency

            # Personality-based adjustment
            if hasattr(self.personality, 'primary_trait'):
                if self.personality.primary_trait.value == 'deceptive':
                    hide_chance *= 1.5  # Deceptive types hide more easily
                elif self.personality.primary_trait.value == 'honest':
                    hide_chance *= 0.5  # Honest types less likely to hide

            # Event severity also affects decision (more severe events are riskier to hide)
            severity_modifier = 1.0 - (event.severity * 0.5)  # Higher severity means less likely to hide
            hide_chance *= severity_modifier

            # Make decision
            should_hide = random.random() < hide_chance

            if should_hide:
                self.last_month_corrupted = True
                self.last_reasoning = f"Decided to hide event '{event.name}' to avoid central accountability"

            return should_hide

        # Other events are not hidden
        return False

    def get_state(self) -> Dict[str, Any]:
        """Get Agent current state"""
        return {
            'agent_id': self.agent_id,
            'province_id': self.province_id,
            'province_name': self.province_name,
            'loyalty': self.loyalty,
            'corruption_tendency': self.corruption_tendency,
            'corruption_ratio': self.corruption_ratio,
            'expenditure_inflation': self.expenditure_inflation,
            'last_month_corrupted': self.last_month_corrupted,
            'mode': self.mode.value,
            'llm_enabled': self.llm_config.enabled if hasattr(self, 'llm_config') else False
        }
