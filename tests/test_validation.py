import pytest

from models.inspection import InspectionReport
from models.sample_data import sample_report
from services.report_service import ReportValidationError, build_pdf
from services.validation_service import validate_report


def _errors(report):
    return validate_report(report).errors


def test_sample_data_is_valid():
    assert validate_report(sample_report()).is_valid


@pytest.mark.parametrize(
    "attr,label",
    [
        ("yield_strength", "Yield Strength"),
        ("uts", "Ultimate Tensile Strength"),
        ("elongation", "Elongation"),
    ],
)
def test_negative_tensile_values_rejected(attr, label):
    report = sample_report()
    setattr(report.tensile, attr, -1.0)
    assert any(label in e and "negative" in e for e in _errors(report))


def test_negative_hardness_rejected():
    report = sample_report()
    report.hardness.readings = [82, -3]
    assert any("Hardness reading 2" in e for e in _errors(report))


def test_report_number_required():
    report = sample_report()
    report.info.report_number = "   "
    assert "Report Number is required." in _errors(report)


def test_material_required():
    report = sample_report()
    report.info.material = ""
    assert "Material / Product is required." in _errors(report)


def test_empty_report_is_invalid():
    errors = _errors(InspectionReport())
    assert "Report Number is required." in errors
    assert "Material / Product is required." in errors
    assert "Report Date is required." in errors


def test_unit_must_be_selected():
    report = sample_report()
    report.tensile.uts_unit = None
    assert any("Ultimate Tensile Strength: select a unit" in e for e in _errors(report))


def test_hardness_scale_must_be_selected():
    report = sample_report()
    report.hardness.scale = None
    assert any("hardness scale" in e for e in _errors(report))


def test_criterion_min_greater_than_max_rejected():
    report = sample_report()
    report.criteria.hardness.minimum = 95
    assert any("minimum (95) is greater than maximum (90)" in e for e in _errors(report))


def test_missing_mandatory_results_are_identified():
    report = sample_report()
    report.tensile.elongation = None
    result = validate_report(report)
    assert result.is_valid  # a warning, not an error
    assert any("Mandatory test result(s) not entered: Elongation" in w for w in result.warnings)


def test_invalid_report_cannot_be_generated():
    report = sample_report()
    report.tensile.uts = -10
    with pytest.raises(ReportValidationError):
        build_pdf(report)
