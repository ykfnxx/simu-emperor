"""
Agent Personality and Capability Definitions

Defines personality types and capability parameters for GovernorAgent
"""

from typing import Optional
from pydantic import BaseModel
from enum import Enum


class PersonalityTrait(Enum):
    """Personality Type Enumeration"""
    HONEST = "honest"          # Honest - Tends to report truthfully, rarely deceives
    CORRUPT = "corrupt"        # Corrupt - Tends to embezzle and frequently deceives
    PRAGMATIC = "pragmatic"    # Pragmatic - Makes flexible decisions based on actual situation
    AMBITIOUS = "ambitious"    # Ambitious - Pursues achievements, may exaggerate results
    CAUTIOUS = "cautious"      # Cautious - Avoids risks, makes conservative decisions
    DECEPTIVE = "deceptive"    # Deceptive - Proficient in various deception methods


class AgentCapability(BaseModel):
    """
    Agent Capability Model

    All capability values range: 0.0-1.0
    """
    event_generation_rate: float = 0.3           # Event generation probability - likelihood of generating events per turn
    fabrication_skill: float = 0.5               # Fabrication ability - ability to create convincing events
    narrative_consistency: float = 0.7           # Narrative consistency - ability to maintain consistent statements
    risk_tolerance: float = 0.5                  # Risk tolerance - willingness to take risks
    deception_detection_resistance: float = 0.5  # Anti-detection ability - ability to avoid detection by central authority
    persuasiveness: float = 0.6                  # Persuasiveness - ability to make central authority believe their statements

    class Config:
        use_enum_values = True


class GovernorPersonality(BaseModel):
    """
    GovernorAgent Personality Configuration

    Defines Agent's basic personality traits, behavioral tendencies, and capability values
    """

    # Core personality types
    primary_trait: PersonalityTrait                    # Primary personality trait
    secondary_trait: Optional[PersonalityTrait] = None  # Secondary personality trait (optional)

    # Personality parameters (range: 0.0-1.0 or 0-100)
    loyalty_base: float = 70.0              # Base loyalty (0-100), affects concealment tendency
    corruption_tendency: float = 0.3        # Corruption tendency (0-1), base corruption probability
    wealth_desire: float = 0.5              # Wealth desire (0-1), intensity of motivation for embezzlement
    reputation_concern: float = 0.6         # Reputation concern (0-1), concern about being discovered
    central_fear: float = 0.4               # Fear of central authority (0-1), affects concealment decisions

    # Behavioral tendencies (probability: 0.0-1.0)
    hide_event_probability: float = 0.2     # Event hiding probability - don't report events to central
    fabricate_event_probability: float = 0.1  # Event fabrication probability - create false events
    report_override_probability: float = 0.3  # Report adjustment probability - modify real data

    # Capability values
    capabilities: AgentCapability = AgentCapability()

    class Config:
        use_enum_values = True

    def get_corruption_base_chance(self) -> float:
        """
        Calculate base corruption probability

        Formula: corruption_tendency + (100-loyalty_base)/200
        """
        return self.corruption_tendency + (100 - self.loyalty_base) / 200

    def get_fabrication_base_chance(self) -> float:
        """
        Calculate base fabrication probability

        Consider: fabrication ability, wealth desire, fear of central authority
        """
        return (
            self.capabilities.fabrication_skill * 0.4 +
            self.wealth_desire * 0.3 +
            (1 - self.central_fear) * 0.3
        )


    def get_event_generation_chance(self, situation_multiplier: float = 1.0) -> float:
        """
        Calculate event generation probability

        Args:
            situation_multiplier: Situation multiplier (adjusted based on game state)

        Returns:
            Actual event generation probability
        """
        return min(
            self.capabilities.event_generation_rate * situation_multiplier,
            1.0
        )


    def get_risk_adjusted_bias_ratio(self, desired_ratio: float) -> float:
        """
        Adjust bias ratio based on risk tolerance

        Cautious agents will reduce risky behaviors

        Args:
            desired_ratio: Ideal ratio

        Returns:
            Adjusted ratio
        """
        risk_factor = self.capabilities.risk_tolerance

        if abs(desired_ratio) > 0.2:
            # High-risk behavior, adjust based on risk tolerance
            return desired_ratio * risk_factor

        return desired_ratio

    def should_hide_event(self, event_severity: float) -> bool:
        """
        Decide whether to hide events

        Args:
            event_severity: Event severity level (0-1)

        Returns:
            Whether to hide
        """
        # High severity events are more likely to be hidden
        severity_factor = event_severity

        # Consider reputation concern and central fear
        fear_factor = (1 - self.central_fear)
        reputation_factor = self.reputation_concern

        hide_chance = (
            self.hide_event_probability * 0.5 +
            severity_factor * 0.3 +
            fear_factor * 0.1 +
            reputation_factor * 0.1
        )

        return random.random() < hide_chance

    def should_fabricate_event(self, needs_cover: bool = False) -> bool:
        """
        Decide whether to fabricate events

        Args:
            needs_cover: Whether need to cover up (increases fabrication probability)

        Returns:
            Whether to fabricate
        """
        base_chance = self.get_fabrication_base_chance()

        if needs_cover:
            # If need to cover up, probability doubles
            base_chance *= 2

        # Consider risk tolerance
        base_chance *= self.capabilities.risk_tolerance

        return random.random() < min(base_chance, 0.8)  # Maximum 80% probability

    def generate_narrative(self, event_type: str, is_fabricated: bool) -> str:
        """
        Generate event narrative description

        Fabricated events need more detailed explanations

        Args:
            event_type: Event type
            is_fabricated: Whether fabricated

        Returns:
            Narrative text
        """
        base_narrative = f"Local event detected: {event_type}"

        if is_fabricated:
            # Fabricated events need more detailed explanations
            if self.capabilities.narrative_consistency > 0.7:
                # High narrative consistency: more credible description
                details = [
                    "According to local government reports",
                    "After multi-party verification",
                    "Preliminary investigation shows",
                    "Local officials confirm"
                ]
                base_narrative = f"{random.choice(details)}, {base_narrative.lower()}."

                # Add specific details
                if "financial" in event_type:
                    base_narrative += f" Specific amount: {random.randint(50, 200)} gold coins."
                elif "population" in event_type:
                    base_narrative += f" Affected population: approximately {random.randint(1000, 5000)} people."
                elif "stability" in event_type:
                    base_narrative += f" Impact scope: local area."

                # Add time information
                base_narrative += f" Expected duration: {random.randint(2, 5)} months."

            else:
                # Low narrative consistency: vague description
                base_narrative += " Specific situation still under investigation."

        return base_narrative

    def adjust_for_central_attention(self, attention_level: float):
        """
        Adjust behavior based on central attention

        Args:
            attention_level: Central attention level (0-1)
        """
        if attention_level > 0.7:
            # Under high attention, reduce deceptive behaviors
            self.hide_event_probability *= 0.5
            self.fabricate_event_probability *= 0.5
            self.report_override_probability *= 0.7

        elif attention_level < 0.3:
            # Under low attention, increase deceptive behaviors
            self.hide_event_probability *= 1.5
            self.fabricate_event_probability *= 1.5
            self.report_override_probability *= 1.3


