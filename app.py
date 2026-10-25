"""Metal Inspection Report Generator — Streamlit entry point.

Run with:  streamlit run app.py
"""

from __future__ import annotations

import streamlit as st

from config import settings
from models.sample_data import sample_report
from services import claude_service
from services.calculation_service import evaluate_report
from services.validation_service import validate_report
from ui.ai_summary import render_ai_summary
from ui.company_settings import render_company_settings
from ui.covering_letter import render_covering_letter
from ui.generate_report import render_generate
from ui.history import render_history
from ui.inspection_form import render_inspection
from ui.settings_page import render_settings
from ui.state import get_repository, init_state, load_report, report_from_state, start_new_report

st.set_page_config(page_title="Metal Inspection Report Generator", page_icon="🔩", layout="wide")


def _sidebar() -> None:
    with st.sidebar:
        st.title("🔩 Metal Inspection")
        st.caption(settings.LAB_NAME)

        st.button("Load Sample Data", icon="🧪", width="stretch",
                  on_click=load_report, args=(sample_report(),))
        st.button("New Report", icon="🆕", width="stretch", on_click=start_new_report)

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
        "1 · Inspection & Report",
        "2 · AI Summary (optional)",
        "3 · Covering Letter",
        "Report History",
        "⚙️ Settings / Edit Defaults",
    ])
    with tabs[0]:
        render_inspection()
        st.divider()
        render_generate(repo)
    with tabs[1]:
        render_ai_summary()
    with tabs[2]:
        render_covering_letter()
    with tabs[3]:
        render_history(repo)
    with tabs[4]:
        defaults_tab, company_tab = st.tabs(["Report defaults", "Company letterhead"])
        with defaults_tab:
            render_settings()
        with company_tab:
            render_company_settings()


main()
