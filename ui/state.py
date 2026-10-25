"""Mapping between the InspectionReport model and Streamlit session state.

Every form widget is bound to a session-state key named "<section>.<field>"
(e.g. "tensile.uts", "criteria.uts.minimum"). Loading sample data, starting a
new report or reopening a saved report simply rewrites these keys.
"""

from __future__ import annotations

from dataclasses import fields
from datetime import date

import streamlit as st

from config import settings
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

DEFAULT_READING_COUNT = 3
_SIMPLE_SECTIONS = {
    "info": InspectionInfo,
    "tensile": TensileTest,
    "metallography": Metallography,
    "ai": AIText,
}
_HARDNESS_FIELDS = ("scale", "load_condition", "method")


def reading_key(i: int) -> str:
    return f"hardness.reading.{i}"


def report_to_state(report: InspectionReport) -> dict:
    """Flatten a report into session-state key/value pairs."""
    state: dict = {}
    for section, cls in _SIMPLE_SECTIONS.items():
        obj = getattr(report, section)
        for f in fields(cls):
            state[f"{section}.{f.name}"] = getattr(obj, f.name)

    try:
        state["info.report_date"] = date.fromisoformat(report.info.report_date)
    except ValueError:
        state["info.report_date"] = None

    for name in _HARDNESS_FIELDS:
        state[f"hardness.{name}"] = getattr(report.hardness, name)
    readings = report.hardness.readings[: settings.MAX_HARDNESS_READINGS]
    state["hardness.count"] = max(len(readings), 1) if readings else DEFAULT_READING_COUNT
    for i in range(settings.MAX_HARDNESS_READINGS):
        state[reading_key(i)] = readings[i] if i < len(readings) else None

    c = report.criteria
    state["criteria.source"] = c.source
    for key in AcceptanceCriteria.CRITERION_KEYS:
        crit: Criterion = getattr(c, key)
        for f in fields(Criterion):
            state[f"criteria.{key}.{f.name}"] = getattr(crit, f.name)
    return state


def report_from_state() -> InspectionReport:
    """Build a report from the current widget values."""
    s = st.session_state

    def section(name: str, cls):
        return cls(**{f.name: s.get(f"{name}.{f.name}", f.default) for f in fields(cls)
                      if f"{name}.{f.name}" in s})

    info: InspectionInfo = section("info", InspectionInfo)
    d = s.get("info.report_date")
    info.report_date = d.isoformat() if isinstance(d, date) else ""
    for attr in ("report_number", "customer", "material", "grade", "heat_batch", "sample_number",
                 "drawing_number", "specification", "inspector"):
        setattr(info, attr, (getattr(info, attr) or "").strip())

    count = int(s.get("hardness.count") or 0)
    readings = [s.get(reading_key(i)) for i in range(count)]
    hardness = HardnessTest(
        readings=[float(r) for r in readings if r is not None],
        **{name: s.get(f"hardness.{name}") for name in _HARDNESS_FIELDS},
    )
    hardness.load_condition = hardness.load_condition or ""
    hardness.method = hardness.method or ""

    criteria = AcceptanceCriteria(source=s.get("criteria.source", ""))
    for key in AcceptanceCriteria.CRITERION_KEYS:
        crit = Criterion(**{f.name: s.get(f"criteria.{key}.{f.name}") for f in fields(Criterion)})
        crit.mandatory = bool(crit.mandatory)
        if key == "elongation":
            crit.unit = "%"
        setattr(criteria, key, crit)

    return InspectionReport(
        info=info,
        tensile=section("tensile", TensileTest),
        hardness=hardness,
        metallography=section("metallography", Metallography),
        criteria=criteria,
        ai=section("ai", AIText),
    )


def load_report(report: InspectionReport) -> None:
    """Write a report into session state. Call from a button callback."""
    st.session_state.update(report_to_state(report))
    for key in ("evaluation", "evaluated_data", "last_validation", "generated", "ai_error", "ai_notice"):
        st.session_state.pop(key, None)


def new_report() -> InspectionReport:
    return InspectionReport(info=InspectionInfo(report_date=date.today().isoformat()))


def init_state() -> None:
    if "initialized" not in st.session_state:
        load_report(new_report())
        st.session_state["initialized"] = True
