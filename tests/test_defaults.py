"""Saved report defaults: extraction, persistence, application and checks."""

from models.defaults import ReportDefaults, apply_config, defaults_from_report, extract_config, missing_settings
from models.evaluation import OverallResult
from models.inspection import InspectionInfo, InspectionReport
from models.sample_data import sample_report
from database.database import ReportRepository
from services.calculation_service import evaluate_report
from services.defaults_service import load_defaults, save_defaults
from services.validation_service import validate_defaults


def _real_report() -> InspectionReport:
    report = sample_report()
    report.info.is_sample = False
    report.info.report_number = "QC-REAL-1"
    return report


def test_extract_keeps_settings_but_no_readings():
    config = extract_config(sample_report())
    assert config.tensile.yield_unit == "MPa"
    assert config.tensile.method == "Example tensile test method"
    assert config.hardness.scale == "HB"
    assert config.metallography.grain_size_method == "Comparison method"
    assert config.criteria.uts.minimum == 300
    # measured values and per-sample details are not defaults
    assert config.tensile.yield_strength is None
    assert config.tensile.uts is None
    assert config.tensile.elongation is None
    assert config.hardness.readings == []
    assert config.metallography.grain_size is None
    assert config.metallography.microstructure == ""
    assert config.info.report_number == "" and config.info.material == ""
    # report-specific fields are not defaults
    assert config.info.customer == "" and config.info.inspector == ""
    assert config.metallography.specimen_id == "" and config.tensile.specimen_id == ""
    assert config.metallography.etchant == "" and config.metallography.magnification == ""


def test_apply_config_fills_settings_and_keeps_readings():
    report = InspectionReport(info=InspectionInfo(report_number="N-1", material="Steel"))
    report.tensile.uts = 320
    apply_config(report, extract_config(sample_report()))
    assert report.tensile.uts == 320
    assert report.tensile.uts_unit == "MPa"
    assert report.criteria.uts.minimum == 300
    assert report.info.report_number == "N-1"


def test_defaults_seeded_from_latest_real_report_and_persisted(tmp_path):
    repo = ReportRepository(tmp_path / "h.db")
    sample = sample_report()  # sample reports are never used as defaults
    repo.save(sample, "PASS")
    real = _real_report()
    real.criteria.uts.minimum = 410
    repo.save(real, "PASS")

    defaults = load_defaults(repo)
    assert defaults.seeded_from == "QC-REAL-1"
    assert defaults.config.criteria.uts.minimum == 410
    assert defaults.reading_count == 3

    # Persisted: a later report does not silently change the defaults.
    later = _real_report()
    later.info.report_number = "QC-REAL-2"
    later.criteria.uts.minimum = 999
    repo.save(later, "PASS")
    assert load_defaults(ReportRepository(tmp_path / "h.db")).config.criteria.uts.minimum == 410


def test_edited_defaults_persist(tmp_path):
    repo = ReportRepository(tmp_path / "h.db")
    defaults = defaults_from_report(_real_report())
    defaults.config.criteria.hardness.maximum = 88
    defaults.config.tensile.method = "Edited method"
    save_defaults(repo, defaults)
    reloaded = load_defaults(ReportRepository(tmp_path / "h.db"))
    assert reloaded.config.criteria.hardness.maximum == 88
    assert reloaded.config.tensile.method == "Edited method"


def test_empty_history_gives_empty_defaults(tmp_path):
    defaults = load_defaults(ReportRepository(tmp_path / "h.db"))
    assert defaults.config.tensile.yield_unit is None
    assert not defaults.config.criteria.uts.is_specified


def test_new_report_with_defaults_evaluates_against_saved_limits():
    config = extract_config(sample_report())
    report = InspectionReport(info=InspectionInfo(report_number="N-1", report_date="2026-10-25",
                                                  material="Aluminium"))
    report.tensile.yield_strength, report.tensile.uts, report.tensile.elongation = 275, 280, 12
    report.hardness.readings = [80, 82]
    report.metallography.grain_size = 8
    apply_config(report, config)
    evaluation = evaluate_report(report)
    assert evaluation.get("uts").status.value == "FAIL"
    assert evaluation.overall == OverallResult.FAIL


