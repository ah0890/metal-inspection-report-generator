"""Generate Report tab: PDF / Word output and saving to history."""

from __future__ import annotations

import streamlit as st

from database.database import ReportRepository
from services.calculation_service import evaluate_report
from services.report_service import ReportValidationError, build_docx, build_pdf
from services.validation_service import validate_report
from ui.evaluation_view import show_evaluation, show_validation
from ui.state import report_from_state


def render_generate(repo: ReportRepository) -> None:
    st.subheader("Generate Report")

    report = report_from_state()
    validation = validate_report(report)
    show_validation(validation)
    if validation.is_valid:
        show_evaluation(evaluate_report(report))
        if not report.ai.summary.strip():
            st.caption("No inspection summary entered — an automatic factual summary will be used.")
    else:
        st.info("The report can be generated once the errors above are corrected.")

    c1, c2 = st.columns(2)
    make_pdf = c1.button("Generate PDF", type="primary", icon="📄", width="stretch",
                         disabled=not validation.is_valid)
    make_docx = c2.button("Generate Word Report", icon="📝", width="stretch",
                          disabled=not validation.is_valid)

    try:
        if make_pdf:
            st.session_state["generated"] = build_pdf(report, repo)
        elif make_docx:
            st.session_state["generated"] = build_docx(report, repo)
    except ReportValidationError as e:
        show_validation(e.validation)

    generated = st.session_state.get("generated")
    if generated is not None:
        if generated.page_count and generated.page_count > 1:
            st.warning(f"The PDF needed {generated.page_count} pages even with compact layout. "
                       "Shorten the free-text fields to fit one page.")
        elif generated.page_count == 1:
            st.success("PDF generated — 1 page (A4). Saved to report history.")
        else:
            st.success("Word report generated. Saved to report history.")
        st.download_button(f"Download {generated.filename}", data=generated.data,
                           file_name=generated.filename, mime=generated.mime, icon="⬇️",
                           type="primary")