# Predefined personality configurations
PERSONALITY_PRESETS = {
    "honest_governor": GovernorPersonality(
        primary_trait=PersonalityTrait.HONEST,
        loyalty_base=90.0,
        corruption_tendency=0.1,
        wealth_desire=0.3,
        reputation_concern=0.9,
        central_fear=0.7,
        capabilities=AgentCapability(
            event_generation_rate=0.1,
            fabrication_skill=0.2,
            narrative_consistency=0.9,
            risk_tolerance=0.2,
            deception_detection_resistance=0.3
        )
    ),

    "corrupt_governor": GovernorPersonality(
        primary_trait=PersonalityTrait.CORRUPT,
        loyalty_base=30.0,
        corruption_tendency=0.8,
        wealth_desire=0.9,
        reputation_concern=0.2,
        central_fear=0.1,
        capabilities=AgentCapability(
            event_generation_rate=0.4,
            fabrication_skill=0.8,
            narrative_consistency=0.4,
            risk_tolerance=0.8,
            deception_detection_resistance=0.7
        )
    ),

    "deceptive_governor": GovernorPersonality(
        primary_trait=PersonalityTrait.DECEPTIVE,
        loyalty_base=50.0,
        corruption_tendency=0.5,
        wealth_desire=0.7,
        reputation_concern=0.8,
        central_fear=0.5,
        capabilities=AgentCapability(
            event_generation_rate=0.6,
            fabrication_skill=0.9,
            narrative_consistency=0.9,
            risk_tolerance=0.6,
            deception_detection_resistance=0.9
        )
    ),

    "pragmatic_governor": GovernorPersonality(
        primary_trait=PersonalityTrait.PRAGMATIC,
        loyalty_base=60.0,
        corruption_tendency=0.4,
        wealth_desire=0.6,
        reputation_concern=0.7,
        central_fear=0.5,
        capabilities=AgentCapability(
            event_generation_rate=0.3,
            fabrication_skill=0.5,
            narrative_consistency=0.7,
            risk_tolerance=0.5,
            deception_detection_resistance=0.5
        )
    ),

    "ambitious_governor": GovernorPersonality(
        primary_trait=PersonalityTrait.AMBITIOUS,
        loyalty_base=70.0,
        corruption_tendency=0.3,
        wealth_desire=0.7,
        reputation_concern=0.8,
        central_fear=0.4,
        capabilities=AgentCapability(
            event_generation_rate=0.4,
            fabrication_skill=0.6,
            narrative_consistency=0.8,
            risk_tolerance=0.6,
            deception_detection_resistance=0.6
        )
    ),

    "cautious_governor": GovernorPersonality(
        primary_trait=PersonalityTrait.CAUTIOUS,
        loyalty_base=75.0,
        corruption_tendency=0.2,
        wealth_desire=0.4,
        reputation_concern=0.8,
        central_fear=0.6,
        capabilities=AgentCapability(
            event_generation_rate=0.2,
            fabrication_skill=0.3,
            narrative_consistency=0.6,
            risk_tolerance=0.3,
            deception_detection_resistance=0.4
        )
    )
}
