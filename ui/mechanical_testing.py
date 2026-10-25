"""Mechanical Testing tab: tensile and hardness."""

from __future__ import annotations

import streamlit as st

from config import settings
from services.calculation_service import average_hardness
from services.formatting import format_number
from ui.state import reading_key

UNIT_PLACEHOLDER = "Select unit"


def _value_with_unit(label: str, value_key: str, unit_key: str, units: list[str], help: str = "") -> None:
    c1, c2 = st.columns([3, 2])
    c1.number_input(label, key=value_key, value=None, step=1.0, format="%.2f",
                    placeholder="Not entered", help=help or None)
    c2.selectbox(f"{label.rstrip(' *')} Unit", units, key=unit_key, index=None,
                 placeholder=UNIT_PLACEHOLDER)


def render_mechanical() -> None:
    st.subheader("Mechanical Testing")
    st.caption("Leave a value empty if the test was not performed. Units are never assumed — select one.")

    st.markdown("#### Tensile Test")
    c1, c2 = st.columns(2)
    with c1:
        _value_with_unit("Yield Strength", "tensile.yield_strength", "tensile.yield_unit",
                         settings.STRENGTH_UNITS)
        _value_with_unit("Ultimate Tensile Strength (UTS)", "tensile.uts", "tensile.uts_unit",
                         settings.STRENGTH_UNITS)
        st.number_input("Percentage Elongation (%)", key="tensile.elongation", value=None,
                        step=0.1, format="%.1f", placeholder="Not entered")
    with c2:
        _value_with_unit("Gauge Length", "tensile.gauge_length", "tensile.gauge_length_unit",
                         settings.LENGTH_UNITS)
        cc1, cc2 = st.columns([3, 2])
        cc1.number_input("Test Temperature (if applicable)", key="tensile.test_temperature",
                         value=None, step=1.0, format="%.1f", placeholder="Not entered")
        cc2.selectbox("Temperature Unit", settings.TEMPERATURE_UNITS, key="tensile.temperature_unit",
                      index=None, placeholder=UNIT_PLACEHOLDER)
        st.text_input("Tensile Test Specimen ID", key="tensile.specimen_id", max_chars=40)
    st.text_input("Tensile Test Method / Standard", key="tensile.method", max_chars=settings.MAX_CHARS_SHORT)

    st.divider()
    st.markdown("#### Hardness Test")
    c1, c2, c3 = st.columns(3)
    c1.selectbox("Hardness Scale", settings.HARDNESS_SCALES, key="hardness.scale", index=None,
                 placeholder="Select scale")
    c2.number_input("Number of Readings", key="hardness.count", min_value=1,
                    max_value=settings.MAX_HARDNESS_READINGS, step=1)
    c3.text_input("Load / Indenter (optional)", key="hardness.load_condition", max_chars=40)

    count = int(st.session_state.get("hardness.count") or 1)
    cols = st.columns(min(count, 5))
    for i in range(count):
        cols[i % len(cols)].number_input(f"Reading {i + 1}", key=reading_key(i), value=None,
                                         step=0.5, format="%.1f", placeholder="—")

    readings = [st.session_state.get(reading_key(i)) for i in range(count)]
    entered = [r for r in readings if r is not None]
    scale = st.session_state.get("hardness.scale") or ""
    if entered and all(r >= 0 for r in entered):
        avg = average_hardness(entered)
        st.metric("Average Hardness (calculated)", f"{format_number(avg, 1)} {scale}".strip(),
                  help=f"Arithmetic mean of {len(entered)} reading(s).")
    elif entered:
        st.error("Hardness readings cannot be negative.")
    else:
        st.info("Enter hardness readings to calculate the average automatically.")

    st.text_input("Hardness Test Method / Standard", key="hardness.method",
                  max_chars=settings.MAX_CHARS_SHORT)
