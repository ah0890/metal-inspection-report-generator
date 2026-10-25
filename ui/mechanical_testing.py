"""Mechanical test readings. Units, scale and methods come from the saved settings."""

from __future__ import annotations

import streamlit as st

from config import settings
from models.inspection import InspectionReport
from services.calculation_service import average_hardness
from services.formatting import format_number
from ui.state import reading_key

NO_UNIT = "unit not set"


def _label(name: str, unit: str | None) -> str:
    return f"{name} ({unit or NO_UNIT})"


def render_mechanical(config: InspectionReport) -> None:
    t, h = config.tensile, config.hardness

    st.markdown("#### Mechanical Testing")
    c1, c2, c3 = st.columns(3)
    c1.number_input(_label("Yield Strength", t.yield_unit), key="tensile.yield_strength", value=None,
                    step=1.0, format="%.2f", placeholder="Enter reading")
    c2.number_input(_label("Ultimate Tensile Strength", t.uts_unit), key="tensile.uts", value=None,
                    step=1.0, format="%.2f", placeholder="Enter reading")
    c3.number_input("Percentage Elongation (%)", key="tensile.elongation", value=None,
                    step=0.1, format="%.1f", placeholder="Enter reading")

    scale = h.scale or ""
    c1, c2 = st.columns([1, 3])
    c1.number_input("Number of hardness readings", key="hardness.count", min_value=1,
                    max_value=settings.MAX_HARDNESS_READINGS, step=1)
    count = int(st.session_state.get("hardness.count") or 1)
    with c2:
        cols = st.columns(min(count, 5))
        for i in range(count):
            cols[i % len(cols)].number_input(_label(f"Hardness {i + 1}", h.scale), key=reading_key(i),
                                             value=None, step=0.5, format="%.1f", placeholder="—")

    entered = [r for i in range(count) if (r := st.session_state.get(reading_key(i))) is not None]
    if entered and all(r >= 0 for r in entered):
        st.caption(f"Average hardness (calculated): **{format_number(average_hardness(entered), 1)} "
                   f"{scale}** from {len(entered)} reading(s)")
    elif entered:
        st.error("Hardness readings cannot be negative.")
