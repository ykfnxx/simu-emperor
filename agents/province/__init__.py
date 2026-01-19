"""
Province Agent package

This package implements the three-agent province management system:
- PerceptionAgent: Analyzes historical data and trends
- DecisionAgent: Makes decisions based on player instructions and autonomous goals
- ExecutionAgent: Executes behaviors and generates events
"""

from .models import (
    # Enums
    TrendDirection,
    RiskLevel,
    InstructionStatus,
    BehaviorType,

    # Perception models
    EventSummary,
    MonthlyDetailedData,
    QuarterlySummary,
    AnnualSummary,
    EventIndex,
    TrendAnalysis,
    PerceptionContext,

    # Decision models
    PlayerInstruction,
    BehaviorDefinition,
    InstructionEvaluation,
    Decision,

    # Execution models
    BehaviorEffect,
    ExecutedBehavior,
    BehaviorEvent,
    ExecutionResult,
)

__all__ = [
    # Enums
    'TrendDirection',
    'RiskLevel',
    'InstructionStatus',
    'BehaviorType',

    # Perception models
    'EventSummary',
    'MonthlyDetailedData',
    'QuarterlySummary',
    'AnnualSummary',
    'EventIndex',
    'TrendAnalysis',
    'PerceptionContext',

    # Decision models
    'PlayerInstruction',
    'BehaviorDefinition',
    'InstructionEvaluation',
    'Decision',

    # Execution models
    'BehaviorEffect',
    'ExecutedBehavior',
    'BehaviorEvent',
    'ExecutionResult',
]
