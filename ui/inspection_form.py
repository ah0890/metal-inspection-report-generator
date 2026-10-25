"""Inspection Information tab."""

from __future__ import annotations

import streamlit as st

from config import settings

S = settings.MAX_CHARS_SHORT


def render_inspection_info() -> None:
    st.subheader("Inspection Information")
    st.caption("Fields marked * are required.")

    st.markdown("**Report**")
    c1, c2, c3 = st.columns(3)
    c1.text_input("Report Number *", key="info.report_number", max_chars=40)
    c2.date_input("Date *", key="info.report_date", format="YYYY-MM-DD")
    c3.text_input("Inspector Name", key="info.inspector", max_chars=S)
    st.text_input("Customer / Department", key="info.customer", max_chars=S)

    st.markdown("**Material**")
    c1, c2 = st.columns(2)
    c1.text_input("Material / Product *", key="info.material", max_chars=S)
    c2.text_input("Material Grade", key="info.grade", max_chars=S)
    c1, c2 = st.columns(2)
    c1.text_input("Heat / Batch Number", key="info.heat_batch", max_chars=S)
    c2.text_input("Sample Number", key="info.sample_number", max_chars=S)

    st.markdown("**Specification**")
    c1, c2 = st.columns(2)
    c1.text_input("Drawing / Specification Number", key="info.drawing_number", max_chars=S)
    c2.text_input("Specification / Standard", key="info.specification", max_chars=S)

    st.text_area(
        "Remarks",
        key="info.remarks",
        max_chars=settings.MAX_CHARS_REMARKS,
        height=90,
        help="Free text. Claude can reword this professionally in the AI Summary tab.",
    )
    st.checkbox(
        "Mark as SAMPLE DATA (adds a watermark to the report)",
        key="info.is_sample",
    )
