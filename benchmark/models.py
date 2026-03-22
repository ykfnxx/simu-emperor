from __future__ import annotations

from dataclasses import dataclass
from typing import List, Self


@dataclass
class MetricResult:
    """
    Unified metric result for a benchmark.
    """

    name: str
    value: float
    target: float
    unit: str
    passed: bool

    def to_dict(self) -> dict:
        """
        Serialize to a JSON-serializable dictionary.
        """
        return {
            "name": self.name,
            "value": self.value,
            "target": self.target,
            "unit": self.unit,
            "passed": self.passed,
        }

    @classmethod
    def from_dict(cls, data: dict) -> Self:
        """
        Deserialize from a dictionary produced by to_dict.
        """
        return cls(
            name=data["name"],
            value=data["value"],
            target=data["target"],
            unit=data["unit"],
            passed=data["passed"],
        )


@dataclass
class CaseDetail:
    """
    Detail for an individual benchmark case.
    """

    case_id: str
    passed: bool
    input: str
    expected: List[str]
    actual: List[str]
    reason: str
    args_correct: bool = True  # Whether tool call arguments match expected

    def to_dict(self) -> dict:
        return {
            "case_id": self.case_id,
            "passed": self.passed,
            "input": self.input,
            "expected": list(self.expected),
            "actual": list(self.actual),
            "reason": self.reason,
            "args_correct": self.args_correct,
        }

    @classmethod
    def from_dict(cls, data: dict) -> Self:
        return cls(
            case_id=data["case_id"],
            passed=data["passed"],
            input=data["input"],
            expected=list(data["expected"]),
            actual=list(data["actual"]),
            reason=data["reason"],
            args_correct=data.get("args_correct", True),
        )


@dataclass
class ModuleResult:
    """
    Aggregated benchmark results for a module.
    """

    module: str
    metrics: List[MetricResult]
    details: List[CaseDetail]
    duration_seconds: float

    def to_dict(self) -> dict:
        return {
            "module": self.module,
            "metrics": [m.to_dict() for m in self.metrics],
            "details": [d.to_dict() for d in self.details],
            "duration_seconds": self.duration_seconds,
        }

    @classmethod
    def from_dict(cls, data: dict) -> Self:
        return cls(
            module=data["module"],
            metrics=[MetricResult.from_dict(m) for m in data["metrics"]],
            details=[CaseDetail.from_dict(c) for c in data["details"]],
            duration_seconds=data["duration_seconds"],
        )
