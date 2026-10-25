"""Report orchestration: validate -> evaluate -> render -> record in history.

The UI calls these functions; they hold no Streamlit code so they can be
reused from scripts or tests.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Optional

from database.database import ReportRepository
from models.evaluation import EvaluationResult
from models.inspection import InspectionReport
from reports.docx_generator import generate_docx
from reports.pdf_generator import generate_pdf
from services.calculation_service import evaluate_report
from services.validation_service import ValidationResult, validate_report


class ReportValidationError(Exception):
    def __init__(self, validation: ValidationResult):
        self.validation = validation
        super().__init__("; ".join(validation.errors))


@dataclass
class GeneratedReport:
    data: bytes
    filename: str
    mime: str
    evaluation: EvaluationResult
    page_count: Optional[int] = None


def safe_filename(report: InspectionReport, extension: str) -> str:
    number = re.sub(r"[^A-Za-z0-9._-]+", "_", report.info.report_number.strip()) or "report"
    return f"Inspection_Report_{number}.{extension}"


def _prepare(report: InspectionReport) -> EvaluationResult:
    validation = validate_report(report)
    if not validation.is_valid:
        raise ReportValidationError(validation)
    # Always re-evaluate at generation time so the report can never show a
    # stale result.
    return evaluate_report(report)


def build_pdf(report: InspectionReport, repo: Optional[ReportRepository] = None) -> GeneratedReport:
    evaluation = _prepare(report)
    pdf = generate_pdf(report, evaluation)
    if repo is not None:
        repo.save(report, evaluation.overall.value)
    return GeneratedReport(pdf.data, safe_filename(report, "pdf"), "application/pdf",
                           evaluation, pdf.page_count)


def build_docx(report: InspectionReport, repo: Optional[ReportRepository] = None) -> GeneratedReport:
    evaluation = _prepare(report)
    data = generate_docx(report, evaluation)
    if repo is not None:
        repo.save(report, evaluation.overall.value)
    return GeneratedReport(
        data, safe_filename(report, "docx"),
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        evaluation,
    )
