"""Data model for an inspection report.

Plain dataclasses keep the model independent of Streamlit, the database and
the report generators. ``None`` always means "not entered" — the application
never substitutes a default value or unit for missing data.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field, fields
from typing import Any, Optional


def _from_dict(cls, data: Optional[dict]) -> Any:
    """Build dataclass ``cls`` from a dict, ignoring unknown keys.

    Tolerating unknown/missing keys lets older saved reports reopen after
    fields are added or removed.
    """
    data = data or {}
    names = {f.name for f in fields(cls)}
    return cls(**{k: v for k, v in data.items() if k in names})


@dataclass
class InspectionInfo:
    report_number: str = ""
    report_date: str = ""  # ISO format YYYY-MM-DD
    customer: str = ""
    material: str = ""
    grade: str = ""
    heat_batch: str = ""
    sample_number: str = ""
    drawing_number: str = ""
    specification: str = ""
    inspector: str = ""
    remarks: str = ""
    is_sample: bool = False


@dataclass
class TensileTest:
    yield_strength: Optional[float] = None
    yield_unit: Optional[str] = None
    uts: Optional[float] = None
    uts_unit: Optional[str] = None
    elongation: Optional[float] = None  # always percent
    gauge_length: Optional[float] = None
    gauge_length_unit: Optional[str] = None
    specimen_id: str = ""
    test_temperature: Optional[float] = None
    temperature_unit: Optional[str] = None
    method: str = ""


@dataclass
class HardnessTest:
    readings: list[float] = field(default_factory=list)
    scale: Optional[str] = None
    load_condition: str = ""  # e.g. "10 mm ball / 3000 kgf"
    method: str = ""

    @property
    def count(self) -> int:
        return len(self.readings)

    @property
    def average(self) -> Optional[float]:
        # Imported lazily to avoid a circular import at module load.
        from services.calculation_service import average_hardness

        return average_hardness(self.readings)


@dataclass
class Metallography:
    grain_size: Optional[float] = None  # grain size number, e.g. 8 for ASTM No. 8
    grain_size_method: str = ""
    microstructure: str = ""
    etchant: str = ""
    magnification: str = ""
    specimen_id: str = ""
    preparation_remarks: str = ""


@dataclass
class Criterion:
    """A user-entered acceptance criterion. Both limits are optional."""

    minimum: Optional[float] = None
    maximum: Optional[float] = None
    unit: Optional[str] = None
    mandatory: bool = True

    @property
    def is_specified(self) -> bool:
        return self.minimum is not None or self.maximum is not None


@dataclass
class AcceptanceCriteria:
    yield_strength: Criterion = field(default_factory=Criterion)
    uts: Criterion = field(default_factory=Criterion)
    elongation: Criterion = field(default_factory=lambda: Criterion(unit="%"))
    hardness: Criterion = field(default_factory=Criterion)
    grain_size: Criterion = field(default_factory=Criterion)
    source: str = ""  # where the criteria come from (spec, PO, drawing...)

    CRITERION_KEYS = ("yield_strength", "uts", "elongation", "hardness", "grain_size")

    @classmethod
    def from_dict(cls, data: Optional[dict]) -> "AcceptanceCriteria":
        data = data or {}
        kwargs: dict[str, Any] = {"source": data.get("source", "")}
        for key in cls.CRITERION_KEYS:
            if key in data:
                kwargs[key] = _from_dict(Criterion, data[key])
        return cls(**kwargs)


@dataclass
class AIText:
    """Professionally worded text. Produced by Claude, always editable by the inspector."""

    summary: str = ""
    microstructure: str = ""
    remarks: str = ""


@dataclass
class InspectionReport:
    info: InspectionInfo = field(default_factory=InspectionInfo)
    tensile: TensileTest = field(default_factory=TensileTest)
    hardness: HardnessTest = field(default_factory=HardnessTest)
    metallography: Metallography = field(default_factory=Metallography)
    criteria: AcceptanceCriteria = field(default_factory=AcceptanceCriteria)
    ai: AIText = field(default_factory=AIText)

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Optional[dict]) -> "InspectionReport":
        data = data or {}
        return cls(
            info=_from_dict(InspectionInfo, data.get("info")),
            tensile=_from_dict(TensileTest, data.get("tensile")),
            hardness=_from_dict(HardnessTest, data.get("hardness")),
            metallography=_from_dict(Metallography, data.get("metallography")),
            criteria=AcceptanceCriteria.from_dict(data.get("criteria")),
            ai=_from_dict(AIText, data.get("ai")),
        )
