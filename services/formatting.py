"""Shared display formatting for the UI and the report generators."""

from __future__ import annotations

from typing import Optional

NOT_SPECIFIED = "Acceptance criterion not specified"
NOT_REPORTED = "Not reported"


def format_number(value: Optional[float], decimals: int = 3) -> str:
    """Format a number without trailing zeros: 275.0 -> '275', 12.40 -> '12.4'."""
    if value is None:
        return ""
    text = f"{value:.{decimals}f}".rstrip("0").rstrip(".")
    return "0" if text in ("", "-0") else text


def with_unit(value: Optional[float], unit: Optional[str], decimals: int = 3) -> str:
    if value is None:
        return NOT_REPORTED
    number = format_number(value, decimals)
    return f"{number} {unit}" if unit else number


def grain_size_text(value: Optional[float]) -> str:
    return NOT_REPORTED if value is None else f"No. {format_number(value)}"


def limits_text(minimum: Optional[float], maximum: Optional[float], unit: Optional[str]) -> str:
    """Human-readable requirement for a min / max / range criterion.

    Uses 'Min.' / 'Max.' rather than >= / <= symbols so the text renders with
    the standard PDF fonts on every printer.
    """
    suffix = f" {unit}" if unit else ""
    if minimum is not None and maximum is not None:
        return f"{format_number(minimum)} – {format_number(maximum)}{suffix}"
    if minimum is not None:
        return f"Min. {format_number(minimum)}{suffix}"
    if maximum is not None:
        return f"Max. {format_number(maximum)}{suffix}"
    return NOT_SPECIFIED


def grain_limits_text(minimum: Optional[float], maximum: Optional[float]) -> str:
    """Grain size numbers increase as grains get finer (e.g. ASTM E112)."""
    if minimum is not None and maximum is not None:
        return f"No. {format_number(minimum)} – {format_number(maximum)}"
    if minimum is not None:
        return f"No. {format_number(minimum)} or finer"
    if maximum is not None:
        return f"No. {format_number(maximum)} or coarser"
    return NOT_SPECIFIED
