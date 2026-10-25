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
from models.defaults import CONFIG_FIELDS, ReportDefaults, apply_config, extract_config
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
    report = InspectionReport(
        info=info,
        tensile=section("tensile", TensileTest),
        hardness=HardnessTest(readings=[float(r) for r in readings if r is not None]),
        metallography=section("metallography", Metallography),
        ai=section("ai", AIText),
    )
    return apply_config(report, current_config())


def load_report(report: InspectionReport, config_source: str = "report",
                reading_count: int = 3) -> None:
    """Write a report into session state. Call from a button callback."""
    st.session_state.update(report_to_state(report, reading_count))
    st.session_state["config_source"] = config_source
    st.session_state["report_config"] = extract_config(report)
    for key in _TRANSIENT_KEYS:
        st.session_state.pop(key, None)


def start_new_report() -> None:
    """Blank report that uses the saved defaults. Usable as a button callback."""
    defaults = load_defaults(get_repository())
    report = InspectionReport(info=InspectionInfo(report_date=date.today().isoformat()))
    load_report(report, config_source="defaults", reading_count=defaults.reading_count)


def use_saved_defaults() -> None:
    """Switch the current report to the saved defaults (button callback)."""
    st.session_state["config_source"] = "defaults"
    st.session_state.pop("generated", None)


# --------------------------------------------------------------------------
# Defaults editor ("def." keys on the Settings page)
# --------------------------------------------------------------------------

def defaults_to_state(config: InspectionReport, reading_count: int) -> None:
    """Load a configuration into the Settings widgets. Call from a callback."""
    s = st.session_state
    for section, names in CONFIG_FIELDS.items():
        obj = getattr(config, section)
        for name in names:
            s[f"def.{section}.{name}"] = getattr(obj, name)
    s["def.criteria.source"] = config.criteria.source
    for key in AcceptanceCriteria.CRITERION_KEYS:
        crit = getattr(config.criteria, key)
        for f in fields(Criterion):
            s[f"def.criteria.{key}.{f.name}"] = getattr(crit, f.name)
    s["def.reading_count"] = reading_count


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
    return ReportDefaults(config=config, reading_count=int(s.get("def.reading_count") or 3),
                          seeded_from=seeded_from)


def init_state() -> None:
    if "initialized" not in st.session_state:
        start_new_report()
        defaults = load_defaults(get_repository())
        defaults_to_state(defaults.config, defaults.reading_count)
        st.session_state["initialized"] = True
