"""Acceptance Criteria tab and the deterministic Evaluate step."""

from __future__ import annotations

import streamlit as st

from config import settings
from services.calculation_service import evaluate_report
from services.validation_service import validate_report
from ui.evaluation_view import show_evaluation, show_validation
from ui.state import report_from_state


def _evaluation_inputs(report) -> dict:
    """Report data that affects the evaluation (AI wording does not)."""
    data = report.to_dict()
    data.pop("ai", None)
    return data


def _criterion_row(key: str, label: str, units: list[str] | None, unit_label: str = "") -> None:
    c0, c1, c2, c3, c4 = st.columns([2.2, 1.6, 1.6, 1.6, 1.2])
    c0.markdown(f"**{label}**")
    c1.number_input("Minimum", key=f"criteria.{key}.minimum", value=None, step=1.0,
                    format="%.2f", placeholder="Not specified", label_visibility="collapsed")
    c2.number_input("Maximum", key=f"criteria.{key}.maximum", value=None, step=1.0,
                    format="%.2f", placeholder="Not specified", label_visibility="collapsed")
    if units:
        c3.selectbox("Unit", units, key=f"criteria.{key}.unit", index=None,
                     placeholder="Select", label_visibility="collapsed")
    else:
        c3.markdown(unit_label)
    c4.checkbox("Mandatory", key=f"criteria.{key}.mandatory")


def render_criteria() -> None:
    st.subheader("Acceptance Criteria")
    st.info(
        "Enter limits only from the governing specification, drawing, purchase order or an "
        "explicitly selected standard. **No limits are assumed for any material or grade.** "
        "Leave a limit empty if it is not specified — the report will state "
        "*\"Acceptance criterion not specified\"*.",
        icon="📏",
    )
    st.text_input("Source of acceptance criteria (specification / PO / drawing)",
                  key="criteria.source", max_chars=settings.MAX_CHARS_SHORT)

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
        "Mandatory tests that fail make the overall result FAIL; a mandatory test without a "
        "criterion or result makes it REVIEW REQUIRED. Units must match the result — no unit "
        "conversion is performed."
    )

    st.divider()
    if st.button("Evaluate", type="primary", icon="🧮"):
        report = report_from_state()
        validation = validate_report(report)
        st.session_state["last_validation"] = validation
        if validation.is_valid:
            st.session_state["evaluation"] = evaluate_report(report)
            st.session_state["evaluated_data"] = _evaluation_inputs(report)
        else:
            st.session_state.pop("evaluation", None)

    if "last_validation" in st.session_state:
        show_validation(st.session_state["last_validation"])
    evaluation = st.session_state.get("evaluation")
    if evaluation is not None:
        if _evaluation_inputs(report_from_state()) != st.session_state.get("evaluated_data"):
            st.caption("⚠️ Data has changed since this evaluation. Click **Evaluate** again.")
        st.markdown("##### Evaluation (calculated by Python, not AI)")
        show_evaluation(evaluation)
