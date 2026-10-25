"""Mapping between the InspectionReport model and Streamlit session state.

Per-inspection widgets are bound to keys named "<section>.<field>"
(e.g. "tensile.uts"). The reusable configuration (units, methods, standards,
acceptance criteria) is not entered per report: it comes from

* the saved defaults, for a new report (``config_source == "defaults"``), or
* the settings stored with the report itself, for a reopened history report
  or the sample data (``config_source == "report"``), so an old report is
  never silently re-evaluated against changed limits.

The Settings page edits the defaults through keys prefixed with "def.".
"""

from __future__ import annotations

from dataclasses import fields
from datetime import date

import streamlit as st

from config import settings
from database.database import ReportRepository
from models.defaults import (
    CONFIG_FIELDS,
    DEFAULT_INITIAL_MAGNIFICATION,
    DEFAULT_SUGGESTED_ETCHANT,
    ReportDefaults,
    apply_config,
    extract_config,
)
from models.inspection import (
    AcceptanceCriteria,
    AIText,
    Criterion,
    HardnessTest,
    InspectionInfo,
    InspectionReport,
    Metallography,
    TensileTest,
)
from services.defaults_service import load_defaults
from services.validation_service import ValidationResult, validate_new_entry, validate_report

_SIMPLE_SECTIONS = {
    "info": InspectionInfo,
    "tensile": TensileTest,
    "metallography": Metallography,
    "ai": AIText,
}
_TRANSIENT_KEYS = ("generated", "ai_error", "ai_notice", "last_validation")


@st.cache_resource
def get_repository() -> ReportRepository:
    return ReportRepository()


def reading_key(i: int) -> str:
    return f"hardness.reading.{i}"


# --------------------------------------------------------------------------
# Per-inspection data
# --------------------------------------------------------------------------

def report_to_state(report: InspectionReport, reading_count: int) -> dict:
    """Flatten a report's per-inspection values into session-state pairs."""
    state: dict = {}
    for section, cls in _SIMPLE_SECTIONS.items():
        obj = getattr(report, section)
        for f in fields(cls):
            state[f"{section}.{f.name}"] = getattr(obj, f.name)
    try:
        state["info.report_date"] = date.fromisoformat(report.info.report_date)
    except ValueError:
        state["info.report_date"] = None

    readings = report.hardness.readings[: settings.MAX_HARDNESS_READINGS]
    state["hardness.count"] = len(readings) or reading_count
    for i in range(settings.MAX_HARDNESS_READINGS):
        state[reading_key(i)] = readings[i] if i < len(readings) else None
    return state


def current_config() -> InspectionReport:
    """Configuration that applies to the report currently in the form."""
    if st.session_state.get("config_source") == "report" and "report_config" in st.session_state:
        return st.session_state["report_config"]
    return load_defaults(get_repository()).config


def report_from_state() -> InspectionReport:
    """Build the full report: entered values plus the applicable configuration."""
    s = st.session_state

    def section(name: str, cls):
        return cls(**{f.name: s[f"{name}.{f.name}"] for f in fields(cls) if f"{name}.{f.name}" in s})

    info: InspectionInfo = section("info", InspectionInfo)
    d = s.get("info.report_date")
    info.report_date = d.isoformat() if isinstance(d, date) else ""
    for attr in ("report_number", "material", "grade", "heat_batch", "sample_number"):
        setattr(info, attr, (getattr(info, attr) or "").strip())

    count = int(s.get("hardness.count") or 0)
    readings = [s.get(reading_key(i)) for i in range(count)]
    for attr in ("customer", "inspector"):
        setattr(info, attr, (getattr(info, attr) or "").strip())
    metallography: Metallography = section("metallography", Metallography)
    metallography.specimen_id = (metallography.specimen_id or "").strip()
    metallography.magnification = (metallography.magnification or "").strip()
    metallography.etchant = current_etchant()
    report = InspectionReport(
        info=info,
        tensile=section("tensile", TensileTest),
        hardness=HardnessTest(readings=[float(r) for r in readings if r is not None]),
        metallography=metallography,
        ai=section("ai", AIText),
    )
    return apply_config(report, current_config())


# --------------------------------------------------------------------------
# Etchant confirmation (asked for every new report)
# --------------------------------------------------------------------------

ETCHANT_USE_SUGGESTED = "suggested"
ETCHANT_OTHER = "other"


def etchant_confirmed() -> bool:
    return st.session_state.get("etchant.choice") in (ETCHANT_USE_SUGGESTED, ETCHANT_OTHER)


