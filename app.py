"""Metal Inspection Report Generator — Streamlit entry point.

Run with:  streamlit run app.py
"""

from __future__ import annotations

import streamlit as st

from config import settings
from database.database import ReportRepository
from models.sample_data import sample_report
from services import claude_service
from services.calculation_service import evaluate_report
from services.validation_service import validate_report
from ui.acceptance_criteria import render_criteria
from ui.ai_summary import render_ai_summary
from ui.generate_report import render_generate
from ui.history import render_history
from ui.inspection_form import render_inspection_info
from ui.mechanical_testing import render_mechanical
from ui.metallography import render_metallography
from ui.state import init_state, load_report, new_report, report_from_state

st.set_page_config(page_title="Metal Inspection Report Generator", page_icon="🔩", layout="wide")


@st.cache_resource
def get_repository() -> ReportRepository:
    return ReportRepository()


def _sidebar() -> None:
    with st.sidebar:
        st.title("🔩 Metal Inspection")
        st.caption(settings.LAB_NAME)

        st.button("Load Sample Data", icon="🧪", width="stretch",
                  on_click=load_report, args=(sample_report(),))
        st.button("New Report", icon="🆕", width="stretch",
                  on_click=load_report, args=(new_report(),))

        report = report_from_state()
        if report.info.is_sample:
            st.warning("**SAMPLE DATA** loaded — the report will be watermarked.")

        st.divider()
        st.markdown("**Live status**")
        validation = validate_report(report)
        if validation.is_valid:
            overall = evaluate_report(report).overall.value
            icon = {"PASS": "🟢", "FAIL": "🔴"}.get(overall, "🟠")
            st.markdown(f"{icon} Overall: **{overall}**")
        else:
            st.markdown("⚠️ **Incomplete** — please fix:")
            st.caption("\n".join(f"- {e}" for e in validation.errors))

        st.divider()
        if claude_service.is_configured():
            st.caption(f"✅ AI wording available ({settings.CLAUDE_MODEL})")
        else:
            st.caption(f"⚪ AI wording off — `{settings.ANTHROPIC_API_KEY_ENV}` not set")


def main() -> None:
    init_state()
    repo = get_repository()
    _sidebar()

    st.title("Metal Inspection Report Generator")
    tabs = st.tabs([
        "1 · Inspection Information",
        "2 · Mechanical Testing",
        "3 · Metallography",
        "4 · Acceptance Criteria",
        "5 · AI Summary",
        "6 · Generate Report",
        "Report History",
    ])
    with tabs[0]:
        render_inspection_info()
    with tabs[1]:
        render_mechanical()
    with tabs[2]:
        render_metallography()
    with tabs[3]:
        render_criteria()
    with tabs[4]:
        render_ai_summary()
    with tabs[5]:
        render_generate(repo)
    with tabs[6]:
        render_history(repo)


main()
