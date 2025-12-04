"""
Governor Agent Extension Module

Adds event generation and Reporting decision functions to GovernorAgent
"""

from typing import Dict, Any, Optional, List
from pydantic import BaseModel
import random
from .personality import PersonalityTrait


class EventGenerationDecision(BaseModel):
    """Event generation decision"""
    should_generate_event: bool
    event_type: Optional[str] = None
    is_fabricated: bool = False
    reasoning: str = ""


class ReportingDecision(BaseModel):
    """Unified Reporting decision"""
    reporting_bias_ratio: float  # -0.5(conceal) ~ +0.5(exaggerate)
    reporting_target: str        # "increase_revenue"/"decrease_revenue"/"increase_cost"/"decrease_cost"
    narrative: str               # Adjustment explanation
    is_fabricated: bool = False
    hidden_events: List[str] = []
    concealment_reasoning: str = ""

    def calculate_adjusted_values(self, actual_income: float, actual_expenditure: float):
        """Calculate adjusted values"""
        if "revenue" in self.reporting_target:
            adjusted_income = actual_income * (1 + self.reporting_bias_ratio)
            adjusted_expenditure = actual_expenditure
        else:
            adjusted_income = actual_income
            adjusted_expenditure = actual_expenditure * (1 + self.reporting_bias_ratio)
        return adjusted_income, adjusted_expenditure


class EventConcealmentDecision(BaseModel):
    """Event concealment decision"""
    hidden_events: List[str] = []
    reasoning: str = ""


async def decide_event_generation(
    self,
    province: Any,
    game_state: Dict[str, Any]
) -> EventGenerationDecision:
    """
    Decide whether to generate events

    Based on:
    - Agent personality and capabilities
    - Current situation
    - Whether need to cover up
    """
    from .agent_event_generator import AgentEventGenerator

    generator = AgentEventGenerator()

    # Assess situation
    situation_score = generator.assess_situation_for_event_generation(
        self, province.to_dict(), game_state
    )

    # Calculate generation probability
    generation_rate = self.personality.capabilities.event_generation_rate
    actual_rate = generation_rate * situation_score

    if random.random() >= actual_rate:
        return EventGenerationDecision(should_generate_event=False)

    # Select event type
    from events.event_models import AgentEventType
    event_type = generator.select_event_type(self, province.to_dict(), game_state)

    # Decide whether to fabricate
    needs_cover = province.actual_income < province.reported_income * 0.8
    should_fabricate = self.personality.should_fabricate_event(needs_cover)

    return EventGenerationDecision(
        should_generate_event=True,
        event_type=event_type.value,
        is_fabricated=should_fabricate,
        reasoning=f"Based on current situation assessment, {self.personality.primary_trait.value} personality tendency"
    )


async def decide_reporting(
    self,
    province: Any,
    game_state: Dict[str, Any]
) -> ReportingDecision:
    """
    Decide how to report data

    Can report more or less, based on:
    - Personality type
    - Current needs
    - Risk tolerance
    """
    # Determine bias direction based on personality
    trait = self.personality.primary_trait

    if trait == PersonalityTrait.CORRUPT:
        # Corrupt official: conceal income
        target = "decrease_revenue"
        ratio = random.uniform(-0.3, -0.1)
        narrative = "Local economy declining, tax revenue decreasing"

    elif trait == PersonalityTrait.AMBITIOUS:
        # Ambitious official: exaggerate income
        target = "increase_revenue"
        ratio = random.uniform(0.1, 0.3)
        narrative = "Local economy booming, tax revenue increasing"

    elif trait == PersonalityTrait.DECEPTIVE:
        # Deceptive official: complex strategy
        if province.actual_income < 400:
            # When income is low, conceal to avoid accountability
            target = "decrease_revenue"
            ratio = random.uniform(-0.2, -0.05)
        else:
            # When income is high, exaggerate to show achievements
            target = "increase_revenue"
            ratio = random.uniform(0.05, 0.25)
        narrative = "Based on detailed accounting and local actual situation"

    elif trait == PersonalityTrait.PRAGMATIC:
        # Pragmatic official: small adjustments
        if random.random() < 0.5:
            target = "decrease_revenue"
            ratio = random.uniform(-0.1, 0)
        else:
            target = "increase_revenue"
            ratio = random.uniform(0, 0.1)
        narrative = "Reasonable adjustments based on actual situation"

    elif trait == PersonalityTrait.HONEST:
        # Honest official: minimal adjustments
        target = "increase_revenue"
        ratio = random.uniform(-0.05, 0.05)
        narrative = "Report local financial data truthfully"

    else:  # CAUTIOUS
        # Cautious official: conservative reporting
        target = "decrease_revenue"
        ratio = random.uniform(-0.15, 0.05)
        narrative = "Conservative estimate, reserving risk provisions"

    # Consider risk tolerance
    ratio = self.personality.get_risk_adjusted_bias_ratio(ratio)

    # Decide whether to fabricate explanations
    is_fabricated = abs(ratio) > 0.1 and self.personality.should_fabricate_event()

    return ReportingDecision(
        reporting_bias_ratio=ratio,
        reporting_target=target,
        narrative=narrative,
        is_fabricated=is_fabricated,
        hidden_events=[],
        concealment_reasoning=""
    )


async def decide_event_visibility(
    self,
    event: Any
) -> EventConcealmentDecision:
    """
    Decide whether to hide events

    Consider event severity and risk of being discovered
    """
    hidden_events = []

    # Check event severity
    if event.severity > 0.7:
        # High severity, consider hiding
        if self.personality.should_hide_event(event.severity):
            hidden_events.append(event.event_id)

    elif event.severity > 0.5 and self.personality.primary_trait == PersonalityTrait.CORRUPT:
        # Medium severity, corrupt officials tend to hide
        if random.random() < 0.6:
            hidden_events.append(event.event_id)

    return EventConcealmentDecision(
        hidden_events=hidden_events,
        reasoning=f"{self.personality.primary_trait.value} personality decision"
    )


# Add new methods to GovernorAgent class
# Execute the following code before use:
# GovernorAgent.decide_event_generation = decide_event_generation
# GovernorAgent.decide_reporting = decide_reporting
# GovernorAgent.decide_event_visibility = decide_event_visibility
