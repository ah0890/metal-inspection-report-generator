"""Covering Letter tab: details, live review, documents, submission package, letter history."""

from __future__ import annotations

from dataclasses import fields
from datetime import date

import pandas as pd
import streamlit as st

from database.database import LetterFinalizedError
from models.letter import CURRENT_TEMPLATE_VERSION, STATUS_FINAL, CoveringLetter
from reports.letter_content import (
    build_letter_content,
    derived_sample_count,
    derived_values,
    letter_plain_text,
    resolve_letter,
    standard_paragraphs,
)
from services import claude_service
from services.letter_service import (
    LetterValidationError,
    build_letter_documents,
    build_package,
    finalize_submission,
    find_reports,
    LETTER_PREFIX,
    format_letter_number,
    load_company,
    next_letter_number,
    normalize_letter_number,
    parse_letter_number,
    validate_letter,
)
from services.report_service import ReportValidationError, build_pdf
from ui.state import get_repository, report_from_state, validate_form

P = "letter."
_TRANSIENT = ("letter_files", "letter_package", "letter_ai_error")


# --------------------------------------------------------------------------
# Session state <-> CoveringLetter
# --------------------------------------------------------------------------

def _set_number_parts(number: str) -> None:
    """Split a letter number into the serial / year inputs, or the full-number field."""
    s = st.session_state
    parts = parse_letter_number(number)
    s[P + "custom_number"] = parts is None
    if parts:
        s[P + "serial"], s[P + "year"] = parts
    else:
        today = date.today()
        s[P + "serial"], s[P + "year"] = 1, today.year % 100
    s[P + "full_number"] = normalize_letter_number(number)


def load_letter_into_state(letter: CoveringLetter, status: str = "", letter_id=None) -> None:
    s = st.session_state
    for f in fields(CoveringLetter):
        s[P + f.name] = getattr(letter, f.name)
    try:
        s[P + "letter_date"] = date.fromisoformat(letter.letter_date)
    except ValueError:
        s[P + "letter_date"] = date.today()
    _set_number_parts(letter.letter_number)
    s["letter_status"] = status
    s["letter_id"] = letter_id
    for key in _TRANSIENT:
        s.pop(key, None)


def current_letter_number() -> str:
    s = st.session_state
    if s.get(P + "custom_number"):
        return normalize_letter_number(s.get(P + "full_number", ""))
    return format_letter_number(s.get(P + "serial") or 1, s.get(P + "year") or 0)


def letter_from_state() -> CoveringLetter:
    s = st.session_state
    letter = CoveringLetter(**{f.name: s[P + f.name] for f in fields(CoveringLetter) if P + f.name in s})
    d = s.get(P + "letter_date")
    letter.letter_date = d.isoformat() if isinstance(d, date) else ""
    for f in fields(CoveringLetter):
        value = getattr(letter, f.name)
        if isinstance(value, str):
            setattr(letter, f.name, value.strip())
    letter.report_numbers = list(s.get(P + "report_numbers") or [])
    letter.letter_number = current_letter_number()
    return letter


def _blank_letter() -> CoveringLetter:
    """New letter: next free number, today's date, nothing carried over."""
    return CoveringLetter(letter_number=next_letter_number(get_repository()),
                          letter_date=date.today().isoformat())


def init_letter_state() -> None:
    if P + "letter_number" not in st.session_state:
        load_letter_into_state(_blank_letter())


def _new_letter() -> None:
    load_letter_into_state(_blank_letter())


# --------------------------------------------------------------------------
# Callbacks
# --------------------------------------------------------------------------

def _pick(field: str) -> None:
    value = st.session_state.get(f"pick.{field}")
    if value:
        st.session_state[P + field] = value
    st.session_state[f"pick.{field}"] = None


def _add_report(number: str) -> None:
    current = list(st.session_state.get(P + "report_numbers") or [])
    if number and number not in current:
        st.session_state[P + "report_numbers"] = current + [number]


