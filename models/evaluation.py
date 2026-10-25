"""Result types produced by the deterministic evaluation (calculation_service)."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


class Status(str, Enum):
    """Status of a single test against its acceptance criterion."""

    PASS = "PASS"
    FAIL = "FAIL"
    REVIEW = "REVIEW"  # criterion exists but cannot be evaluated (missing result, unit mismatch)
    NOT_EVALUATED = "NOT EVALUATED"  # no criterion specified


class OverallResult(str, Enum):
    PASS = "PASS"
    FAIL = "FAIL"
    REVIEW_REQUIRED = "REVIEW REQUIRED"


@dataclass
class TestEvaluation:
    key: str
    name: str
    actual: Optional[float]
    unit: Optional[str]
    result_text: str
    requirement_text: str
    status: Status
    mandatory: bool
    note: str = ""

    __test__ = False  # stop pytest from collecting this class as a test


@dataclass
class EvaluationResult:
    items: list[TestEvaluation] = field(default_factory=list)
    overall: OverallResult = OverallResult.REVIEW_REQUIRED
    reasons: list[str] = field(default_factory=list)

    def get(self, key: str) -> Optional[TestEvaluation]:
        return next((i for i in self.items if i.key == key), None)
