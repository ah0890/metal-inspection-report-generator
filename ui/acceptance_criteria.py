"""Acceptance criteria editor, shown on the Settings / Edit Defaults page."""

from __future__ import annotations

import streamlit as st

from config import settings


def _criterion_row(key: str, label: str, units: list[str] | None, unit_label: str = "") -> None:
    c0, c1, c2, c3, c4 = st.columns([2.2, 1.6, 1.6, 1.6, 1.2])
    c0.markdown(f"**{label}**")
    c1.number_input("Minimum", key=f"def.criteria.{key}.minimum", value=None, step=1.0,
                    format="%.2f", placeholder="Not specified", label_visibility="collapsed")
    c2.number_input("Maximum", key=f"def.criteria.{key}.maximum", value=None, step=1.0,
                    format="%.2f", placeholder="Not specified", label_visibility="collapsed")
    if units:
        c3.selectbox("Unit", units, key=f"def.criteria.{key}.unit", index=None,
                     placeholder="Select", label_visibility="collapsed")
    else:
        c3.markdown(unit_label)
    c4.checkbox("Mandatory", key=f"def.criteria.{key}.mandatory")


def render_criteria_editor() -> None:
    st.markdown("#### Acceptance Criteria")
    st.caption(
        "Enter limits only from the governing specification, drawing or purchase order. "
        "**No limits are assumed for any material or grade.** Leave a limit empty if it is not "
        "specified — the report will state *\"Acceptance criterion not specified\"*, and a "
        "mandatory test without limits makes the result REVIEW REQUIRED."
    )
    st.text_input("Source of acceptance criteria (specification / PO / drawing)",
                  key="def.criteria.source", max_chars=settings.MAX_CHARS_SHORT)

    h0, h1, h2, h3, h4 = st.columns([2.2, 1.6, 1.6, 1.6, 1.2])
    for col, text in zip((h0, h1, h2, h3, h4), ("Test", "Minimum", "Maximum", "Unit / Scale", "Mandatory")):
        col.caption(text)
    _criterion_row("yield_strength", "Yield Strength", settings.STRENGTH_UNITS)
    _criterion_row("uts", "Ultimate Tensile Strength", settings.STRENGTH_UNITS)
    _criterion_row("elongation", "Elongation", None, "%")
    _criterion_row("hardness", "Hardness", settings.HARDNESS_SCALES)
    _criterion_row("grain_size", "Grain Size Number", None, "No. (min = finer limit)")
    st.caption(
        "Grain size: *Minimum* means \"No. N or finer\", *Maximum* means \"No. N or coarser\". "
        "Limit units must match the result units — no unit conversion is performed."
    )
