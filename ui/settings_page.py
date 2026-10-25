"""Settings / Edit Defaults: the reusable configuration used for every new report."""

from __future__ import annotations

import streamlit as st

from config import settings
from models.defaults import defaults_from_report, missing_settings
from services.defaults_service import load_defaults, save_defaults
from services.validation_service import validate_defaults
from ui.acceptance_criteria import render_criteria_editor
from ui.state import defaults_from_state, defaults_to_state, get_repository

S = settings.MAX_CHARS_SHORT


def _save() -> None:
    repo = get_repository()
    current = load_defaults(repo)
    defaults = defaults_from_state(seeded_from=current.seeded_from)
    errors = validate_defaults(defaults.config)
    if errors:
        st.session_state["settings_errors"] = errors
        return
    st.session_state.pop("settings_errors", None)
    save_defaults(repo, defaults)
    st.session_state["settings_notice"] = "Defaults saved. They will be used for all new reports."


def _discard() -> None:
    defaults = load_defaults(get_repository())
    defaults_to_state(defaults.config, defaults.reading_count)
    st.session_state.pop("settings_errors", None)
    st.session_state["settings_notice"] = "Unsaved changes discarded."


def _copy_from_history(report_id: int) -> None:
    report = get_repository().load(report_id)
    if report is not None:
        d = defaults_from_report(report)
        defaults_to_state(d.config, d.reading_count)
        st.session_state["settings_notice"] = (
            f"Settings copied from report {report.info.report_number}. Review them and click "
            "**Save defaults** to keep them."
        )


def _unit(label: str, key: str, options: list[str], col) -> None:
    col.selectbox(label, options, key=key, index=None, placeholder="Not set")


def render_settings() -> None:
    repo = get_repository()
    saved = load_defaults(repo)

    st.subheader("Settings / Edit Defaults")
    st.caption(
        "These units, standards, methods and acceptance limits are applied automatically to every "
        "new report. They change only when you click **Save defaults**."
    )
    if saved.seeded_from:
        st.caption(f"Defaults were first taken from report **{saved.seeded_from}**.")

    if st.session_state.get("settings_notice"):
        st.success(st.session_state.pop("settings_notice"))
    if st.session_state.get("settings_errors"):
        st.error("**Not saved — please correct:**\n\n"
                 + "\n".join(f"- {e}" for e in st.session_state["settings_errors"]))

    missing = missing_settings(saved.config)
    if missing:
        st.warning("**Not set in the saved defaults** (left empty rather than guessed):\n\n"
                   + "\n".join(f"- {m}" for m in missing))

    st.markdown("#### Report Header")
    c1, c2 = st.columns(2)
    c1.text_input("Customer / Department", key="def.info.customer", max_chars=S)
    c2.text_input("Inspector Name", key="def.info.inspector", max_chars=S)
    c1, c2 = st.columns(2)
    c1.text_input("Specification / Standard", key="def.info.specification", max_chars=S)
    c2.text_input("Drawing / Specification Number", key="def.info.drawing_number", max_chars=S)

    st.markdown("#### Tensile Test")
    c1, c2, c3 = st.columns(3)
    _unit("Yield Strength unit", "def.tensile.yield_unit", settings.STRENGTH_UNITS, c1)
    _unit("UTS unit", "def.tensile.uts_unit", settings.STRENGTH_UNITS, c2)
    c3.text_input("Elongation unit", value="%", disabled=True)
    c1, c2, c3, c4 = st.columns(4)
    c1.number_input("Gauge Length", key="def.tensile.gauge_length", value=None, step=1.0,
                    format="%.1f", placeholder="Not set")
    _unit("Gauge Length unit", "def.tensile.gauge_length_unit", settings.LENGTH_UNITS, c2)
    c3.number_input("Test Temperature", key="def.tensile.test_temperature", value=None, step=1.0,
                    format="%.1f", placeholder="Not set")
    _unit("Temperature unit", "def.tensile.temperature_unit", settings.TEMPERATURE_UNITS, c4)
    st.text_input("Tensile Test Method / Standard", key="def.tensile.method", max_chars=S)

    st.markdown("#### Hardness Test")
    c1, c2, c3 = st.columns(3)
    _unit("Hardness Scale", "def.hardness.scale", settings.HARDNESS_SCALES, c1)
    c2.text_input("Load / Indenter", key="def.hardness.load_condition", max_chars=40)
    c3.number_input("Default number of readings", key="def.reading_count", min_value=1,
                    max_value=settings.MAX_HARDNESS_READINGS, step=1)
    st.text_input("Hardness Test Method / Standard", key="def.hardness.method", max_chars=S)

    st.markdown("#### Metallography")
    c1, c2, c3 = st.columns(3)
    c1.text_input("Grain Size Standard / Method", key="def.metallography.grain_size_method", max_chars=S)
    c2.text_input("Etchant", key="def.metallography.etchant", max_chars=S)
    c3.text_input("Magnification", key="def.metallography.magnification", max_chars=20)

    render_criteria_editor()

    st.divider()
    c1, c2 = st.columns(2)
    c1.button("Save defaults", type="primary", icon="💾", on_click=_save, width="stretch")
    c2.button("Discard unsaved changes", on_click=_discard, width="stretch")

    with st.expander("Copy settings from a report in history"):
        rows = repo.search()
        if not rows:
            st.caption("No saved reports yet.")
        else:
            labels = {r["id"]: f"{r['report_number']}{' (SAMPLE)' if r['is_sample'] else ''} — "
                               f"{r['material'] or '—'} — {r['report_date'] or ''}" for r in rows}
            selected = st.selectbox("Report", list(labels), format_func=labels.get,
                                    key="def.copy_from")
            st.button("Copy its settings into the form above", on_click=_copy_from_history,
                      args=(selected,))
            st.caption("Only units, standards, methods and limits are copied — never readings.")
