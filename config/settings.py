"""Application settings.

All configurable values live here so the report layout, unit lists and
AI behaviour can be changed without touching business logic.
Secrets (the Anthropic API key) are read from the environment / .env only.
"""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent

# Load variables from a local .env file if present (never committed).
load_dotenv(BASE_DIR / ".env")

# --------------------------------------------------------------------------
# Storage
# --------------------------------------------------------------------------
DATA_DIR = Path(os.getenv("MIRG_DATA_DIR", BASE_DIR / "data"))
DATABASE_PATH = Path(os.getenv("MIRG_DATABASE_PATH", DATA_DIR / "reports.db"))

# --------------------------------------------------------------------------
# Report branding / document control (shown on the PDF and DOCX)
# --------------------------------------------------------------------------
LAB_NAME = os.getenv("MIRG_LAB_NAME", "Quality Control Laboratory")
LAB_SUBTITLE = os.getenv("MIRG_LAB_SUBTITLE", "Mechanical Testing & Metallography")
FORM_NUMBER = os.getenv("MIRG_FORM_NUMBER", "QC-MIR-01 Rev. 0")

# --------------------------------------------------------------------------
# Anthropic / Claude
# --------------------------------------------------------------------------
ANTHROPIC_API_KEY_ENV = "ANTHROPIC_API_KEY"
CLAUDE_MODEL = os.getenv("MIRG_CLAUDE_MODEL", "claude-opus-5-5")
# Wording a few short paragraphs is a simple task; low effort keeps it fast.
CLAUDE_EFFORT = os.getenv("MIRG_CLAUDE_EFFORT", "low")
CLAUDE_MAX_TOKENS = 16000
CLAUDE_TIMEOUT_SECONDS = 120.0

# --------------------------------------------------------------------------
# Units and scales offered in the UI. No unit is pre-selected: the inspector
# must choose one explicitly.
# --------------------------------------------------------------------------
STRENGTH_UNITS = ["MPa", "N/mm²", "ksi", "psi"]
LENGTH_UNITS = ["mm", "in"]
TEMPERATURE_UNITS = ["°C", "°F"]
HARDNESS_SCALES = ["HB", "HBW", "HRA", "HRB", "HRC", "HV", "HK"]
MAX_HARDNESS_READINGS = 10

# --------------------------------------------------------------------------
# Free-text limits. They keep the generated report on a single A4 page.
# --------------------------------------------------------------------------
MAX_CHARS_SHORT = 80
MAX_CHARS_OBSERVATION = 500
MAX_CHARS_REMARKS = 400
MAX_CHARS_SUMMARY = 600
