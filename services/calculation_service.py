"""Deterministic acceptance evaluation.

Every PASS / FAIL decision in the application is made here, in plain Python.
Claude is never asked to compare numbers. Acceptance limits come only from the
user-entered criteria; nothing is assumed for a material or grade.

Rules
-----
* A limit is inclusive: actual >= minimum and actual <= maximum pass.
* No criterion entered            -> NOT EVALUATED ("Acceptance criterion not specified").
* Criterion entered, no result    -> REVIEW.
* Result and criterion in different units -> REVIEW (no unit conversion is performed).

Overall result
--------------
1. Any mandatory test FAIL                                   -> FAIL
2. Otherwise any of: a REVIEW item, a mandatory test without
   a criterion, or a non-mandatory test that failed           -> REVIEW REQUIRED
3. Otherwise, at least one test evaluated as PASS             -> PASS
4. Nothing evaluated at all                                   -> REVIEW REQUIRED
"""

from __future__ import annotations

from typing import Iterable, Optional

from models.evaluation import EvaluationResult, OverallResult, Status, TestEvaluation
from models.inspection import Criterion, InspectionReport
from services.formatting import (
    grain_limits_text,
    grain_size_text,
    limits_text,
    with_unit,
)


def average_hardness(readings: Iterable[Optional[float]]) -> Optional[float]:
    """Arithmetic mean of the hardness readings; ``None`` when there are none.

    Raises ValueError for negative readings, which are physically impossible.
    """
    values = [float(r) for r in readings if r is not None]
    if not values:
        return None
    if any(v < 0 for v in values):
        raise ValueError("Hardness readings cannot be negative.")
    return sum(values) / len(values)


def compare_to_limits(
    actual: Optional[float], minimum: Optional[float], maximum: Optional[float]
) -> Status:
    """Compare a measured value with optional inclusive minimum / maximum limits."""
    if minimum is None and maximum is None:
        return Status.NOT_EVALUATED
    if actual is None:
        return Status.REVIEW
    if minimum is not None and actual < minimum:
        return Status.FAIL
    if maximum is not None and actual > maximum:
        return Status.FAIL
    return Status.PASS


def evaluate_test(
    key: str,
    name: str,
    actual: Optional[float],
    actual_unit: Optional[str],
    criterion: Criterion,
    *,
    check_units: bool = True,
    result_text: Optional[str] = None,
    requirement_text: Optional[str] = None,
) -> TestEvaluation:
    """Evaluate one test result against its criterion."""
    status = compare_to_limits(actual, criterion.minimum, criterion.maximum)
    note = ""

    if status == Status.REVIEW:
        note = "Result not reported"
    elif (
        status in (Status.PASS, Status.FAIL)
        and check_units
        and (criterion.unit or None) != (actual_unit or None)
    ):
        status = Status.REVIEW
        note = (
            f"Unit mismatch: result in {actual_unit or 'no unit'}, criterion in "
            f"{criterion.unit or 'no unit'} (no conversion performed)"
        )
    elif status == Status.NOT_EVALUATED and criterion.mandatory:
        note = "Acceptance criterion not specified"

    return TestEvaluation(
        key=key,
        name=name,
        actual=actual,
        unit=actual_unit,
        result_text=result_text if result_text is not None else with_unit(actual, actual_unit),
        requirement_text=(
            requirement_text
            if requirement_text is not None
            else limits_text(criterion.minimum, criterion.maximum, criterion.unit)
        ),
        status=status,
        mandatory=criterion.mandatory,
        note=note,
    )


def overall_result(items: list[TestEvaluation]) -> tuple[OverallResult, list[str]]:
    """Combine individual statuses into PASS / FAIL / REVIEW REQUIRED with reasons."""
    failed = [i for i in items if i.status == Status.FAIL and i.mandatory]
    if failed:
        return OverallResult.FAIL, [
            f"{i.name} does not meet the specified requirement." for i in failed
        ]

    reasons: list[str] = []
    for i in items:
        if i.status == Status.FAIL:  # non-mandatory failure
            reasons.append(f"{i.name} (non-mandatory) does not meet the criterion; engineering review needed.")
        elif i.status == Status.REVIEW:
            reasons.append(f"{i.name}: {i.note or 'cannot be evaluated'}.")
        elif i.status == Status.NOT_EVALUATED and i.mandatory:
            reasons.append(f"{i.name}: acceptance criterion not specified for a mandatory test.")
    if reasons:
        return OverallResult.REVIEW_REQUIRED, reasons

    if not any(i.status == Status.PASS for i in items):
        return OverallResult.REVIEW_REQUIRED, ["No acceptance criteria were evaluated."]

    return OverallResult.PASS, ["All evaluated tests meet the specified acceptance criteria."]


def evaluate_report(report: InspectionReport) -> EvaluationResult:
    """Evaluate every test in the report and calculate the overall result."""
    t, h, m, c = report.tensile, report.hardness, report.metallography, report.criteria

    hardness_avg = average_hardness(h.readings)
    hardness_text = None
    if hardness_avg is not None:
        hardness_text = with_unit(hardness_avg, h.scale, decimals=1)
        if h.count > 1:
            hardness_text += f" (avg. of {h.count})"

    items = [
        evaluate_test("yield_strength", "Yield Strength", t.yield_strength, t.yield_unit, c.yield_strength),
        evaluate_test("uts", "Ultimate Tensile Strength", t.uts, t.uts_unit, c.uts),
        evaluate_test(
            "elongation", "Elongation", t.elongation, "%", c.elongation,
            requirement_text=limits_text(c.elongation.minimum, c.elongation.maximum, "%"),
            check_units=False,
        ),
        evaluate_test("hardness", "Hardness", hardness_avg, h.scale, c.hardness, result_text=hardness_text),
        evaluate_test(
            "grain_size", "Grain Size", m.grain_size, None, c.grain_size,
            check_units=False,
            result_text=grain_size_text(m.grain_size),
            requirement_text=grain_limits_text(c.grain_size.minimum, c.grain_size.maximum),
        ),
    ]
    overall, reasons = overall_result(items)
    return EvaluationResult(items=items, overall=overall, reasons=reasons)

