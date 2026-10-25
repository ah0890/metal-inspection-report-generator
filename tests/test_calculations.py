import pytest

from models.evaluation import OverallResult, Status
from models.inspection import Criterion
from models.sample_data import sample_report
from services.calculation_service import (
    average_hardness,
    compare_to_limits,
    evaluate_report,
    evaluate_test,
    overall_result,
)
from services.formatting import NOT_SPECIFIED


# --- Hardness average --------------------------------------------------------

def test_average_hardness():
    assert average_hardness([80, 82, 84]) == pytest.approx(82.0)


def test_average_hardness_single_reading():
    assert average_hardness([82]) == 82.0


def test_average_hardness_ignores_empty_entries():
    assert average_hardness([80, None, 84]) == pytest.approx(82.0)


def test_average_hardness_no_readings():
    assert average_hardness([]) is None


def test_average_hardness_rejects_negative():
    with pytest.raises(ValueError):
        average_hardness([80, -1])


# --- Minimum criteria ----------------------------------------------------------

def test_yield_above_minimum_passes():
    r = evaluate_test("ys", "Yield Strength", 275, "MPa", Criterion(minimum=250, unit="MPa"))
    assert r.status == Status.PASS


def test_uts_below_minimum_fails():
    r = evaluate_test("uts", "UTS", 280, "MPa", Criterion(minimum=300, unit="MPa"))
    assert r.status == Status.FAIL


def test_minimum_is_inclusive():
    assert compare_to_limits(250, 250, None) == Status.PASS


def test_elongation_minimum():
    assert compare_to_limits(12.4, 10, None) == Status.PASS
    assert compare_to_limits(9.9, 10, None) == Status.FAIL


# --- Maximum criteria ----------------------------------------------------------

def test_maximum_criteria():
    assert compare_to_limits(85, None, 90) == Status.PASS
    assert compare_to_limits(90, None, 90) == Status.PASS
    assert compare_to_limits(90.1, None, 90) == Status.FAIL


# --- Range criteria -------------------------------------------------------------

@pytest.mark.parametrize(
    "value,expected",
    [(70, Status.PASS), (82, Status.PASS), (90, Status.PASS), (69.9, Status.FAIL), (95, Status.FAIL)],
)
def test_hardness_range(value, expected):
    r = evaluate_test("h", "Hardness", value, "HB", Criterion(minimum=70, maximum=90, unit="HB"))
    assert r.status == expected


# --- Missing information / no assumptions ------------------------------------

def test_no_criterion_is_not_evaluated_and_says_so():
    r = evaluate_test("ys", "Yield Strength", 275, "MPa", Criterion())
    assert r.status == Status.NOT_EVALUATED
    assert r.requirement_text == NOT_SPECIFIED


def test_criterion_without_result_needs_review():
    r = evaluate_test("ys", "Yield Strength", None, "MPa", Criterion(minimum=250, unit="MPa"))
    assert r.status == Status.REVIEW


def test_unit_mismatch_is_not_converted():
    r = evaluate_test("ys", "Yield Strength", 40, "ksi", Criterion(minimum=250, unit="MPa"))
    assert r.status == Status.REVIEW
    assert "no conversion" in r.note


def test_hardness_scale_mismatch_needs_review():
    r = evaluate_test("h", "Hardness", 30, "HRC", Criterion(minimum=70, maximum=90, unit="HB"))
    assert r.status == Status.REVIEW


def test_grain_size_or_finer():
    report = sample_report()
    report.metallography.grain_size = 6  # coarser than required No. 7
    assert evaluate_report(report).get("grain_size").status == Status.FAIL
    report.metallography.grain_size = 7
    assert evaluate_report(report).get("grain_size").status == Status.PASS


# --- Overall result --------------------------------------------------------------

def _item(status, mandatory=True, name="T"):
    from models.evaluation import TestEvaluation

    return TestEvaluation(name.lower(), name, None, None, "", "", status, mandatory)


def test_overall_pass_when_all_pass():
    result, _ = overall_result([_item(Status.PASS), _item(Status.PASS)])
    assert result == OverallResult.PASS


def test_overall_fail_when_one_mandatory_fails():
    result, reasons = overall_result([_item(Status.PASS), _item(Status.FAIL, name="UTS")])
    assert result == OverallResult.FAIL
    assert "UTS" in reasons[0]


def test_fail_takes_precedence_over_review():
    result, _ = overall_result([_item(Status.REVIEW), _item(Status.FAIL)])
    assert result == OverallResult.FAIL


def test_overall_review_when_mandatory_criterion_missing():
    result, _ = overall_result([_item(Status.PASS), _item(Status.NOT_EVALUATED)])
    assert result == OverallResult.REVIEW_REQUIRED


def test_overall_review_when_result_missing():
    result, _ = overall_result([_item(Status.PASS), _item(Status.REVIEW)])
    assert result == OverallResult.REVIEW_REQUIRED


def test_non_mandatory_failure_needs_review_not_fail():
    result, _ = overall_result([_item(Status.PASS), _item(Status.FAIL, mandatory=False)])
    assert result == OverallResult.REVIEW_REQUIRED


def test_non_mandatory_without_criterion_is_ignored():
    result, _ = overall_result([_item(Status.PASS), _item(Status.NOT_EVALUATED, mandatory=False)])
    assert result == OverallResult.PASS


def test_overall_review_when_nothing_evaluated():
    result, _ = overall_result([_item(Status.NOT_EVALUATED, mandatory=False)])
    assert result == OverallResult.REVIEW_REQUIRED


# --- Sample data ------------------------------------------------------------------

def test_sample_data_passes():
    evaluation = evaluate_report(sample_report())
    assert evaluation.overall == OverallResult.PASS
    assert all(i.status == Status.PASS for i in evaluation.items)


def test_sample_with_low_uts_fails():
    report = sample_report()
    report.tensile.uts = 280
    evaluation = evaluate_report(report)
    assert evaluation.get("uts").status == Status.FAIL
    assert evaluation.overall == OverallResult.FAIL