def test_missing_mandatory_criterion_in_defaults_gives_review_required():
    config = extract_config(sample_report())
    config.criteria.grain_size.minimum = None  # mandatory, but no limit saved
    report = apply_config(sample_report(), config)
    assert evaluate_report(report).overall == OverallResult.REVIEW_REQUIRED
    assert "Grain Size acceptance limits (mandatory test)" in missing_settings(config)


def test_missing_settings_are_reported_not_guessed():
    config = extract_config(sample_report())
    config.metallography.grain_size_method = ""
    config.criteria.source = ""
    missing = missing_settings(config)
    assert "Grain Size Standard / Method" in missing
    assert "Source of acceptance criteria" in missing


def test_validate_defaults_rejects_unit_mismatch_and_bad_limits():
    config = extract_config(sample_report())
    config.criteria.uts.unit = "ksi"
    config.criteria.hardness.minimum = 95
    errors = validate_defaults(config)
    assert any("UTS: criterion unit (ksi) differs" in e for e in errors)
    assert any("minimum (95) is greater than maximum (90)" in e for e in errors)
    assert validate_defaults(extract_config(sample_report())) == []


def test_defaults_round_trip():
    d = defaults_from_report(_real_report())
    assert ReportDefaults.from_dict(d.to_dict()) == d


# --- Report-specific fields (customer, inspector, specimen IDs, etchant, magnification)

def test_apply_config_never_overwrites_report_specific_fields():
    config = extract_config(sample_report())
    report = InspectionReport()
    report.info.customer, report.info.inspector = "Dept A", "Inspector B"
    report.metallography.specimen_id, report.tensile.specimen_id = "M-9", "T-9"
    report.metallography.etchant, report.metallography.magnification = "Keller's reagent", "200X"
    apply_config(report, config)
    assert (report.info.customer, report.info.inspector) == ("Dept A", "Inspector B")
    assert (report.metallography.specimen_id, report.tensile.specimen_id) == ("M-9", "T-9")
    assert report.metallography.etchant == "Keller's reagent"
    assert report.metallography.magnification == "200X"


def test_suggestions_default_to_nital_and_100x():
    d = ReportDefaults()
    assert d.suggested_etchant == "Nital"
    assert d.initial_magnification == "100X"


def test_legacy_saved_defaults_migrate_to_suggestions():
    legacy = defaults_from_report(_real_report()).to_dict()
    legacy.pop("suggested_etchant")
    legacy.pop("initial_magnification")
    legacy["config"]["info"]["customer"] = "Old Customer"
    legacy["config"]["info"]["inspector"] = "Old Inspector"
    legacy["config"]["metallography"]["etchant"] = "Nital"
    legacy["config"]["metallography"]["magnification"] = "200X"
    d = ReportDefaults.from_dict(legacy)
    assert d.suggested_etchant == "Nital"
    assert d.initial_magnification == "200X"
    assert d.config.info.customer == "" and d.config.info.inspector == ""
    assert d.config.criteria.uts.minimum == 300  # limits kept


def test_new_entry_requires_customer_inspector_specimen_and_etchant_confirmation():
    from services.validation_service import validate_new_entry

    report = sample_report()
    report.info.customer = report.info.inspector = report.metallography.specimen_id = ""
    errors = validate_new_entry(report, etchant_confirmed=False).errors
    assert "Customer / Department is required for each report." in errors
    assert "Inspector Name is required for each report." in errors
    assert "Metallography Specimen ID is required for each report." in errors
    assert "Confirm the etchant used for this specimen (Metallography)." in errors
    assert validate_new_entry(sample_report(), etchant_confirmed=True).errors == []


def test_tensile_specimen_id_is_independent():
    from services.validation_service import validate_new_entry

    report = sample_report()
    report.tensile.specimen_id = ""
    result = validate_new_entry(report, etchant_confirmed=True)
    assert result.errors == []  # metallography specimen ID still present
    assert "Tensile Test Specimen ID is empty." in result.warnings


def test_historical_reports_still_validate_for_regeneration():
    from services.report_service import build_pdf

    old = sample_report()
    old.info.inspector = ""  # e.g. an older report saved without an inspector
    assert build_pdf(old).page_count == 1
