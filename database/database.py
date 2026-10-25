"""SQLite report history.

Stores searchable metadata plus the full report data (JSON) so a report can be
reopened and regenerated, covering letters (finalized letters keep snapshots
of their enclosed reports and are never overwritten), and a small key/value
``settings`` table that holds the saved report defaults and letterhead. The Anthropic API key is never part of the report
data and is never written here.
"""

from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Iterator, Optional

from config import settings
from models.inspection import InspectionReport
from models.letter import STATUS_DRAFT, STATUS_FINAL, CompanyProfile, CoveringLetter

_SCHEMA = """
CREATE TABLE IF NOT EXISTS reports (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    report_number   TEXT NOT NULL UNIQUE,
    report_date     TEXT,
    customer        TEXT,
    material        TEXT,
    grade           TEXT,
    heat_batch      TEXT,
    inspector       TEXT,
    overall_result  TEXT,
    is_sample       INTEGER NOT NULL DEFAULT 0,
    data_json       TEXT NOT NULL,
    created_at      TEXT NOT NULL,
    updated_at      TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_reports_material ON reports(material);
CREATE INDEX IF NOT EXISTS idx_reports_heat ON reports(heat_batch);
CREATE TABLE IF NOT EXISTS letters (
    id                      INTEGER PRIMARY KEY AUTOINCREMENT,
    letter_number           TEXT NOT NULL UNIQUE,
    letter_date             TEXT,
    recipient_organization  TEXT,
    indenter                TEXT,
    project_name            TEXT,
    report_numbers          TEXT NOT NULL,   -- JSON list, enclosure order
    status                  TEXT NOT NULL,   -- DRAFT | FINAL
    data_json               TEXT NOT NULL,   -- the covering letter
    reports_json            TEXT,            -- FINAL: snapshot of the enclosed reports
    company_json            TEXT,            -- FINAL: snapshot of the letterhead
    created_at              TEXT NOT NULL,
    updated_at              TEXT NOT NULL,
    finalized_at            TEXT
);
CREATE TABLE IF NOT EXISTS settings (
    key         TEXT PRIMARY KEY,
    value_json  TEXT NOT NULL,
    updated_at  TEXT NOT NULL
);
"""

LETTER_LIST_COLUMNS = (
    "id", "letter_number", "letter_date", "recipient_organization", "indenter",
    "project_name", "report_numbers", "status", "updated_at", "finalized_at",
)

LIST_COLUMNS = (
    "id", "report_number", "report_date", "customer", "material", "grade",
    "heat_batch", "inspector", "overall_result", "is_sample", "updated_at",
)


class LetterFinalizedError(Exception):
    """Raised instead of silently overwriting a finalized covering letter."""


