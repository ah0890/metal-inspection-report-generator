"""Covering letter and company letterhead models.

Empty strings / ``None`` mean "not provided". The letter text omits anything
that is not provided; nothing is invented.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field, fields
from typing import Optional

DEFAULT_COMPANY_NAME = "AH Precision Inspection & Testing Services"
DEFAULT_TAGLINE = "Precision • Integrity • Quality"

STATUS_DRAFT = "DRAFT"
STATUS_FINAL = "FINAL"


def _from_dict(cls, data: Optional[dict]):
    data = data or {}
    names = {f.name for f in fields(cls)}
    return cls(**{k: v for k, v in data.items() if k in names})


@dataclass
class CompanyProfile:
    """Letterhead details. Only the name and tagline have initial values."""

    name: str = DEFAULT_COMPANY_NAME
    tagline: str = DEFAULT_TAGLINE
    address: str = ""
    telephone: str = ""
    email: str = ""
    website: str = ""
    logo_base64: str = ""  # PNG/JPEG image, base64-encoded
    logo_mime: str = ""
    signatory_name: str = ""  # General Manager's name, if provided
    signatory_designation: str = "General Manager"

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Optional[dict]) -> "CompanyProfile":
        return _from_dict(cls, data)

    @property
    def contact_line(self) -> str:
        parts = [self.telephone and f"Tel: {self.telephone}", self.email and f"Email: {self.email}",
                 self.website]
        return "  |  ".join(p for p in parts if p)


@dataclass
class CoveringLetter:
    # Letter information
    letter_number: str = ""
    letter_date: str = ""  # ISO YYYY-MM-DD
    recipient_organization: str = ""
    recipient_department: str = ""
    recipient_name: str = ""  # name and/or designation
    recipient_address: str = ""
    # Project and submission information
    project_name: str = ""
    project_reference: str = ""
    indenter: str = ""  # indenter / requesting organization
    submission_reference: str = ""
    receipt_date: str = ""  # free text, e.g. "2026-10-20"
    testing_date: str = ""  # free text: a date or a date range
    sample_count: Optional[int] = None
    material_description: str = ""
    sample_ids: str = ""
    additional_references: str = ""
    # Forwarding information
    signatory_name: str = ""
    signatory_designation: str = ""
    forward_to: str = ""
    # Enclosed inspection reports (report numbers, in enclosure order)
    report_numbers: list[str] = field(default_factory=list)
    # Optional reviewed wording. Empty -> standard deterministic wording.
    body_override: str = ""

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Optional[dict]) -> "CoveringLetter":
        return _from_dict(cls, data)
