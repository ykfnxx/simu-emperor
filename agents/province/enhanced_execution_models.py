"""
Enhanced Execution Agent data models

Defines additional Pydantic models for LLM-enhanced execution capabilities:
- LLM execution interpretation models
- Creative event generation models  
- Execution quality assessment models
- Context and historical data models
"""

from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field
from enum import Enum
from agents.province.models import BehaviorType, BehaviorDefinition, Decision


class ExecutionMode(str, Enum):
    """Execution agent mode"""
    STANDARD = "standard"  # Rule-based only
    LLM_ENHANCED = "llm_enhanced"  # LLM-enhanced execution
    HYBRID = "hybrid"  # Combination of both


class ExecutionContext(BaseModel):
    """Context for execution"""
    season: str = "spring"  # spring, summer, autumn, winter
    recent_events: List[str] = Field(default_factory=list)
    population_mood: str = "neutral"  # positive, neutral, negative
    economic_conditions: str = "stable"  # booming, stable, struggling, crisis
    political_stability: str = "stable"  # stable, tense, unstable
    historical_context: Optional[Dict[str, Any]] = None


class LLMExecutionInterpretation(BaseModel):
    """LLM interpretation of execution strategy"""
    execution_strategy: str = Field(description="Overall execution approach")
    timing_recommendations: List[str] = Field(default_factory=list, description="Optimal timing suggestions")
    resource_allocation: Dict[str, Any] = Field(default_factory=dict, description="Resource allocation strategy")
    risk_mitigation: List[str] = Field(default_factory=list, description="Risk mitigation measures")
    expected_challenges: List[str] = Field(default_factory=list, description="Anticipated challenges")
    success_metrics: List[str] = Field(default_factory=list, description="Success measurement criteria")
    confidence_level: float = Field(ge=0.0, le=1.0, description="Confidence in execution success")
    execution_phases: Optional[List[str]] = None


class CreativeEventOutput(BaseModel):
    """Output for creative event generation"""
    event_name: str = Field(description="Creative and engaging event name")
    description: str = Field(description="Detailed, immersive event description")
    severity: float = Field(ge=0.1, le=1.0, description="Event severity level")
    visibility: str = Field(description="Event visibility level")
    special_characteristics: List[str] = Field(default_factory=list, description="Special event features")
    narrative_tone: str = Field(description="Tone of the event narrative")
    cultural_context: Optional[str] = None


class OptimizedExecutionSequence(BaseModel):
    """Optimized execution sequence"""
    execution_phases: List[str] = Field(description="Ordered execution phases")
    timing_recommendations: List[str] = Field(default_factory=list)
    resource_allocation: Dict[str, Any] = Field(default_factory=dict)
    phase_dependencies: Dict[str, List[str]] = Field(default_factory=dict)
    estimated_duration: Optional[str] = None


class ExecutionPhase(BaseModel):
    """Individual execution phase"""
    phase_name: str
    behaviors: List[BehaviorDefinition]
    estimated_duration: str
    prerequisites: List[str] = Field(default_factory=list)
    expected_outcomes: List[str] = Field(default_factory=list)
    has_follow_up: bool = False
    has_long_term_impact: bool = False


class ExecutionQualityReport(BaseModel):
    """Comprehensive execution quality assessment"""
    effectiveness: float = Field(ge=0.0, le=1.0, description="How well execution achieved intended goals")
    efficiency: float = Field(ge=0.0, le=1.0, description="Resource utilization efficiency")
    impact: float = Field(ge=0.0, le=1.0, description="Overall social and economic impact")
    risk_management: float = Field(ge=0.0, le=1.0, description="How well risks were managed")
    adaptability: float = Field(ge=0.0, le=1.0, description="Ability to adapt to changing conditions")
    overall_score: float = Field(ge=0.0, le=1.0, description="Overall execution quality score")
    detailed_assessment: str = Field(description="Detailed quality assessment narrative")
    improvement_recommendations: List[str] = Field(default_factory=list)
    success_factors: List[str] = Field(default_factory=list)
    failure_factors: List[str] = Field(default_factory=list)


class ExecutionPrediction(BaseModel):
    """Prediction of execution outcomes"""
    success_rate: float = Field(ge=0.0, le=1.0, description="Predicted success probability")
    expected_effectiveness: float = Field(ge=1.0, le=10.0, description="Expected effectiveness score")
    potential_challenges: List[str] = Field(default_factory=list, description="Likely challenges")
    recommended_optimizations: List[str] = Field(default_factory=list, description="Suggested improvements")
    risk_factors: List[str] = Field(default_factory=list, description="Key risk factors")
    confidence_level: float = Field(ge=0.0, le=1.0, description="Confidence in prediction")


class ExecutionRecord(BaseModel):
    """Historical execution record for learning"""
    execution_id: str
    province_id: int
    month: int
    year: int
    decision: Decision
    execution_result: Dict[str, Any]
    quality_score: float
    success_indicators: Dict[str, Any]
    challenges_encountered: List[str] = Field(default_factory=list)
    adaptations_made: List[str] = Field(default_factory=list)


class OutcomeFeedback(BaseModel):
    """Feedback on execution outcomes"""
    execution_id: str
    actual_outcome: str
    outcome_quality: float = Field(ge=0.0, le=1.0)
    stakeholder_satisfaction: float = Field(ge=0.0, le=1.0)
    unexpected_consequences: List[str] = Field(default_factory=list)
    lessons_learned: List[str] = Field(default_factory=list)


class LearnedExecutionPatterns(BaseModel):
    """Learned patterns from execution history"""
    success_patterns: List[Dict[str, Any]] = Field(default_factory=list)
    failure_lessons: List[Dict[str, Any]] = Field(default_factory=list)
    optimized_parameters: Dict[str, Any] = Field(default_factory=dict)
    execution_recommendations: List[str] = Field(default_factory=list)
    pattern_confidence: Dict[str, float] = Field(default_factory=dict)


class EnhancedExecutionResult(BaseModel):
    """Enhanced execution result with quality assessment"""
    execution_result: Dict[str, Any]  # Original ExecutionResult
    quality_report: ExecutionQualityReport
    learning_insights: Optional[Dict[str, Any]] = None
    execution_interpretation: Optional[LLMExecutionInterpretation] = None
    predictive_insights: Optional[ExecutionPrediction] = None


class LLMExecutionInput(BaseModel):
    """Input for LLM execution interpretation"""
    decision: Decision
    province_state: Dict[str, Any]
    execution_context: ExecutionContext
    historical_context: Optional[List[ExecutionRecord]] = None
    risk_tolerance: float = Field(ge=0.0, le=1.0, default=0.5)


class HistoricalContext(BaseModel):
    """Historical context for execution"""
    recent_executions: List[ExecutionRecord] = Field(default_factory=list)
    seasonal_patterns: Dict[str, Any] = Field(default_factory=dict)
    historical_outcomes: Dict[str, float] = Field(default_factory=dict)
    lessons_learned: List[str] = Field(default_factory=list)