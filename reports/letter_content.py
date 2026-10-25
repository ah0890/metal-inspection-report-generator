"""Covering-letter content (WHAT the letter says), shared by the PDF and DOCX generators.

Everything is deterministic. Each sentence fragment is included only when its
data is available, so the letter never states a date, reference or activity
that was not entered or present in the enclosed reports. The letter never
states test outcomes (pass/fail).
"""

from __future__ import annotations

import copy
import re
from dataclasses import dataclass
from datetime import date
from typing import Iterable

from models.inspection import InspectionReport
from models.letter import CompanyProfile, CoveringLetter

DEFAULT_DESIGNATION = "General Manager"
_NUMBER_WORDS = {2: "two", 3: "three", 4: "four", 5: "five", 6: "six", 7: "seven", 8: "eight",
                 9: "nine", 10: "ten"}


# --------------------------------------------------------------------------
# Helpers
# --------------------------------------------------------------------------

def format_date(value: str) -> str:
    """'2026-10-25' -> '25 October 2026'. Free text is returned unchanged."""
    try:
        d = date.fromisoformat(value.strip())
    except (ValueError, AttributeError):
        return (value or "").strip()
    return f"{d.day} {d:%B %Y}"


def join_list(items: list[str]) -> str:
    items = [i for i in items if i]
    if len(items) <= 1:
        return "".join(items)
    return ", ".join(items[:-1]) + " and " + items[-1]


def _unique(values: Iterable[str]) -> list[str]:
    seen, out = set(), []
    for v in values:
        v = (v or "").strip()
        if v and v.lower() not in seen:
            seen.add(v.lower())
            out.append(v)
    return out


def report_activities(report: InspectionReport) -> list[str]:
    """Tests actually present in a report (by its entered data)."""
    t, h, m = report.tensile, report.hardness, report.metallography
    acts = []
    if any(v is not None for v in (t.yield_strength, t.uts, t.elongation)):
        acts.append("tensile testing")
    if h.readings:
        acts.append("hardness testing")
    if m.grain_size is not None or m.microstructure.strip():
        acts.append("metallographic examination")
    return acts


def report_title(report: InspectionReport) -> str:
    acts = report_activities(report)
    mech = "tensile testing" in acts or "hardness testing" in acts
    metal = "metallographic examination" in acts
    if mech and metal:
        return "Mechanical Testing and Metallography Inspection Report"
    if mech:
        return "Mechanical Testing Inspection Report"
    if metal:
        return "Metallography Inspection Report"
    return "Inspection Report"


# --------------------------------------------------------------------------
# Values derived from the enclosed reports (used when a field is left blank)
# --------------------------------------------------------------------------

def derived_values(reports: list[InspectionReport]) -> dict[str, str]:
    """Letter fields that can be filled from the enclosed inspection reports."""
    materials = _unique(
        " ".join(p for p in (r.info.material, r.info.grade) if p.strip()) for r in reports
    )
    ids = _unique(r.info.sample_number for r in reports)
    batches = _unique(r.info.heat_batch for r in reports)
    sample_ids = "; ".join(p for p in (
        ", ".join(ids) and f"Sample No. {', '.join(ids)}",
        ", ".join(batches) and f"Heat/Batch {', '.join(batches)}",
    ) if p)

    dates = sorted(d for d in (r.info.report_date for r in reports) if d)
    testing = ""
    if dates:
        first, last = format_date(dates[0]), format_date(dates[-1])
        testing = first if first == last else f"{first} to {last}"

    return {
        "material_description": ", ".join(materials),
        "sample_ids": sample_ids,
        "testing_date": testing,
        "indenter": join_list(_unique(r.info.customer for r in reports)),
    }


def resolve_letter(letter: CoveringLetter, reports: list[InspectionReport]) -> CoveringLetter:
    """Copy of the letter with blank fields filled from the enclosed reports."""
    resolved = copy.deepcopy(letter)
    for key, value in derived_values(reports).items():
        if not getattr(resolved, key).strip():
            setattr(resolved, key, value)
    return resolved


# --------------------------------------------------------------------------
# Letter content
# --------------------------------------------------------------------------

@dataclass
class LetterContent:
    company: CompanyProfile
    letter_number: str
    date_text: str
    recipient_lines: list[str]
    subject: str
    reference_lines: list[str]
    salutation: str
    paragraphs: list[str]
    closing: str
    for_company: str
    signatory_name: str
    signatory_designation: str
    enclosures: list[str]


def _report_phrase(numbers: list[str]) -> str:
    if len(numbers) == 1:
        return f"Inspection Report No. {numbers[0]}"
    return f"Inspection Reports Nos. {join_list(numbers)}"