def _copy_standard_wording(text: str) -> None:
    st.session_state[P + "body_override"] = text


def _reset_wording() -> None:
    st.session_state[P + "body_override"] = ""


def _improve_with_claude(facts: dict, draft: list[str]) -> None:
    st.session_state.pop("letter_ai_error", None)
    try:
        paragraphs = claude_service.generate_letter_wording(facts, draft)
    except claude_service.ClaudeServiceError as e:
        st.session_state["letter_ai_error"] = str(e)
        return
    st.session_state[P + "body_override"] = "\n\n".join(paragraphs)


def _reopen_letter(letter_id: int) -> None:
    record = get_repository().load_letter(letter_id)
    if record:
        load_letter_into_state(record["letter"], record["status"], letter_id)


def _upper_full_number() -> None:
    st.session_state[P + "full_number"] = normalize_letter_number(
        st.session_state.get(P + "full_number", ""))


def _use_next_number() -> None:
    _set_number_parts(next_letter_number(get_repository()))


def _start_revision() -> None:
    """Changes to a finalized letter go out as a new letter with the next number."""
    s = st.session_state
    _set_number_parts(next_letter_number(get_repository()))
    s[P + "template_version"] = CURRENT_TEMPLATE_VERSION
    s[P + "letter_date"] = date.today()
    s["letter_status"] = ""
    s["letter_id"] = None
    for key in _TRANSIENT:
        s.pop(key, None)


# --------------------------------------------------------------------------
# Rendering helpers
# --------------------------------------------------------------------------

def _text(col, label: str, field: str, *, history: bool = False, area: bool = False,
          placeholder: str = "", help: str | None = None) -> None:
    """Text field with an optional 'previously used' picker below it."""
    widget = col.text_area if area else col.text_input
    kwargs = {"height": 68} if area else {}
    widget(label, key=P + field, placeholder=placeholder or None, help=help, **kwargs)
    if history:
        values = get_repository().letter_field_values(field)
        if values:
            col.selectbox(f"Previously used {label.lower()}", values, index=None, key=f"pick.{field}",
                          placeholder="↳ select previously used", on_change=_pick, args=(field,),
                          label_visibility="collapsed")


def _current_report():
    """Current form report if it is valid, else None."""
    report = report_from_state()
    return report if validate_form(report).is_valid else None


def _gather_reports(letter: CoveringLetter):
    repo = get_repository()
    current = _current_report()
    extra = {current.info.report_number: current} if current else {}
    reports, missing = find_reports(repo, letter.report_numbers, extra)
    return reports, missing, current


def _save_current_report_if_enclosed(letter: CoveringLetter, current) -> None:
    """The current form report must be in history before it is finalized with a letter."""
    if current is not None and current.info.report_number in letter.report_numbers:
        build_pdf(current, get_repository())


def _downloads(files, key_prefix: str) -> None:
    cols = st.columns(len(files))
    for col, f in zip(cols, files):
        col.download_button(f"⬇️ {f.filename}", data=f.data, file_name=f.filename, mime=f.mime,
                            key=f"{key_prefix}.{f.filename}", width="stretch")


# --------------------------------------------------------------------------
# Main tab
# --------------------------------------------------------------------------