def current_etchant() -> str:
    """The confirmed etchant for this report; empty until the inspector confirms."""
    s = st.session_state
    if s.get("etchant.choice") == ETCHANT_USE_SUGGESTED:
        return (s.get("etchant.suggested") or "").strip()
    if s.get("etchant.choice") == ETCHANT_OTHER:
        return (s.get("etchant.other") or "").strip()
    return ""


def validate_form(report: InspectionReport) -> ValidationResult:
    """Full validation of the report being entered (stored-report rules + per-report entries)."""
    result = validate_report(report)
    entry = validate_new_entry(report, etchant_confirmed())
    return ValidationResult(errors=entry.errors + result.errors,
                            warnings=result.warnings + entry.warnings)


def load_report(report: InspectionReport, config_source: str = "report",
                reading_count: int = 3, confirm_etchant: bool = True) -> None:
    """Write a report into session state. Call from a button callback.

    Reopened history reports keep their values (etchant counted as confirmed);
    a new report passes ``confirm_etchant=False`` so the inspector must confirm.
    """
    st.session_state.update(report_to_state(report, reading_count))
    etchant = report.metallography.etchant.strip()
    st.session_state["etchant.suggested"] = etchant
    st.session_state["etchant.choice"] = ETCHANT_USE_SUGGESTED if confirm_etchant and etchant else None
    st.session_state["etchant.other"] = ""
    st.session_state["config_source"] = config_source
    st.session_state["report_config"] = extract_config(report)
    for key in _TRANSIENT_KEYS:
        st.session_state.pop(key, None)


def start_new_report() -> None:
    """New report: saved defaults for reusable settings; report-specific fields start
    blank (customer, inspector, specimen IDs) or as suggestions (etchant to be
    confirmed, magnification editable). Usable as a button callback."""
    defaults = load_defaults(get_repository())
    report = InspectionReport(info=InspectionInfo(report_date=date.today().isoformat()))
    report.metallography.etchant = defaults.suggested_etchant
    report.metallography.magnification = defaults.initial_magnification
    load_report(report, config_source="defaults", reading_count=defaults.reading_count,
                confirm_etchant=False)


def use_saved_defaults() -> None:
    """Switch the current report to the saved defaults (button callback)."""
    st.session_state["config_source"] = "defaults"
    st.session_state.pop("generated", None)


# --------------------------------------------------------------------------
# Defaults editor ("def." keys on the Settings page)
# --------------------------------------------------------------------------

def defaults_to_state(defaults: ReportDefaults) -> None:
    """Load saved defaults into the Settings widgets. Call from a callback."""
    s = st.session_state
    config = defaults.config
    for section, names in CONFIG_FIELDS.items():
        obj = getattr(config, section)
        for name in names:
            s[f"def.{section}.{name}"] = getattr(obj, name)
    s["def.criteria.source"] = config.criteria.source
    for key in AcceptanceCriteria.CRITERION_KEYS:
        crit = getattr(config.criteria, key)
        for f in fields(Criterion):
            s[f"def.criteria.{key}.{f.name}"] = getattr(crit, f.name)
    s["def.reading_count"] = defaults.reading_count
    s["def.suggested_etchant"] = defaults.suggested_etchant
    s["def.initial_magnification"] = defaults.initial_magnification


def defaults_from_state(seeded_from: str = "") -> ReportDefaults:
    s = st.session_state
    config = InspectionReport()
    for section, names in CONFIG_FIELDS.items():
        obj = getattr(config, section)
        for name in names:
            value = s.get(f"def.{section}.{name}")
            setattr(obj, name, value.strip() if isinstance(value, str) else value)
    config.criteria.source = (s.get("def.criteria.source") or "").strip()
    for key in AcceptanceCriteria.CRITERION_KEYS:
        crit = Criterion(**{f.name: s.get(f"def.criteria.{key}.{f.name}") for f in fields(Criterion)})
        crit.mandatory = bool(crit.mandatory)
        if key == "elongation":
            crit.unit = "%"
        setattr(config.criteria, key, crit)
    return ReportDefaults(
        config=config, reading_count=int(s.get("def.reading_count") or 3), seeded_from=seeded_from,
        suggested_etchant=(s.get("def.suggested_etchant") or "").strip() or DEFAULT_SUGGESTED_ETCHANT,
        initial_magnification=((s.get("def.initial_magnification") or "").strip()
                               or DEFAULT_INITIAL_MAGNIFICATION),
    )


def init_state() -> None:
    if "initialized" not in st.session_state:
        start_new_report()
        defaults_to_state(load_defaults(get_repository()))
        st.session_state["initialized"] = True