def standard_paragraphs(letter: CoveringLetter, reports: list[InspectionReport]) -> list[str]:
    """Standard wording built only from the provided data. ``letter`` must be resolved."""
    n = letter.sample_count
    count = _NUMBER_WORDS.get(n, str(n))
    samples = "the samples" if not n else ("the sample" if n == 1 else f"the {count} samples")
    if letter.material_description:
        samples += f" of {letter.material_description}"
    if letter.sample_ids:
        samples += f" ({letter.sample_ids})"
    received = " received"
    if letter.indenter:
        received += f" from {letter.indenter}"
    if letter.submission_reference:
        received += f" vide reference {letter.submission_reference}"
    if letter.receipt_date:
        received += f" on {format_date(letter.receipt_date)}"

    activities = join_list(_unique(a for r in reports for a in report_activities(r)))
    work = activities or "the requested inspection and testing"
    subject_noun = "sample has" if n == 1 else "samples have"
    p1 = (f"With reference to {samples}{received}, the submitted {subject_noun} been subjected "
          f"to {work} as requested.")
    if letter.testing_date:
        p1 += f" The inspection and testing were carried out on {letter.testing_date}."

    numbers = letter.report_numbers
    p2 = (f"The inspection and testing results are compiled in the enclosed {_report_phrase(numbers)} "
          "for your review and record.")

    paragraphs = [p1, p2]
    project = letter.project_name
    if letter.project_reference:
        project = f"{project} ({letter.project_reference})" if project else letter.project_reference
    target = letter.forward_to or letter.indenter
    it = "report is" if len(numbers) == 1 else "reports are"
    if target:
        p3 = f"The {it} hereby submitted for onward transmission to {target}"
        paragraphs.append(p3 + (f" in connection with {project}." if project else "."))
    elif project:
        paragraphs.append(f"The {it} submitted in connection with {project}.")

    paragraphs.append("Should you require any further information or clarification, please "
                      "contact the undersigned.")
    return paragraphs


def build_letter_content(letter: CoveringLetter, reports: list[InspectionReport],
                         company: CompanyProfile) -> LetterContent:
    letter = resolve_letter(letter, reports)
    by_number = {r.info.report_number: r for r in reports}
    numbers = letter.report_numbers

    recipient = [letter.recipient_name, letter.recipient_department, letter.recipient_organization]
    recipient_lines = [line.strip() for line in recipient if line.strip()]
    recipient_lines += [line.strip() for line in letter.recipient_address.splitlines() if line.strip()]

    noun = "Report" if len(numbers) == 1 else "Reports"
    subject = f"Submission of Inspection and Testing {noun}"
    if letter.project_name:
        subject += f" for {letter.project_name}"
    elif letter.material_description:
        subject += f" – {letter.material_description}"

    refs = []
    if letter.project_reference:
        refs.append(f"Project Ref.: {letter.project_reference}")
    if letter.submission_reference:
        refs.append(f"Sample Submission Ref.: {letter.submission_reference}")
    refs += [line.strip() for line in letter.additional_references.splitlines() if line.strip()]

    if letter.body_override.strip():
        paragraphs = [p.strip() for p in letter.body_override.split("\n\n") if p.strip()]
    else:
        paragraphs = standard_paragraphs(letter, reports)

    enclosures = []
    for number in numbers:
        r = by_number.get(number)
        if r is None:
            enclosures.append(f"Inspection Report No. {number}")
            continue
        details = [" ".join(p for p in (r.info.material, r.info.grade) if p.strip())]
        if r.info.heat_batch.strip():
            details.append(f"Heat/Batch {r.info.heat_batch.strip()}")
        detail = ", ".join(d for d in details if d)
        enclosures.append(f"{report_title(r)} No. {number}" + (f" ({detail})" if detail else ""))

    return LetterContent(
        company=company,
        letter_number=letter.letter_number.strip(),
        date_text=format_date(letter.letter_date),
        recipient_lines=recipient_lines,
        subject=subject,
        reference_lines=refs,
        salutation="Dear Sir/Madam,",
        paragraphs=paragraphs,
        closing="Yours faithfully,",
        for_company=f"For {company.name}" if company.name.strip() else "",
        signatory_name=(letter.signatory_name or company.signatory_name).strip(),
        signatory_designation=(letter.signatory_designation or company.signatory_designation
                               or DEFAULT_DESIGNATION).strip(),
        enclosures=enclosures,
    )


def letter_plain_text(c: LetterContent) -> str:
    """Plain-text rendering, used for the on-screen review."""
    lines = [f"Ref. No.: {c.letter_number}", f"Date: {c.date_text}", ""]
    lines += c.recipient_lines + ["", f"Subject: {c.subject}"]
    lines += c.reference_lines
    lines += ["", c.salutation, ""]
    for p in c.paragraphs:
        lines += [p, ""]
    lines += [c.closing, c.for_company, "", "", c.signatory_name, c.signatory_designation, "",
              "Enclosures:"]
    lines += [f"{i}. {e}" for i, e in enumerate(c.enclosures, start=1)]
    return "\n".join(line for line in lines if line is not None)


_OUTCOME_RE = re.compile(
    r"\b(pass(?:ed|es)?|fail(?:ed|s|ure)?|accepted|rejected|conform\w*|non-conform\w*|"
    r"satisfactory|unsatisfactory|compliant|non-compliant)\b",
    re.IGNORECASE,
)


def outcome_words(text: str) -> list[str]:
    """Result words found in edited wording; the letter should not state outcomes."""
    return sorted({m.lower() for m in _OUTCOME_RE.findall(text or "")})
