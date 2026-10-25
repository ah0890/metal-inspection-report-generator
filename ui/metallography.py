"""Metallography entries for the current report.

Specimen ID, magnification and etchant are report-specific: the specimen ID
starts blank, magnification starts at the suggested value (100X) and can be
changed, and the suggested etchant (Nital) must be confirmed or replaced on
every new report. The grain size method comes from the saved settings.
"""

from __future__ import annotations

import streamlit as st

from config import settings
from ui.state import ETCHANT_OTHER, ETCHANT_USE_SUGGESTED

MAGNIFICATIONS = ["50X", "100X", "200X", "400X", "500X", "1000X"]


def _etchant_confirmation() -> None:
    suggested = (st.session_state.get("etchant.suggested") or "").strip()
    labels = {
        ETCHANT_USE_SUGGESTED: f"Yes — {suggested} is appropriate for this specimen",
        ETCHANT_OTHER: "No — another etchant was used",
    }
    options = [ETCHANT_USE_SUGGESTED, ETCHANT_OTHER] if suggested else [ETCHANT_OTHER]
    question = (f"Etchant: is **{suggested}** appropriate for this specimen? *"
                if suggested else "Etchant: please enter the etchant used *")
    st.radio(question, options, key="etchant.choice", index=None, format_func=labels.get,
             horizontal=True)
    if st.session_state.get("etchant.choice") == ETCHANT_OTHER:
        st.text_input("Etchant used for this specimen *", key="etchant.other",
                      max_chars=settings.MAX_CHARS_SHORT, placeholder="e.g. Keller's reagent")
    elif st.session_state.get("etchant.choice") is None:
        st.caption("Please confirm the etchant for this inspection; it is not assumed.")


def render_metallography() -> None:
    st.markdown("#### Metallography")
    c1, c2, c3 = st.columns(3)
    c1.text_input("Metallography Specimen ID *", key="metallography.specimen_id", max_chars=40,
                  help="Enter the specimen ID for this inspection.")
    c2.number_input("Grain Size Number", key="metallography.grain_size", value=None, step=0.5,
                    format="%.1f", placeholder="Enter reading",
                    help="Grain size number, e.g. 8 for ASTM No. 8. Higher numbers are finer.")
    current = st.session_state.get("metallography.magnification") or ""
    options = MAGNIFICATIONS + ([current] if current and current not in MAGNIFICATIONS else [])
    c3.selectbox("Magnification", options, key="metallography.magnification",
                 accept_new_options=True, help="Starts at 100X. Choose or type another value.")
    _etchant_confirmation()
    st.text_area("Microstructure Observation", key="metallography.microstructure",
                 max_chars=settings.MAX_CHARS_OBSERVATION, height=68,
                 help="Free text. Claude can reword this in the AI Summary tab.")