def render_covering_letter() -> None:
    init_letter_state()
    repo = get_repository()
    company = load_company(repo)
    s = st.session_state

    st.subheader("Covering Letter Details")
    c1, c2 = st.columns([3, 1])
    c1.caption("The covering letter is a separate document from the inspection report. The "
               "material/product, sample IDs and enclosure list are taken automatically from the "
               "enclosed reports.")
    c2.button("New letter", icon="🆕", on_click=_new_letter, width="stretch")

    if s.get("letter_status") == STATUS_FINAL:
        st.info(f"Letter **{s.get(P + 'letter_number')}** is **FINALIZED** and preserved in history. "
                "Regenerate its documents from the Letter History below, or start a revision to "
                "make changes under a new letter number.")
        st.button("Start a revision (new letter number)", on_click=_start_revision)

    # --- Enclosed reports --------------------------------------------------
    st.markdown("#### Enclosed Inspection Reports")
    history_numbers = [r["report_number"] for r in repo.search()]
    current = _current_report()
    options = list(dict.fromkeys(history_numbers + list(s.get(P + "report_numbers") or [])))
    current_number = current.info.report_number if current else ""
    if current_number and current_number not in options:
        options.insert(0, current_number)
    c1, c2 = st.columns([3, 1])
    c1.multiselect(
        "Reports enclosed with this letter (in enclosure order)", options, key=P + "report_numbers",
        format_func=lambda n: f"{n} (current form – saved when the package is generated)"
        if n == current_number and n not in history_numbers else n,
        placeholder="Select one or more reports",
    )
    c2.button("Add current report", on_click=_add_report, args=(current_number,),
              disabled=not current_number, width="stretch",
              help="Adds the report currently in the Inspection tab.")

    letter = letter_from_state()
    reports, missing, current = _gather_reports(letter)
    auto = derived_values(reports)
    auto_count = derived_sample_count(reports)

    # --- Letter information ------------------------------------------------
    st.markdown("#### Letter Information")
    c1, c2, c3, c4 = st.columns([1.3, 1, 1, 1.6])
    if s.get(P + "custom_number"):
        c1.text_input("Letter Number *", key=P + "full_number", on_change=_upper_full_number,
                      help="Full letter number; letters are converted to uppercase.")
    else:
        c1.text_input("Letter Number prefix", value=LETTER_PREFIX, disabled=True)
        c2.number_input("Serial No. *", key=P + "serial", min_value=1, max_value=999, step=1)
        c3.number_input("Year (YY) *", key=P + "year", min_value=0, max_value=99, step=1,
                        format="%02d")
    c4.date_input("Letter Date *", key=P + "letter_date", format="YYYY-MM-DD",
                  help="Defaults to today's date.")
    c1, c2 = st.columns([3, 1])
    c1.caption(f"Letter number: **{current_letter_number()}** — separate from the inspection "
               "report number(s).")
    c2.checkbox("Edit complete number", key=P + "custom_number")
    existing_id = repo.letter_id(current_letter_number())
    number_taken = existing_id is not None and existing_id != s.get("letter_id")
    if number_taken:
        st.error(f"Letter number {current_letter_number()} has already been issued "
                 f"({repo.letter_status(current_letter_number())}). Use another number.")
        st.button(f"Use the next free number ({next_letter_number(repo)})", on_click=_use_next_number)

    st.markdown("#### Recipient")
    c1, c2 = st.columns(2)
    _text(c1, "Recipient organization *", "recipient_organization", history=True)
    _text(c2, "Recipient department / section", "recipient_department", history=True)
    c1, c2 = st.columns(2)
    _text(c1, "Recipient name / designation", "recipient_name", history=True)
    _text(c2, "Recipient address", "recipient_address", history=True, area=True)

    # --- Samples -------------------------------------------------------------
    st.markdown("#### Samples")
    if s.get(P + "template_version", CURRENT_TEMPLATE_VERSION) == 1:
        st.caption("This letter was created with the original letter template; its project and "
                   "submission details are kept as issued.")
    c1, c2 = st.columns([1, 3])
    c1.number_input("Number of Samples", key=P + "sample_count", value=None, min_value=1, step=1,
                    placeholder=f"Auto: {auto_count}" if auto_count else "Not stated",
                    help="Leave empty to use the number of sample numbers in the enclosed reports.")
    _text(c2, "Sample IDs / Batch Numbers", "sample_ids",
          placeholder=f"Auto: {auto['sample_ids']}" if auto["sample_ids"] else "")
    if auto["material_description"]:
        st.caption(f"Material / product (from the reports): **{auto['material_description']}**")
    elif reports:
        st.caption("No material/product is recorded in the enclosed reports; the letter will "
                   "refer to the material identified in the enclosed report(s).")

    # --- Signature and transmission ---------------------------------------------
    st.markdown("#### Signature")
    c1, c2, c3 = st.columns(3)
    _text(c1, "General Manager's name", "signatory_name",
          placeholder=company.signatory_name or "Set a default in Settings")
    _text(c2, "Designation", "signatory_designation",
          placeholder=company.signatory_designation or "General Manager")
    _text(c3, "Concerned authority (optional)", "forward_to", history=True,
          help="Named in the transmission sentence. If empty, the letter says "
               "'the concerned authority'.")

    # --- Review ----------------------------------------------------------------
    letter = letter_from_state()
    reports, missing, current = _gather_reports(letter)
    errors, warnings = validate_letter(letter, reports, missing)
    if number_taken:
        errors.append(f"Letter number {letter.letter_number} has already been issued.")

    st.markdown("#### Review the Letter")
    with st.expander("✏️ Edit or improve the wording (optional)"):
        standard = "\n\n".join(standard_paragraphs(resolve_letter(letter, reports), reports))
        st.caption("Leave empty to use the standard wording generated from your data. Letterhead, "
                   "reference, date, recipient, subject and enclosure list are always generated "
                   "automatically and cannot be changed by AI.")
        b1, b2, b3 = st.columns(3)
        b1.button("Copy standard wording here", on_click=_copy_standard_wording, args=(standard,),
                  width="stretch")
        b2.button("Improve wording with Claude", icon="✨", width="stretch",
                  disabled=bool(errors), on_click=_improve_with_claude,
                  args=(resolve_letter(letter, reports).to_dict() | {"body_override": ""},
                        standard.split("\n\n")))
        b3.button("Reset to standard wording", on_click=_reset_wording, width="stretch")
        if not claude_service.is_configured():
            st.caption("AI wording is unavailable (ANTHROPIC_API_KEY not set); the standard "
                       "wording is always available.")
        if s.get("letter_ai_error"):
            st.error(s["letter_ai_error"])
        st.text_area("Letter body (paragraphs separated by a blank line)", key=P + "body_override",
                     height=220)

    if errors:
        st.error("**Before generating the letter:**\n\n" + "\n".join(f"- {e}" for e in errors))
    if warnings:
        st.warning("\n".join(f"- {w}" for w in warnings))
    if reports:
        content = build_letter_content(letter, reports, company)
        with st.container(border=True):
            st.text(letter_plain_text(content))

    # --- Documents ---------------------------------------------------------------
    st.markdown("#### Documents")
    c1, c2, c3 = st.columns(3)
    save_draft = c1.button("Save draft", icon="💾", disabled=bool(errors), width="stretch")
    letter_only = c2.button("Generate Covering Letter (PDF + Word)", icon="✉️",
                            disabled=bool(errors), width="stretch")
    package = c3.button("Generate Complete Submission Package", icon="📦", type="primary",
                        disabled=bool(errors), width="stretch",
                        help="Inspection report(s) PDF + Word, covering letter PDF + Word and a "
                             "ZIP. The letter is recorded as FINAL and cannot be overwritten.")

    try:
        if save_draft:
            repo.save_letter(letter)
            st.success(f"Draft letter {letter.letter_number} saved.")
        elif letter_only:
            pdf, docx, pages = build_letter_documents(letter, reports, company)
            repo.save_letter(letter)
            s["letter_files"] = ([pdf, docx], pages)
        elif package:
            _save_current_report_if_enclosed(letter, current)
            reports, missing = find_reports(repo, letter.report_numbers)
            s["letter_package"] = finalize_submission(repo, letter, reports, company)
            s["letter_status"] = STATUS_FINAL
            s.pop("letter_files", None)
    except LetterFinalizedError as e:
        st.error(str(e))
        st.button("Start a revision (new letter number)", key="rev2", on_click=_start_revision)
    except (LetterValidationError, ReportValidationError) as e:
        msgs = e.errors if isinstance(e, LetterValidationError) else e.validation.errors
        st.error("Cannot generate: " + "; ".join(msgs))

    if s.get("letter_files"):
        files, pages = s["letter_files"]
        st.success(f"Covering letter generated ({pages} page{'s' if pages != 1 else ''}). "
                   "Saved as a draft in Letter History.")
        if pages > 1:
            st.warning("The letter needs more than one page. Shorten the additional references "
                       "or the edited wording to fit one A4 page.")
        _downloads(files, "lf")

    pkg = s.get("letter_package")
    if pkg is not None:
        st.success(f"Submission package generated and letter {pkg.letter_number} recorded "
                   f"as FINAL. Covering letter: {pkg.letter_pages} page(s); reports: "
                   + ", ".join(f"{n} ({p} page)" for n, p in pkg.report_pages.items()) + ".")
        st.download_button(f"⬇️ Download all as ZIP ({pkg.zip_file.filename})", data=pkg.zip_file.data,
                           file_name=pkg.zip_file.filename, mime=pkg.zip_file.mime, type="primary",
                           key="pkg.zip")
        st.caption("Or download the files individually:")
        _downloads([pkg.letter_pdf, pkg.letter_docx], "pkg.l")
        for i in range(0, len(pkg.report_files), 2):
            _downloads(pkg.report_files[i:i + 2], f"pkg.r{i}")

    render_letter_history()


