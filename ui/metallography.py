"""Metallography tab."""

from __future__ import annotations

import streamlit as st

from config import settings


def render_metallography() -> None:
    st.subheader("Metallography")

    c1, c2, c3 = st.columns(3)
    c1.number_input("Grain Size Number", key="metallography.grain_size", value=None, step=0.5,
                    format="%.1f", placeholder="Not entered",
                    help="Grain size number, e.g. 8 for ASTM No. 8. Higher numbers are finer.")
    c2.text_input("Grain Size Standard / Method", key="metallography.grain_size_method",
                  max_chars=settings.MAX_CHARS_SHORT)
    c3.text_input("Specimen ID", key="metallography.specimen_id", max_chars=40)

    c1, c2 = st.columns(2)
    c1.text_input("Etchant", key="metallography.etchant", max_chars=settings.MAX_CHARS_SHORT)
    c2.text_input("Magnification", key="metallography.magnification", max_chars=20,
                  placeholder="e.g. 100X")

    st.text_area("Microstructure Observation", key="metallography.microstructure",
                 max_chars=settings.MAX_CHARS_OBSERVATION, height=110,
                 help="Free text. Claude can reword this professionally in the AI Summary tab.")
    st.text_area("Metallographic Preparation Remarks", key="metallography.preparation_remarks",
                 max_chars=settings.MAX_CHARS_REMARKS, height=70)
