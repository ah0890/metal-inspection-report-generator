"""SQLite report history.

Stores searchable metadata plus the full report data (JSON) so a report can be
reopened and regenerated. The Anthropic API key is never part of the report
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
"""

LIST_COLUMNS = (
    "id", "report_number", "report_date", "customer", "material", "grade",
    "heat_batch", "inspector", "overall_result", "is_sample", "updated_at",
)


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

    def delete(self, report_id: int) -> None:
        with self._connect() as conn:
            conn.execute("DELETE FROM reports WHERE id = ?", (report_id,))
