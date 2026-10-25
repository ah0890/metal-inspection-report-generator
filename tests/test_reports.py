"""Report generation, one-page guarantee, history and the no-API-key path."""

import io

import pytest
from pypdf import PdfReader

from database.database import ReportRepository
from models.sample_data import sample_report
from services import claude_service
from services.calculation_service import evaluate_report
from services.report_service import build_docx, build_pdf


def _pdf_text(data: bytes) -> tuple[int, str]:
    reader = PdfReader(io.BytesIO(data))
    return len(reader.pages), "\n".join(p.extract_text() for p in reader.pages)


def test_sample_pdf_is_one_page_and_passes():
    generated = build_pdf(sample_report())
    pages, text = _pdf_text(generated.data)
    assert pages == 1 == generated.page_count
    assert "METAL INSPECTION REPORT" in text
    assert "SAMPLE-MIR-0001" in text
    assert "PASS" in text
    assert "SAMPLE DATA" in text


def test_pdf_with_maximum_length_text_stays_on_one_page():
    report = sample_report()
    long = "Observation text with plenty of detail to fill the available space. " * 20
    report.metallography.microstructure = long[:500]
    report.metallography.preparation_remarks = long[:400]
    report.info.remarks = long[:400]
    report.ai.summary = long[:600]
    report.criteria.source = "X" * 80
    generated = build_pdf(report)
    pages, _ = _pdf_text(generated.data)
    assert pages == 1


def test_unspecified_criterion_is_stated_on_report():
    report = sample_report()
    report.criteria.grain_size.minimum = None
    report.criteria.grain_size.mandatory = False
    _, text = _pdf_text(build_pdf(report).data)
    assert "Acceptance criterion not specified" in text


def test_failed_report_shows_fail():
    report = sample_report()
    report.tensile.uts = 280
    generated = build_pdf(report)
    assert generated.evaluation.overall.value == "FAIL"
    assert "FAIL" in _pdf_text(generated.data)[1]


def test_docx_generation():
    generated = build_docx(sample_report())
    assert generated.data[:2] == b"PK"  # DOCX is a zip container
    assert generated.filename.endswith(".docx")


def test_history_save_search_reopen(tmp_path):
    repo = ReportRepository(tmp_path / "history.db")
    report = sample_report()
    build_pdf(report, repo)
    build_pdf(report, repo)  # saving again updates, does not duplicate
    assert len(repo.search()) == 1
    assert repo.search(report_number="mir-0001")
    assert repo.search(material="aluminium")
    assert repo.search(heat_batch="HT-2026")
    assert not repo.search(material="steel")
    row = repo.search()[0]
    assert row["overall_result"] == "PASS"
    reopened = repo.load(row["id"])
    assert reopened == report


def test_api_key_is_never_stored(tmp_path, monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-secret-test-value")
    repo = ReportRepository(tmp_path / "history.db")
    build_pdf(sample_report(), repo)
    assert b"sk-ant-secret-test-value" not in (tmp_path / "history.db").read_bytes()


def test_ai_without_api_key_gives_clear_error(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    report = sample_report()
    with pytest.raises(claude_service.ClaudeServiceError, match="ANTHROPIC_API_KEY is not set"):
        claude_service.generate_wording(report, evaluate_report(report))


def test_ai_prompt_contains_python_statuses_not_raw_limits_to_judge():
    report = sample_report()
    payload = claude_service.build_prompt_payload(report, evaluate_report(report))
    assert payload["overall_result"] == "PASS"
    assert all(r["status"] for r in payload["test_results"])
