"""SAMPLE DATA for trying the application. Clearly flagged as sample on every output."""

from __future__ import annotations

from datetime import date

from models.inspection import (
    AcceptanceCriteria,
    Criterion,
    HardnessTest,
    InspectionInfo,
    InspectionReport,
    Metallography,
    TensileTest,
)


def sample_report() -> InspectionReport:
    return InspectionReport(
        info=InspectionInfo(
            report_number="SAMPLE-MIR-0001",
            report_date=date.today().isoformat(),
            customer="SAMPLE DATA – Production Department",
            material="Aluminium Alloy",
            grade="Example Alloy",
            heat_batch="HT-2026-001",
            sample_number="S-001",
            drawing_number="DRG-0000 (sample)",
            specification="Example Specification (sample)",
            inspector="Sample Inspector",
            remarks="sample data for demonstration only. all tests done as per lab procedure",
            is_sample=True,
        ),
        tensile=TensileTest(
            yield_strength=275.0,
            yield_unit="MPa",
            uts=325.0,
            uts_unit="MPa",
            elongation=12.4,
            gauge_length=50.0,
            gauge_length_unit="mm",
            specimen_id="T-001",
            test_temperature=23.0,
            temperature_unit="°C",
            method="Example tensile test method",
        ),
        hardness=HardnessTest(
            readings=[81.0, 82.0, 83.0],
            scale="HB",
            load_condition="",
            method="Example hardness test method",
        ),
        metallography=Metallography(
            grain_size=8.0,
            grain_size_method="Comparison method",
            microstructure="grain structure okay, uniform, no abnormal thing seen",
            etchant="Appropriate laboratory etchant",
            magnification="100X",
            specimen_id="M-001",
            preparation_remarks="Ground, polished and etched",
        ),
        criteria=AcceptanceCriteria(
            yield_strength=Criterion(minimum=250.0, unit="MPa"),
            uts=Criterion(minimum=300.0, unit="MPa"),
            elongation=Criterion(minimum=10.0, unit="%"),
            hardness=Criterion(minimum=70.0, maximum=90.0, unit="HB"),
            grain_size=Criterion(minimum=7.0),
            source="SAMPLE criteria (entered by user for demonstration)",
        ),
    )
