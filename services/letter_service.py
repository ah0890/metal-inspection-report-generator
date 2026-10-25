"""Covering letters: letterhead settings, validation, documents and submission packages.

No Streamlit code here so the logic can be tested and reused directly.
"""

from __future__ import annotations

import io
import re
import zipfile
from dataclasses import dataclass, field
from datetime import date
from typing import Optional

from database.database import LetterFinalizedError, ReportRepository
from models.inspection import InspectionReport
from models.letter import STATUS_FINAL, CompanyProfile, CoveringLetter
from reports.letter_content import build_letter_content, outcome_words
from reports.letter_docx import generate_letter_docx
from reports.letter_pdf import generate_letter_pdf
from services.report_service import build_docx, build_pdf

COMPANY_KEY = "company_profile"
PDF_MIME = "application/pdf"
DOCX_MIME = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"


class LetterValidationError(Exception):
    def __init__(self, errors: list[str]):
        self.errors = errors
        super().__init__("; ".join(errors))


@dataclass
class GeneratedFile:
    filename: str
    data: bytes
    mime: str


@dataclass
class SubmissionPackage:
    letter_pdf: GeneratedFile
    letter_docx: GeneratedFile
    report_files: list[GeneratedFile] = field(default_factory=list)
    zip_file: Optional[GeneratedFile] = None
    letter_pages: int = 1
    report_pages: dict[str, int] = field(default_factory=dict)
    letter_number: str = ""

    @property
    def all_files(self) -> list[GeneratedFile]:
        return [self.letter_pdf, self.letter_docx, *self.report_files]


# --------------------------------------------------------------------------
# Letterhead
# --------------------------------------------------------------------------

def load_company(repo: ReportRepository) -> CompanyProfile:
    stored = repo.get_setting(COMPANY_KEY)
    return CompanyProfile.from_dict(stored) if stored is not None else CompanyProfile()


def save_company(repo: ReportRepository, profile: CompanyProfile) -> None:
    if not profile.name.strip():
        raise ValueError("Company name cannot be empty.")
    repo.set_setting(COMPANY_KEY, profile.to_dict())


# --------------------------------------------------------------------------
# Validation
# --------------------------------------------------------------------------

def find_reports(repo: ReportRepository, numbers: list[str],
                 extra: Optional[dict[str, InspectionReport]] = None) -> tuple[list[InspectionReport], list[str]]:
    """Enclosed reports in letter order; ``extra`` (e.g. the current form) takes precedence."""
    extra = extra or {}
    found, missing = [], []
    for number in numbers:
        report = extra.get(number) or repo.get_report(number)
        if report is None:
            missing.append(number)
        else:
            found.append(report)
    return found, missing


def validate_letter(letter: CoveringLetter, reports: list[InspectionReport],
                    missing: tuple[str, ...] | list[str] = ()) -> tuple[list[str], list[str]]:
    """(errors, warnings). Errors block document generation."""
    errors, warnings = [], []
    if not letter.letter_number.strip():
        errors.append("Letter Number / Reference Number is required.")
    try:
        date.fromisoformat(letter.letter_date)
    except (TypeError, ValueError):
        errors.append("Letter Date is required.")
    if not letter.recipient_organization.strip():
        errors.append("Recipient organization is required.")
    if not letter.report_numbers:
        errors.append("Attach at least one inspection report.")
    if missing:
        errors.append("Inspection report(s) not found in history: " + ", ".join(missing)
                      + ". Generate the report first.")
    if len(set(letter.report_numbers)) != len(letter.report_numbers):
        errors.append("The same report is attached more than once.")
    if letter.sample_count is not None and letter.sample_count < 1:
        errors.append("Number of samples must be at least 1.")
    numbers_in_reports = {r.info.report_number for r in reports}
    if reports and set(letter.report_numbers) - numbers_in_reports - set(missing):
        errors.append("Enclosure list does not match the attached reports.")

    if letter.letter_number.strip() and letter.letter_number.strip() in numbers_in_reports:
        warnings.append("The letter number is the same as an inspection report number; "
                        "they are normally different references.")
    if not (letter.indenter.strip() or letter.forward_to.strip()):
        warnings.append("No indenter or forwarding authority entered (and none in the reports): "
                        "the onward-transmission sentence will be omitted.")
    if not letter.project_name.strip():
        warnings.append("No project name: the subject line will not name a project.")
    words = outcome_words(letter.body_override)
    if words:
        warnings.append("The edited wording mentions results (" + ", ".join(words) + "). The "
                        "covering letter should not state outcomes; results are in the reports.")
    return errors, warnings


# --------------------------------------------------------------------------
# Documents
# --------------------------------------------------------------------------

def _safe(text: str) -> str:
    return re.sub(r"[^A-Za-z0-9._-]+", "_", text.strip()) or "letter"


def build_letter_documents(letter: CoveringLetter, reports: list[InspectionReport],
                           company: CompanyProfile) -> tuple[GeneratedFile, GeneratedFile, int]:
    content = build_letter_content(letter, reports, company)
    pdf = generate_letter_pdf(content)
    base = f"Covering_Letter_{_safe(letter.letter_number)}"
    return (
        GeneratedFile(f"{base}.pdf", pdf.data, PDF_MIME),
        GeneratedFile(f"{base}.docx", generate_letter_docx(content), DOCX_MIME),
        pdf.page_count,
    )


def build_package(letter: CoveringLetter, reports: list[InspectionReport],
                  company: CompanyProfile) -> SubmissionPackage:
    """Letter PDF/DOCX + every enclosed report as PDF/DOCX + a ZIP of all files."""
    letter_pdf, letter_docx, letter_pages = build_letter_documents(letter, reports, company)
    package = SubmissionPackage(letter_pdf, letter_docx, letter_pages=letter_pages,
                                letter_number=letter.letter_number.strip())
    for report in reports:
        pdf = build_pdf(report)
        docx = build_docx(report)
        package.report_files += [GeneratedFile(pdf.filename, pdf.data, pdf.mime),
                                 GeneratedFile(docx.filename, docx.data, docx.mime)]
        package.report_pages[report.info.report_number] = pdf.page_count or 0

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for f in package.all_files:
            zf.writestr(f.filename, f.data)
    package.zip_file = GeneratedFile(f"Submission_{_safe(letter.letter_number)}.zip",
                                     buf.getvalue(), "application/zip")
    return package


def finalize_submission(repo: ReportRepository, letter: CoveringLetter,
                        reports: list[InspectionReport], company: CompanyProfile) -> SubmissionPackage:
    """Build the complete package and record the letter as FINAL with snapshots.

    Refuses (LetterFinalizedError) if a letter with this number is already final.
    """
    errors, _ = validate_letter(letter, reports)
    if errors:
        raise LetterValidationError(errors)
    if repo.letter_status(letter.letter_number) == STATUS_FINAL:
        raise LetterFinalizedError(
            f"Letter {letter.letter_number.strip()} has already been finalized and cannot be "
            "overwritten. Use a new letter number (e.g. a revision) for changes."
        )
    package = build_package(letter, reports, company)
    repo.save_letter(letter, final=True, reports=reports, company=company)
    return package


def revision_number(letter_number: str, repo: ReportRepository) -> str:
    """Next unused revision reference, e.g. 'AH/2026/014' -> 'AH/2026/014-R1'."""
    base = re.sub(r"-R\d+$", "", letter_number.strip())
    k = 1
    while repo.letter_status(f"{base}-R{k}") is not None:
        k += 1
    return f"{base}-R{k}"