# --------------------------------------------------------------------------
# Letter history
# --------------------------------------------------------------------------

def render_letter_history() -> None:
    repo = get_repository()
    st.divider()
    st.markdown("#### Letter History")
    text = st.text_input("Search letters (letter no., recipient, indenter, project or report no.)",
                         key="lhist.search")
    rows = repo.search_letters(text)
    if not rows:
        st.caption("No covering letters saved yet.")
        return
    df = pd.DataFrame(rows)
    df["report_numbers"] = df["report_numbers"].apply(", ".join)
    st.dataframe(df.drop(columns=["id"]).rename(columns={
        "letter_number": "Letter No.", "letter_date": "Date", "recipient_organization": "Recipient",
        "indenter": "Indenter", "project_name": "Project", "report_numbers": "Enclosed reports",
        "status": "Status", "updated_at": "Last saved", "finalized_at": "Finalized",
    }), hide_index=True, width="stretch")

    labels = {r["id"]: f"{r['letter_number']} [{r['status']}] — {r['recipient_organization'] or '—'}"
              for r in rows}
    selected = st.selectbox("Select a letter", list(labels), format_func=labels.get, key="lhist.sel")
    c1, c2 = st.columns(2)
    c1.button("Reopen in the letter form", icon="📂", on_click=_reopen_letter, args=(selected,),
              width="stretch")
    if c2.button("Regenerate its documents", icon="🔁", width="stretch"):
        record = repo.load_letter(selected)
        if record["status"] == STATUS_FINAL and record["reports"]:
            # Exactly as finalized: stored letter, report snapshots and letterhead.
            reports, company = record["reports"], record["company"] or load_company(repo)
        else:
            reports, _ = find_reports(repo, record["letter"].report_numbers)
            company = load_company(repo)
        try:
            st.session_state["lhist_package"] = build_package(record["letter"], reports, company)
        except ReportValidationError as e:
            st.error("An enclosed report failed validation: " + "; ".join(e.validation.errors))
    pkg = st.session_state.get("lhist_package")
    if pkg is not None:
        st.download_button(f"⬇️ {pkg.zip_file.filename}", data=pkg.zip_file.data,
                           file_name=pkg.zip_file.filename, mime=pkg.zip_file.mime, key="lhist.zip")
