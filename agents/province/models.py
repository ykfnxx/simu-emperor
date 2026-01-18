"""
Province Agent data models

Defines all Pydantic models used by the Province Agent system:
- Perception models (historical data, summaries, trends)
- Decision models (behaviors, instructions)
- Execution models (effects, results)
"""

from typing import List, Dict, Any, Optional, Type
from pydantic import BaseModel, Field
from enum import Enum


# ========== Enums ==========

class TrendDirection(str, Enum):
    """Trend direction enum"""
    INCREASING = "increasing"
    STABLE = "stable"
    DECREASING = "decreasing"


class RiskLevel(str, Enum):
    """Risk level enum"""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class InstructionStatus(str, Enum):
    """Instruction execution status"""
    PENDING = "pending"
    EXECUTING = "executing"
    COMPLETED = "completed"
    FAILED = "failed"


class BehaviorType(str, Enum):
    """Behavior type enum"""
    TAX_ADJUSTMENT = "tax_adjustment"
    INFRASTRUCTURE_INVESTMENT = "infrastructure_investment"
    LOYALTY_CAMPAIGN = "loyalty_campaign"
    STABILITY_MEASURE = "stability_measure"
    EMERGENCY_RELIEF = "emergency_relief"
    CORRUPTION_CRACKDOWN = "corruption_crackdown"
    ECONOMIC_STIMULUS = "economic_stimulus"
    AUSTERITY_MEASURE = "austerity_measure"


# ========== Perception Models ==========

class EventSummary(BaseModel):
    """Single event summary"""
    event_id: str
    event_type: str
    name: str
    severity: float
    month: int
    year: int
    description: Optional[str] = None


class MonthlyDetailedData(BaseModel):
    """Complete data for the most recent month"""
    month: int
    year: int
    population: int
    development_level: float
    loyalty: float
    stability: float
    actual_income: float
    actual_expenditure: float
    reported_income: float
    reported_expenditure: float
    actual_surplus: float
    reported_surplus: float
    events: List[EventSummary] = Field(default_factory=list)


class QuarterlySummary(BaseModel):
    """Quarterly aggregated data with LLM-generated summary"""
    quarter: int  # 1-4
    year: int
    avg_income: float
    median_income: float
    avg_expenditure: float
    median_expenditure: float
    total_surplus: float
    income_trend: TrendDirection
    expenditure_trend: TrendDirection
    loyalty_change: float
    stability_change: float
    major_events: List[str] = Field(default_factory=list)
    special_event_types: List[str] = Field(default_factory=list)
    summary: str  # LLM-generated trend summary


class AnnualSummary(BaseModel):
    """Annual summary with LLM-generated performance summary"""
    year: int
    total_income: float
    total_expenditure: float
    avg_monthly_income: float
    avg_monthly_expenditure: float
    total_surplus: float
    population_change: int
    development_change: float
    loyalty_start: float
    loyalty_end: float
    loyalty_change: float
    major_events: List[str] = Field(default_factory=list)
    disaster_count: int = 0
    rebellion_count: int = 0
    performance_rating: str = "average"
    summary: str  # LLM-generated annual summary


class EventIndex(BaseModel):
    """Indexed critical event"""
    index_id: int
    event_id: str
    event_category: str  # 'rebellion' | 'war' | 'disaster' | 'crisis'
    event_name: str
    severity: float
    month: int
    year: int
    impact_description: str
    is_resolved: bool


class TrendAnalysis(BaseModel):
    """Comprehensive trend analysis"""
    income_trend: TrendDirection
    income_change_rate: float  # Percentage
    expenditure_trend: TrendDirection
    expenditure_change_rate: float
    loyalty_trend: TrendDirection
    loyalty_change_rate: float
    stability_trend: TrendDirection
    stability_change_rate: float
    risk_level: RiskLevel
    risk_factors: List[str] = Field(default_factory=list)
    opportunities: List[str] = Field(default_factory=list)


class PerceptionContext(BaseModel):
    """Complete perception output for DecisionAgent"""
    province_id: int
    province_name: str
    current_month: int
    current_year: int
    recent_data: MonthlyDetailedData
    quarterly_summaries: List[QuarterlySummary]  # Max 4
    annual_summaries: List[AnnualSummary]  # Max 3
    critical_events: List[EventIndex]  # Max 8
    trends: TrendAnalysis
    data_quality: str = "complete"  # 'complete' | 'partial' | 'minimal'
    warnings: List[str] = Field(default_factory=list)


# ========== Decision Models ==========

class PlayerInstruction(BaseModel):
    """Player instruction for Province Agent"""
    instruction_id: Optional[int] = None
    province_id: int
    month: int
    year: int
    instruction_type: str
    template_name: str
    parameters: Dict[str, Any] = Field(default_factory=dict)
    status: InstructionStatus = InstructionStatus.PENDING
    result_summary: Optional[str] = None
    agent_reasoning: Optional[str] = None


class BehaviorDefinition(BaseModel):
    """Definition of a behavior to execute"""
    behavior_type: BehaviorType
    behavior_name: str
    parameters: Dict[str, Any] = Field(default_factory=dict)
    reasoning: Optional[str] = None
    is_valid: bool = True
    validation_error: Optional[str] = None


class InstructionEvaluation(BaseModel):
    """Evaluation of instruction feasibility"""
    is_feasible: bool
    confidence: float  # 0.0 to 1.0
    constraints: List[str] = Field(default_factory=list)
    required_resources: Dict[str, Any] = Field(default_factory=dict)
    expected_outcome: Optional[str] = None
    risk_assessment: RiskLevel = RiskLevel.LOW


class Decision(BaseModel):
    """Agent decision output"""
    province_id: int
    month: int
    year: int
    behaviors: List[BehaviorDefinition]
    in_response_to_instruction: Optional[int] = None
    reasoning: str
    risk_level: RiskLevel
    estimated_effects: Dict[str, Any] = Field(default_factory=dict)


# ========== Execution Models ==========

class BehaviorEffect(BaseModel):
    """Effect of a behavior execution"""
    behavior_type: BehaviorType
    behavior_name: str
    income_change: float = 0.0
    expenditure_change: float = 0.0
    loyalty_change: float = 0.0
    stability_change: float = 0.0
    development_change: float = 0.0
    population_change: int = 0
    other_effects: Dict[str, Any] = Field(default_factory=dict)


class ExecutedBehavior(BaseModel):
    """Record of an executed behavior"""
    behavior_id: Optional[int] = None
    behavior_type: BehaviorType
    behavior_name: str
    parameters: Dict[str, Any] = Field(default_factory=dict)
    effects: BehaviorEffect
    reasoning: Optional[str] = None
    execution_success: bool = True
    execution_message: Optional[str] = None


class BehaviorEvent(BaseModel):
    """Event generated from behavior execution"""
    event_id: str
    event_type: str
    name: str
    description: str
    severity: float
    effects: Dict[str, Any]
    visibility: str = "provincial"
    is_agent_generated: bool = True


class ExecutionResult(BaseModel):
    """Result of behavior execution"""
    province_id: int
    month: int
    year: int
    executed_behaviors: List[ExecutedBehavior]
    generated_events: List[BehaviorEvent]
    total_effects: BehaviorEffect
    province_state_after: Dict[str, Any]
    execution_summary: str
