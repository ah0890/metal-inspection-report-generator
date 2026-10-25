"""Report History tab: search, reopen and regenerate saved reports."""

from __future__ import annotations

import pandas as pd
import streamlit as st

from database.database import ReportRepository
from services.report_service import ReportValidationError, build_pdf
from ui.state import load_report

_COLUMNS = {
    "report_number": "Report No.",
    "report_date": "Date",
    "material": "Material",
    "grade": "Grade",
    "heat_batch": "Heat / Batch",
    "customer": "Customer / Dept.",
    "inspector": "Inspector",
    "overall_result": "Result",
    "updated_at": "Last saved",
}


def _reopen(repo: ReportRepository, report_id: int) -> None:
    report = repo.load(report_id)
    if report is not None:
        load_report(report)
        st.session_state["history_notice"] = (
            f"Report {report.info.report_number} reopened. Switch to the other tabs to edit it."
        )


def render_history(repo: ReportRepository) -> None:
    st.subheader("Report History")
    st.caption("Reports are saved automatically when a PDF or Word report is generated.")

    c1, c2, c3 = st.columns(3)
    number = c1.text_input("Search by Report Number", key="hist.number")
    material = c2.text_input("Search by Material", key="hist.material")
    heat = c3.text_input("Search by Heat / Batch Number", key="hist.heat")

    rows = repo.search(report_number=number, material=material, heat_batch=heat)
    if st.session_state.get("history_notice"):
        st.success(st.session_state.pop("history_notice"))
    if not rows:
        st.info("No saved reports match the search.")
        return

    df = pd.DataFrame(rows)
    df["report_number"] = df.apply(
        lambda r: f"{r['report_number']} (SAMPLE)" if r["is_sample"] else r["report_number"], axis=1
    )
    st.dataframe(df[list(_COLUMNS)].rename(columns=_COLUMNS), hide_index=True,
                 width="stretch")

    labels = {r["id"]: f"{r['report_number']} — {r['material'] or '—'} — {r['report_date'] or ''}"
              for r in rows}
    selected = st.selectbox("Select a report", list(labels), format_func=labels.get,
                            key="hist.selected")
    c1, c2, c3 = st.columns(3)
    c1.button("Reopen in form", icon="📂", on_click=_reopen, args=(repo, selected),
              width="stretch")
    if c2.button("Generate PDF again", icon="📄", width="stretch"):
        report = repo.load(selected)
        try:
            st.session_state["history_pdf"] = build_pdf(report)
        except ReportValidationError as e:
            st.error("Saved report failed validation: " + "; ".join(e.validation.errors))
    if c3.button("Delete from history", icon="🗑️", width="stretch"):
        st.session_state["confirm_delete"] = selected
    if st.session_state.get("confirm_delete") == selected:
        st.warning(f"Delete {labels[selected]} permanently?")
        d1, d2 = st.columns(2)
        if d1.button("Yes, delete", type="primary"):
            repo.delete(selected)
            st.session_state.pop("confirm_delete", None)
            st.session_state.pop("history_pdf", None)
            st.rerun()
        if d2.button("Cancel"):
            st.session_state.pop("confirm_delete", None)
            st.rerun()

    pdf = st.session_state.get("history_pdf")
    if pdf is not None:
        st.download_button(f"Download {pdf.filename}", data=pdf.data, file_name=pdf.filename,
                           mime=pdf.mime, icon="⬇️", type="primary")
