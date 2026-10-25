"""Reusable report configuration ("defaults").

The defaults are the parts of a report that stay the same from one
inspection to the next: units, test methods / standards, metallography
conventions, acceptance criteria and recurring header details. Measured
values (readings, observations, specimen IDs) are never part of the defaults.

The configuration is held as an ``InspectionReport`` that contains only the
fields listed in ``CONFIG_FIELDS``, so it can be copied into or out of any
report with the same model the rest of the application uses.
"""

from __future__ import annotations

import copy
from dataclasses import dataclass, field
from typing import Optional

from models.inspection import AcceptanceCriteria, InspectionReport

# Reusable fields per report section. Everything else is entered per inspection.
CONFIG_FIELDS: dict[str, tuple[str, ...]] = {
    "info": ("customer", "inspector", "specification", "drawing_number"),
    "tensile": (
        "yield_unit", "uts_unit", "gauge_length", "gauge_length_unit",
        "test_temperature", "temperature_unit", "method",
    ),
    "hardness": ("scale", "load_condition", "method"),
    "metallography": ("grain_size_method", "etchant", "magnification"),
}

# Human-readable names, used by the Settings page and the missing-settings check.
FIELD_LABELS: dict[str, str] = {
    "info.customer": "Customer / Department",
    "info.inspector": "Inspector Name",
    "info.specification": "Specification / Standard",
    "info.drawing_number": "Drawing / Specification Number",
    "tensile.yield_unit": "Yield Strength unit",
    "tensile.uts_unit": "UTS unit",
    "tensile.gauge_length": "Gauge Length",
    "tensile.gauge_length_unit": "Gauge Length unit",
    "tensile.test_temperature": "Test Temperature",
    "tensile.temperature_unit": "Test Temperature unit",
    "tensile.method": "Tensile Test Method / Standard",
    "hardness.scale": "Hardness Scale",
    "hardness.load_condition": "Hardness Load / Indenter",
    "hardness.method": "Hardness Test Method / Standard",
    "metallography.grain_size_method": "Grain Size Standard / Method",
    "metallography.etchant": "Etchant",
    "metallography.magnification": "Magnification",
    "criteria.source": "Source of acceptance criteria",
}

_CRITERIA_LABELS = {
    "yield_strength": "Yield Strength",
    "uts": "UTS",
    "elongation": "Elongation",
    "hardness": "Hardness",
    "grain_size": "Grain Size",
}


@dataclass
class ReportDefaults:
    config: InspectionReport = field(default_factory=InspectionReport)
    reading_count: int = 3
    seeded_from: str = ""  # report number the defaults were first taken from

    def to_dict(self) -> dict:
        return {
            "config": self.config.to_dict(),
            "reading_count": self.reading_count,
            "seeded_from": self.seeded_from,
        }

    @classmethod
    def from_dict(cls, data: Optional[dict]) -> "ReportDefaults":
        data = data or {}
        return cls(
            config=extract_config(InspectionReport.from_dict(data.get("config"))),
            reading_count=int(data.get("reading_count") or 3),
            seeded_from=data.get("seeded_from", ""),
        )


def extract_config(report: InspectionReport) -> InspectionReport:
    """Copy only the reusable configuration out of a report (no readings)."""
    config = InspectionReport()
    for section, names in CONFIG_FIELDS.items():
        src, dst = getattr(report, section), getattr(config, section)
        for name in names:
            setattr(dst, name, copy.deepcopy(getattr(src, name)))
    config.criteria = copy.deepcopy(report.criteria)
    return config


def defaults_from_report(report: InspectionReport) -> ReportDefaults:
    count = report.hardness.count or 3
    return ReportDefaults(config=extract_config(report), reading_count=count,
                          seeded_from=report.info.report_number)


def apply_config(report: InspectionReport, config: InspectionReport) -> InspectionReport:
    """Overwrite the report's configuration fields with ``config`` (in place)."""
    for section, names in CONFIG_FIELDS.items():
        src, dst = getattr(config, section), getattr(report, section)
        for name in names:
            setattr(dst, name, copy.deepcopy(getattr(src, name)))
    report.criteria = copy.deepcopy(config.criteria)
    return report


def missing_settings(config: InspectionReport) -> list[str]:
    """Configuration items that are empty. Reported, never filled in by guessing."""
    missing = []
    for section, names in CONFIG_FIELDS.items():
        obj = getattr(config, section)
        for name in names:
            value = getattr(obj, name)
            if value is None or (isinstance(value, str) and not value.strip()):
                missing.append(FIELD_LABELS[f"{section}.{name}"])
    if not config.criteria.source.strip():
        missing.append(FIELD_LABELS["criteria.source"])
    for key in AcceptanceCriteria.CRITERION_KEYS:
        crit = getattr(config.criteria, key)
        if crit.mandatory and not crit.is_specified:
            missing.append(f"{_CRITERIA_LABELS[key]} acceptance limits (mandatory test)")
    return missing