class ReportRepository:
    def __init__(self, db_path: Optional[Path] = None):
        self.db_path = Path(db_path or settings.DATABASE_PATH)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as conn:
            conn.executescript(_SCHEMA)

    @contextmanager
    def _connect(self) -> Iterator[sqlite3.Connection]:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()

    def save(self, report: InspectionReport, overall_result: str) -> None:
        """Insert or update (by report number) a report in the history."""
        info = report.info
        now = datetime.now().isoformat(timespec="seconds")
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO reports (report_number, report_date, customer, material, grade,
                    heat_batch, inspector, overall_result, is_sample, data_json,
                    created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(report_number) DO UPDATE SET
                    report_date = excluded.report_date,
                    customer = excluded.customer,
                    material = excluded.material,
                    grade = excluded.grade,
                    heat_batch = excluded.heat_batch,
                    inspector = excluded.inspector,
                    overall_result = excluded.overall_result,
                    is_sample = excluded.is_sample,
                    data_json = excluded.data_json,
                    updated_at = excluded.updated_at
                """,
                (
                    info.report_number.strip(), info.report_date, info.customer,
                    info.material, info.grade, info.heat_batch, info.inspector,
                    overall_result, int(info.is_sample), json.dumps(report.to_dict()),
                    now, now,
                ),
            )

    def search(
        self, report_number: str = "", material: str = "", heat_batch: str = "", limit: int = 200
    ) -> list[dict]:
        """Case-insensitive partial-match search; empty filters match everything."""
        clauses, params = [], []
        for column, value in (
            ("report_number", report_number),
            ("material", material),
            ("heat_batch", heat_batch),
        ):
            if value.strip():
                clauses.append(f"{column} LIKE ?")
                params.append(f"%{value.strip()}%")
        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        with self._connect() as conn:
            rows = conn.execute(
                f"SELECT {', '.join(LIST_COLUMNS)} FROM reports {where} "
                "ORDER BY updated_at DESC LIMIT ?",
                (*params, limit),
            ).fetchall()
        return [dict(r) for r in rows]

    def load(self, report_id: int) -> Optional[InspectionReport]:
        with self._connect() as conn:
            row = conn.execute("SELECT data_json FROM reports WHERE id = ?", (report_id,)).fetchone()
        return InspectionReport.from_dict(json.loads(row["data_json"])) if row else None

    def latest(self, include_samples: bool = False) -> Optional[InspectionReport]:
        """Most recently saved report (sample reports excluded by default)."""
        where = "" if include_samples else "WHERE is_sample = 0"
        with self._connect() as conn:
            row = conn.execute(
                f"SELECT data_json FROM reports {where} ORDER BY updated_at DESC, id DESC LIMIT 1"
            ).fetchone()
        return InspectionReport.from_dict(json.loads(row["data_json"])) if row else None

    # --- Settings (key/value JSON) ---------------------------------------

    def get_setting(self, key: str) -> Optional[dict]:
        with self._connect() as conn:
            row = conn.execute("SELECT value_json FROM settings WHERE key = ?", (key,)).fetchone()
        return json.loads(row["value_json"]) if row else None

    def set_setting(self, key: str, value: dict) -> None:
        now = datetime.now().isoformat(timespec="seconds")
        with self._connect() as conn:
            conn.execute(
                "INSERT INTO settings (key, value_json, updated_at) VALUES (?, ?, ?) "
                "ON CONFLICT(key) DO UPDATE SET value_json = excluded.value_json, "
                "updated_at = excluded.updated_at",
                (key, json.dumps(value, ensure_ascii=False), now),
            )

    def get_report(self, report_number: str) -> Optional[InspectionReport]:
        with self._connect() as conn:
            row = conn.execute("SELECT data_json FROM reports WHERE report_number = ?",
                               (report_number.strip(),)).fetchone()
        return InspectionReport.from_dict(json.loads(row["data_json"])) if row else None

    def report_field_values(self, column: str, limit: int = 50) -> list[str]:
        """Previously used customer / inspector values, most recent first (suggestions)."""
        if column not in ("customer", "inspector"):
            raise ValueError(f"Unsupported column: {column}")
        with self._connect() as conn:
            rows = conn.execute(
                f"SELECT {column} AS v, MAX(updated_at) AS t FROM reports "
                f"WHERE is_sample = 0 AND TRIM(COALESCE({column}, '')) <> '' "
                f"GROUP BY {column} ORDER BY t DESC LIMIT ?",
                (limit,),
            ).fetchall()
        return [r["v"] for r in rows]

    # --- Covering letters ------------------------------------------------

    def letter_numbers(self) -> list[tuple[str, str]]:
        """(letter number, letter date) for every saved letter."""
        with self._connect() as conn:
            return [(r["letter_number"], r["letter_date"] or "")
                    for r in conn.execute("SELECT letter_number, letter_date FROM letters")]

    def letter_id(self, letter_number: str) -> Optional[int]:
        with self._connect() as conn:
            row = conn.execute("SELECT id FROM letters WHERE letter_number = ?",
                               (letter_number.strip(),)).fetchone()
        return row["id"] if row else None

    def letter_status(self, letter_number: str) -> Optional[str]:
        with self._connect() as conn:
            row = conn.execute("SELECT status FROM letters WHERE letter_number = ?",
                               (letter_number.strip(),)).fetchone()
        return row["status"] if row else None

    def save_letter(self, letter: CoveringLetter, *, final: bool = False,
                    reports: Optional[list[InspectionReport]] = None,
                    company: Optional[CompanyProfile] = None) -> None:
        """Save a draft, or finalize with snapshots of the enclosed reports and letterhead.

        A FINAL letter is never overwritten: saving under its number raises
        LetterFinalizedError, so a revision must use a new letter number.
        """
        number = letter.letter_number.strip()
        if self.letter_status(number) == STATUS_FINAL:
            raise LetterFinalizedError(
                f"Letter {number} has already been finalized and cannot be overwritten. "
                "Use a new letter number (e.g. a revision) for changes."
            )
        now = datetime.now().isoformat(timespec="seconds")
        reports_json = json.dumps([r.to_dict() for r in reports]) if final and reports else None
        company_json = json.dumps(company.to_dict()) if final and company else None
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO letters (letter_number, letter_date, recipient_organization, indenter,
                    project_name, report_numbers, status, data_json, reports_json, company_json,
                    created_at, updated_at, finalized_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(letter_number) DO UPDATE SET
                    letter_date = excluded.letter_date,
                    recipient_organization = excluded.recipient_organization,
                    indenter = excluded.indenter,
                    project_name = excluded.project_name,
                    report_numbers = excluded.report_numbers,
                    status = excluded.status,
                    data_json = excluded.data_json,
                    reports_json = excluded.reports_json,
                    company_json = excluded.company_json,
                    updated_at = excluded.updated_at,
                    finalized_at = excluded.finalized_at
                """,
                (
                    number, letter.letter_date, letter.recipient_organization, letter.indenter,
                    letter.project_name, json.dumps(letter.report_numbers),
                    STATUS_FINAL if final else STATUS_DRAFT, json.dumps(letter.to_dict()),
                    reports_json, company_json, now, now, now if final else None,
                ),
            )

    def search_letters(self, text: str = "", limit: int = 200) -> list[dict]:
        """Partial match on letter number, recipient, indenter, project or report numbers."""
        where, params = "", []
        if text.strip():
            cols = ("letter_number", "recipient_organization", "indenter", "project_name",
                    "report_numbers")
            where = "WHERE " + " OR ".join(f"{c} LIKE ?" for c in cols)
            params = [f"%{text.strip()}%"] * len(cols)
        with self._connect() as conn:
            rows = conn.execute(
                f"SELECT {', '.join(LETTER_LIST_COLUMNS)} FROM letters {where} "
                "ORDER BY updated_at DESC LIMIT ?",
                (*params, limit),
            ).fetchall()
        out = []
        for r in rows:
            d = dict(r)
            d["report_numbers"] = json.loads(d["report_numbers"])
            out.append(d)
        return out

    def load_letter(self, letter_id: int) -> Optional[dict]:
        """Letter plus, for FINAL letters, the report and letterhead snapshots."""
        with self._connect() as conn:
            row = conn.execute("SELECT * FROM letters WHERE id = ?", (letter_id,)).fetchone()
        if not row:
            return None
        return {
            "letter": CoveringLetter.from_dict(json.loads(row["data_json"])),
            "status": row["status"],
            "finalized_at": row["finalized_at"],
            "reports": ([InspectionReport.from_dict(d) for d in json.loads(row["reports_json"])]
                        if row["reports_json"] else None),
            "company": (CompanyProfile.from_dict(json.loads(row["company_json"]))
                        if row["company_json"] else None),
        }

    def letter_field_values(self, field_name: str) -> list[str]:
        """Previously used values of a letter field, most recent first."""
        with self._connect() as conn:
            rows = conn.execute("SELECT data_json FROM letters ORDER BY updated_at DESC").fetchall()
        seen, values = set(), []
        for r in rows:
            value = str(json.loads(r["data_json"]).get(field_name) or "").strip()
            if value and value.lower() not in seen:
                seen.add(value.lower())
                values.append(value)
        return values

    def delete(self, report_id: int) -> None:
        with self._connect() as conn:
            conn.execute("DELETE FROM reports WHERE id = ?", (report_id,))
