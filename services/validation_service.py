"""Input validation.

Errors block evaluation and report generation; warnings are shown to the
inspector but do not block. Validation never fills in missing values.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import Optional

from models.inspection import Criterion, InspectionReport


@dataclass
class ValidationResult:
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    @property
    def is_valid(self) -> bool:
        return not self.errors


def _check_non_negative(value: Optional[float], label: str, errors: list[str]) -> None:
    if value is not None and value < 0:
        errors.append(f"{label} cannot be negative (entered {value:g}).")


SETTINGS_HINT = " Units are never assumed — set it in Settings / Edit Defaults."


def _check_unit(value: Optional[float], unit: Optional[str], label: str, errors: list[str],
                hint: str = SETTINGS_HINT) -> None:
    if value is not None and not unit:
        errors.append(f"{label}: no unit is set.{hint}")


def _check_criterion(c: Criterion, label: str, errors: list[str], needs_unit: bool = True) -> None:
    _check_non_negative(c.minimum, f"{label} minimum", errors)
    _check_non_negative(c.maximum, f"{label} maximum", errors)
    if c.minimum is not None and c.maximum is not None and c.minimum > c.maximum:
        errors.append(f"{label}: minimum ({c.minimum:g}) is greater than maximum ({c.maximum:g}).")
    if needs_unit and c.is_specified and not c.unit:
        errors.append(f"{label} criterion: no unit / scale is set.")


def validate_defaults(config: InspectionReport) -> list[str]:
    """Errors that prevent saving a configuration as the defaults."""
    errors: list[str] = []
    t, c = config.tensile, config.criteria
    _check_non_negative(t.gauge_length, "Gauge Length", errors)
    _check_unit(t.gauge_length, t.gauge_length_unit, "Gauge Length", errors, hint="")
    _check_unit(t.test_temperature, t.temperature_unit, "Test Temperature", errors, hint="")
    _check_criterion(c.yield_strength, "Yield Strength", errors)
    _check_criterion(c.uts, "UTS", errors)
    _check_criterion(c.elongation, "Elongation", errors, needs_unit=False)
    _check_criterion(c.hardness, "Hardness", errors)
    _check_criterion(c.grain_size, "Grain Size", errors, needs_unit=False)
    # A limit is only comparable when it is in the same unit as the result.
    for label, crit_unit, result_unit in (
        ("Yield Strength", c.yield_strength.unit, t.yield_unit),
        ("UTS", c.uts.unit, t.uts_unit),
        ("Hardness", c.hardness.unit, config.hardness.scale),
    ):
        if crit_unit and result_unit and crit_unit != result_unit:
            errors.append(f"{label}: criterion unit ({crit_unit}) differs from the result unit "
                          f"({result_unit}). No conversion is performed.")
    return errors


def validate_new_entry(report: InspectionReport, etchant_confirmed: bool) -> ValidationResult:
    """Report-specific fields that must be entered or confirmed for each new report.

    Applied to the report being entered in the form only, so reports already in
    the history regenerate exactly as they were saved.
    """
    result = ValidationResult()
    info, t, m = report.info, report.tensile, report.metallography
    if not info.customer.strip():
        result.errors.append("Customer / Department is required for each report.")
    if not info.inspector.strip():
        result.errors.append("Inspector Name is required for each report.")

    if m.grain_size is not None or m.microstructure.strip():
        if not m.specimen_id.strip():
            result.errors.append("Metallography Specimen ID is required for each report.")
        if not etchant_confirmed:
            result.errors.append("Confirm the etchant used for this specimen (Metallography).")
        elif not m.etchant.strip():
            result.errors.append("Enter the etchant used for this specimen.")
        if not m.magnification.strip():
            result.errors.append("Magnification is required for the metallography section.")

    if any(v is not None for v in (t.yield_strength, t.uts, t.elongation)) and not t.specimen_id.strip():
        result.warnings.append("Tensile Test Specimen ID is empty.")
    return result


def validate_report(report: InspectionReport) -> ValidationResult:
    result = ValidationResult()
    errors, warnings = result.errors, result.warnings
    info, t, h, m, c = (
        report.info, report.tensile, report.hardness, report.metallography, report.criteria
    )

    # --- Inspection information -------------------------------------------
    if not info.report_number.strip():
        errors.append("Report Number is required.")
    if not info.material.strip():
        errors.append("Material / Product is required.")
    if not info.report_date:
        errors.append("Report Date is required.")
    else:
        try:
            date.fromisoformat(info.report_date)
        except ValueError:
            errors.append(f"Report Date '{info.report_date}' is not a valid date (YYYY-MM-DD).")

    # --- Tensile ----------------------------------------------------------
    _check_non_negative(t.yield_strength, "Yield Strength", errors)
    _check_non_negative(t.uts, "Ultimate Tensile Strength", errors)
    _check_non_negative(t.elongation, "Elongation", errors)
    _check_non_negative(t.gauge_length, "Gauge Length", errors)
    _check_unit(t.yield_strength, t.yield_unit, "Yield Strength", errors)
    _check_unit(t.uts, t.uts_unit, "Ultimate Tensile Strength", errors)
    _check_unit(t.gauge_length, t.gauge_length_unit, "Gauge Length", errors)
    _check_unit(t.test_temperature, t.temperature_unit, "Test Temperature", errors)
    if t.elongation is not None and t.elongation > 100:
        warnings.append(f"Elongation of {t.elongation:g} % is unusually high; please verify.")
    if (
        t.yield_strength is not None
        and t.uts is not None
        and t.yield_unit
        and t.yield_unit == t.uts_unit
        and t.yield_strength > t.uts
    ):
        warnings.append("Yield Strength is greater than UTS; please verify the entered values.")

    # --- Hardness ---------------------------------------------------------
    for i, reading in enumerate(h.readings, start=1):
        _check_non_negative(reading, f"Hardness reading {i}", errors)
    if h.readings and not h.scale:
        errors.append("Hardness: no hardness scale is set — set it in Settings / Edit Defaults.")

    # --- Metallography ----------------------------------------------------
    _check_non_negative(m.grain_size, "Grain Size number", errors)

    # --- Acceptance criteria ---------------------------------------------
    _check_criterion(c.yield_strength, "Yield Strength", errors)
    _check_criterion(c.uts, "UTS", errors)
    _check_criterion(c.elongation, "Elongation", errors, needs_unit=False)
    _check_criterion(c.hardness, "Hardness", errors)
    _check_criterion(c.grain_size, "Grain Size", errors, needs_unit=False)

    # --- Required (mandatory) tests are clearly identified ----------------
    mandatory_results = {
        "Yield Strength": (c.yield_strength.mandatory, t.yield_strength),
        "Ultimate Tensile Strength": (c.uts.mandatory, t.uts),
        "Elongation": (c.elongation.mandatory, t.elongation),
        "Hardness": (c.hardness.mandatory, h.readings or None),
        "Grain Size": (c.grain_size.mandatory, m.grain_size),
    }
    missing = [name for name, (mandatory, value) in mandatory_results.items() if mandatory and value is None]
    if missing:
        warnings.append("Mandatory test result(s) not entered: " + ", ".join(missing) + ".")

    no_results = all(v is None for _, v in mandatory_results.values())
    if no_results:
        warnings.append("No test results have been entered.")

    return result
