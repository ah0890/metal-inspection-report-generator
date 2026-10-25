"""Inspection tab: the only data entered for each new report.

Identification, customer, inspector, specimen IDs and readings are entered here
for every report. Units, methods, standards and acceptance limits are filled in
from the saved settings and shown read-only.
"""

from __future__ import annotations

import streamlit as st

from config import settings
from models.inspection import InspectionReport
from reports.content import build_content
from services.calculation_service import evaluate_report
from ui.mechanical_testing import render_mechanical
from ui.metallography import render_metallography
from ui.state import current_config, get_repository, use_saved_defaults

S = settings.MAX_CHARS_SHORT


def _pick(column: str) -> None:
    value = st.session_state.get(f"pick.info.{column}")
    if value:
        st.session_state[f"info.{column}"] = value
    st.session_state[f"pick.info.{column}"] = None


def _with_suggestions(col, label: str, column: str) -> None:
    """Blank text field plus an optional picker of previously used values (never preselected)."""
    col.text_input(label, key=f"info.{column}", max_chars=S)
    values = get_repository().report_field_values(column)
    if values:
        col.selectbox(f"Previously used {label}", values, index=None, key=f"pick.info.{column}",
                      placeholder="↳ or pick a previously used name", on_change=_pick,
                      args=(column,), label_visibility="collapsed")


def _identification() -> None:
    st.markdown("#### Report Identification")
    c1, c2, c3 = st.columns(3)
    c1.text_input("Report Number *", key="info.report_number", max_chars=40)
    c2.date_input("Date *", key="info.report_date", format="YYYY-MM-DD")
    c3.text_input("Material / Product *", key="info.material", max_chars=S)
    c1, c2 = st.columns(2)
    _with_suggestions(c1, "Customer / Department *", "customer")
    _with_suggestions(c2, "Inspector Name *", "inspector")
    c1, c2, c3 = st.columns(3)
    c1.text_input("Material Grade", key="info.grade", max_chars=S)
    c2.text_input("Heat / Batch Number", key="info.heat_batch", max_chars=S)
    c3.text_input("Sample Number", key="info.sample_number", max_chars=S)


def _optional_details() -> None:
    with st.expander("Optional details for this report (preparation, remarks)"):
        st.text_area("Metallographic Preparation Remarks", key="metallography.preparation_remarks",
                     max_chars=settings.MAX_CHARS_REMARKS, height=68)
        st.text_area("Remarks", key="info.remarks", max_chars=settings.MAX_CHARS_REMARKS, height=68)
        st.checkbox("Mark as SAMPLE DATA (adds a watermark to the report)", key="info.is_sample")


def _applied_settings(config: InspectionReport) -> None:
    from_report = st.session_state.get("config_source") == "report"
    title = ("Settings stored with this report" if from_report
             else "Saved default settings applied to this report")
    with st.expander(f"⚙️ {title}", expanded=False):
        if from_report:
            st.info("This report was reopened from history (or is sample data), so it keeps the "
                    "units, standards and limits it was created with.")
            st.button("Use the saved defaults instead", on_click=use_saved_defaults)
        else:
            st.caption("Change these in **Settings / Edit Defaults**. They are used automatically "
                       "for every new report.")
        # Show exactly what will be printed, using the report's own formatting.
        content = build_content(config, evaluate_report(config))
        rows = [{"Test": i.name + (" *" if i.mandatory else ""), "Requirement": i.requirement_text}
                for i in content.mechanical + content.metallography]
        st.dataframe(rows, hide_index=True, width="stretch")
        t, h, m, info = config.tensile, config.hardness, config.metallography, config.info
        st.markdown(
            f"- **Tensile method:** {t.method or '—'}\n"
            f"- **Hardness:** {h.scale or 'scale not set'} · {h.method or '—'}"
            f"{' · ' + h.load_condition if h.load_condition else ''}\n"
            f"- **Grain size method:** {m.grain_size_method or '—'}\n"
            f"- **Specification:** {info.specification or '—'} · **Drawing / Spec. No.:** "
            f"{info.drawing_number or '—'}\n"
            f"- **Criteria source:** {config.criteria.source or 'not specified'}"
        )


def render_inspection() -> None:
    config = current_config()
    st.subheader("New Inspection")
    st.caption("Enter the identification details and readings, then generate the report below. "
               "Fields marked * are required.")
    _identification()
    render_mechanical(config)
    render_metallography()
    _optional_details()
    _applied_settings(config)
