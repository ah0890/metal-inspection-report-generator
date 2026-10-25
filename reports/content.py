"""Report content shared by the PDF and DOCX generators.

Decides *what* appears on the report (rows, labels, resolved texts). The
generators only decide *how* it looks, so changing a label or adding a row
here updates both output formats.
"""

from __future__ import annotations

from dataclasses import dataclass

from models.evaluation import EvaluationResult, OverallResult, Status, TestEvaluation
from models.inspection import InspectionReport
from services.formatting import format_number, with_unit

DASH = "—"
MECHANICAL_KEYS = ("yield_strength", "uts", "elongation", "hardness")
METALLOGRAPHY_KEYS = ("grain_size",)
STATUS_FOOTNOTE = (
    "* Mandatory test. Status is determined by direct numerical comparison of the "
    "result with the stated requirement (limits inclusive). No limits are assumed."
)


def _v(text: str) -> str:
    return text.strip() if text and text.strip() else DASH


def deterministic_summary(evaluation: EvaluationResult) -> str:
    """Fallback summary used when no AI / manual summary is provided."""
    counts = {s: sum(1 for i in evaluation.items if i.status == s) for s in Status}
    evaluated = counts[Status.PASS] + counts[Status.FAIL]
    parts = [
        f"{evaluated} test(s) were evaluated against the stated acceptance criteria: "
        f"{counts[Status.PASS]} passed and {counts[Status.FAIL]} failed."
    ]
    if counts[Status.REVIEW]:
        parts.append(f"{counts[Status.REVIEW]} test(s) could not be evaluated and require review.")
    parts.append(f"Overall result: {evaluation.overall.value}.")
    if evaluation.overall != OverallResult.PASS:
        parts.append(" ".join(evaluation.reasons[:3]))
    return " ".join(parts)


@dataclass
class ReportContent:
    title: str
    report_number: str
    report_date: str
    is_sample: bool
    info_rows: list[tuple[str, str, str, str]]
    mechanical: list[TestEvaluation]
    tensile_details: str
    hardness_details: str
    criteria_source: str
    metallography: list[TestEvaluation]
    metallography_rows: list[tuple[str, str, str, str]]
    microstructure: str
    summary: str
    remarks: str
    overall: OverallResult
    overall_reasons: list[str]
    inspector: str
    preparation: str
    footnote: str = STATUS_FOOTNOTE
    ai_used: bool = False


def build_content(report: InspectionReport, evaluation: EvaluationResult) -> ReportContent:
    info, t, h, m, ai = report.info, report.tensile, report.hardness, report.metallography, report.ai

    info_rows = [
        ("Report No.", _v(info.report_number), "Date", _v(info.report_date)),
        ("Customer / Dept.", _v(info.customer), "Inspector", _v(info.inspector)),
        ("Material / Product", _v(info.material), "Grade", _v(info.grade)),
        ("Heat / Batch No.", _v(info.heat_batch), "Sample No.", _v(info.sample_number)),
        ("Drawing / Spec. No.", _v(info.drawing_number), "Specification", _v(info.specification)),
    ]

    tensile_bits = []
    if t.specimen_id:
        tensile_bits.append(f"Specimen {t.specimen_id}")
    if t.gauge_length is not None:
        tensile_bits.append(f"Gauge length {with_unit(t.gauge_length, t.gauge_length_unit)}")
    if t.test_temperature is not None:
        tensile_bits.append(f"Test temp. {with_unit(t.test_temperature, t.temperature_unit)}")
    if t.method:
        tensile_bits.append(f"Method {t.method}")

    hardness_bits = []
    if h.readings:
        readings = ", ".join(format_number(r, 1) for r in h.readings)
        hardness_bits.append(f"Readings {readings} {h.scale or ''}".rstrip() + f" (n = {h.count})")
    if h.load_condition:
        hardness_bits.append(f"Load / indenter {h.load_condition}")
    if h.method:
        hardness_bits.append(f"Method {h.method}")

    metallography_rows = [
        ("Specimen ID", _v(m.specimen_id), "Magnification", _v(m.magnification)),
        ("Etchant", _v(m.etchant), "Grain Size Method", _v(m.grain_size_method)),
    ]

    by_key = {i.key: i for i in evaluation.items}
    summary = ai.summary.strip() or deterministic_summary(evaluation)

    return ReportContent(
        title="METAL INSPECTION REPORT",
        report_number=_v(info.report_number),
        report_date=_v(info.report_date),
        is_sample=info.is_sample,
        info_rows=info_rows,
        mechanical=[by_key[k] for k in MECHANICAL_KEYS if k in by_key],
        tensile_details=" · ".join(tensile_bits),
        hardness_details=" · ".join(hardness_bits),
        criteria_source=report.criteria.source.strip(),
        metallography=[by_key[k] for k in METALLOGRAPHY_KEYS if k in by_key],
        metallography_rows=metallography_rows,
        microstructure=_v(ai.microstructure or m.microstructure),
        summary=summary,
        remarks=(ai.remarks or info.remarks).strip(),
        overall=evaluation.overall,
        overall_reasons=evaluation.reasons,
        inspector=info.inspector.strip(),
        ai_used=bool(ai.summary.strip() or ai.microstructure.strip() or ai.remarks.strip()),
        preparation=m.preparation_remarks.strip(),
    )
