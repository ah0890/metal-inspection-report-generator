"""Metallography readings. Method, etchant and magnification come from the saved settings."""

from __future__ import annotations

import streamlit as st

from config import settings


def render_metallography() -> None:
    st.markdown("#### Metallography")
    c1, c2 = st.columns([1, 3])
    c1.number_input("Grain Size Number", key="metallography.grain_size", value=None, step=0.5,
                    format="%.1f", placeholder="Enter reading",
                    help="Grain size number, e.g. 8 for ASTM No. 8. Higher numbers are finer.")
    c2.text_area("Microstructure Observation", key="metallography.microstructure",
                 max_chars=settings.MAX_CHARS_OBSERVATION, height=68,
                 help="Free text. Claude can reword this in the AI Summary tab.")
