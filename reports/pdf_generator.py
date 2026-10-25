"""One-page A4 inspection report built with ReportLab Platypus.

Layout and styling are defined in this module only; the content comes from
reports.content. To restyle the report, change the palette, ``_styles`` or the
column widths below.

One-page guarantee: the report is built at full size first. If it overflows,
it is rebuilt with progressively more compact typography (``SCALES``). The
page count is returned so the caller can warn in the rare case that even the
most compact layout needs a second page.
"""

from __future__ import annotations

import io
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import KeepTogether, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from config import settings
from models.evaluation import EvaluationResult, Status
from models.inspection import InspectionReport
from reports.content import ReportContent, build_content

# --------------------------------------------------------------------------
# Palette
# --------------------------------------------------------------------------
INK = colors.HexColor("#1D2733")
MUTED = colors.HexColor("#5B6775")
NAVY = colors.HexColor("#1F3A5F")
RULE = colors.HexColor("#9AA5B1")
LABEL_BG = colors.HexColor("#EDF0F4")
STATUS_COLORS = {
    "PASS": (colors.HexColor("#17663A"), colors.HexColor("#E3F2E8")),
    "FAIL": (colors.HexColor("#A61B1B"), colors.HexColor("#FBE5E3")),
    "REVIEW": (colors.HexColor("#9A4A00"), colors.HexColor("#FDF0DC")),
    "REVIEW REQUIRED": (colors.HexColor("#9A4A00"), colors.HexColor("#FDF0DC")),
    "NOT EVALUATED": (MUTED, colors.white),
}

PAGE_W, PAGE_H = A4
MARGIN_X = 14 * mm
MARGIN_TOP = 12 * mm
MARGIN_BOTTOM = 14 * mm
CONTENT_W = PAGE_W - 2 * MARGIN_X

# Column widths (fractions of the content width).
INFO_COLS = [0.17, 0.33, 0.15, 0.35]
RESULT_COLS = [0.30, 0.24, 0.30, 0.16]

# Typography scale factors tried in order until the report fits on one page.
SCALES = (1.0, 0.93, 0.86, 0.79, 0.72)


# --------------------------------------------------------------------------
# Fonts: prefer an embedded Unicode TrueType font (renders symbols such as
# ≥, ±, µ); fall back to the built-in Helvetica.
# --------------------------------------------------------------------------
_FONT_CANDIDATES = [
    ("DejaVuSans.ttf", "DejaVuSans-Bold.ttf", ["/usr/share/fonts/truetype/dejavu"]),
    ("arial.ttf", "arialbd.ttf", ["C:/Windows/Fonts"]),
    ("LiberationSans-Regular.ttf", "LiberationSans-Bold.ttf",
     ["/usr/share/fonts/truetype/liberation", "/usr/share/fonts/liberation"]),
    ("Arial.ttf", "Arial Bold.ttf", ["/Library/Fonts", "/System/Library/Fonts/Supplemental"]),
]
_fonts: tuple[str, str] | None = None


def _register_fonts() -> tuple[str, str]:
    global _fonts
    if _fonts:
        return _fonts
    for regular, bold, folders in _FONT_CANDIDATES:
        for folder in folders:
            r, b = Path(folder) / regular, Path(folder) / bold
            if r.exists() and b.exists():
                try:
                    pdfmetrics.registerFont(TTFont("Report", str(r)))
                    pdfmetrics.registerFont(TTFont("Report-Bold", str(b)))
                    # Map <b> markup in Paragraphs to the bold face.
                    pdfmetrics.registerFontFamily("Report", normal="Report", bold="Report-Bold",
                                       italic="Report", boldItalic="Report-Bold")
                    _fonts = ("Report", "Report-Bold")
                    return _fonts
                except Exception:  # unreadable font file: try the next one
                    continue
    _fonts = ("Helvetica", "Helvetica-Bold")
    return _fonts


@dataclass
class PdfResult:
    data: bytes
    page_count: int
    scale: float


def _p(text: str) -> str:
    """Escape user text for a Paragraph and keep line breaks."""
    return escape(text or "").replace("\n", "<br/>")


def _styles(scale: float) -> dict[str, ParagraphStyle]:
    regular, bold = _register_fonts()

    def style(name, size, font=regular, color=INK, align=TA_LEFT, leading=1.22, **kw):
        return ParagraphStyle(
            name, fontName=font, fontSize=size * scale, leading=size * scale * leading,
            textColor=color, alignment=align, **kw,
        )

    return {
        "lab": style("lab", 7.5, bold, MUTED),
        "title": style("title", 16.5, bold, NAVY, leading=1.1),
        "subtitle": style("subtitle", 8, regular, MUTED),
        "meta_label": style("meta_label", 7, bold, MUTED),
        "meta_value": style("meta_value", 8.5, bold, INK),
        "section": style("section", 8, bold, colors.white),
        "label": style("label", 7.3, bold, MUTED),
        "value": style("value", 8.4),
        "th": style("th", 7.3, bold, MUTED),
        "cell": style("cell", 8.4),
        "cell_bold": style("cell_bold", 8.4, bold),
        "status": style("status", 7.6, bold, align=TA_CENTER),
        "detail": style("detail", 7, regular, MUTED),
        "body": style("body", 8.4, leading=1.3),
        "footnote": style("footnote", 6.4, regular, MUTED),
        "overall_label": style("overall_label", 8.5, bold, colors.white, TA_CENTER),
        "overall_value": style("overall_value", 15, bold, align=TA_CENTER, leading=1.05),
        "overall_reason": style("overall_reason", 7.6, regular, INK),
        "sample": style("sample", 7.5, bold, STATUS_COLORS["FAIL"][0], TA_RIGHT),
        "footer": style("footer", 6.3, regular, MUTED),
    }


def _section(title: str, st: dict, scale: float) -> Table:
    t = Table([[Paragraph(_p(title.upper()), st["section"])]], colWidths=[CONTENT_W])
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), NAVY),
        ("LEFTPADDING", (0, 0), (-1, -1), 5),
        ("TOPPADDING", (0, 0), (-1, -1), 2.6 * scale),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 2.6 * scale),
    ]))
    return t


def _grid_style(scale: float, label_cols=(), header=False) -> list:
    pad = 2.6 * scale
    cmds = [
        ("GRID", (0, 0), (-1, -1), 0.5, RULE),
        ("BOX", (0, 0), (-1, -1), 0.9, NAVY),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING", (0, 0), (-1, -1), 4),
        ("RIGHTPADDING", (0, 0), (-1, -1), 4),
        ("TOPPADDING", (0, 0), (-1, -1), pad),
        ("BOTTOMPADDING", (0, 0), (-1, -1), pad),
    ]
    for col in label_cols:
        cmds.append(("BACKGROUND", (col, 0), (col, -1), LABEL_BG))
    if header:
        cmds.append(("BACKGROUND", (0, 0), (-1, 0), LABEL_BG))
    return cmds


def _widths(fractions) -> list[float]:
    return [CONTENT_W * f for f in fractions]


def _header(c: ReportContent, st: dict, scale: float) -> list:
    left = [
        Paragraph(_p(settings.LAB_NAME.upper()), st["lab"]),
        Paragraph(c.title, st["title"]),
        Paragraph(_p(settings.LAB_SUBTITLE), st["subtitle"]),
    ]
    meta = Table(
        [
            [Paragraph("REPORT NO.", st["meta_label"]), Paragraph(_p(c.report_number), st["meta_value"])],
            [Paragraph("DATE", st["meta_label"]), Paragraph(_p(c.report_date), st["meta_value"])],
        ],
        colWidths=[22 * mm, 40 * mm],
    )
    meta.setStyle(TableStyle(_grid_style(scale * 0.8, label_cols=(0,))))
    right = [meta]
    if c.is_sample:
        right.append(Spacer(1, 2))
        right.append(Paragraph("SAMPLE DATA – NOT FOR RELEASE", st["sample"]))

    head = Table([[left, right]], colWidths=[CONTENT_W - 62 * mm, 62 * mm])
    head.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ("RIGHTPADDING", (0, 0), (-1, -1), 0),
        ("TOPPADDING", (0, 0), (-1, -1), 0),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
        ("LINEBELOW", (0, 0), (-1, 0), 1.6, NAVY),
        ("BOTTOMPADDING", (0, 0), (-1, 0), 5 * scale),
    ]))
    return [head]


def _info_table(rows, st: dict, scale: float) -> Table:
    data = [
        [Paragraph(_p(a), st["label"]), Paragraph(_p(b), st["value"]),
         Paragraph(_p(cc), st["label"]), Paragraph(_p(d), st["value"])]
        for a, b, cc, d in rows
    ]
    t = Table(data, colWidths=_widths(INFO_COLS))
    t.setStyle(TableStyle(_grid_style(scale, label_cols=(0, 2))))
    return t


def _status_cell(status: Status, st: dict) -> Paragraph:
    fg, _ = STATUS_COLORS[status.value]
    s = ParagraphStyle("s", parent=st["status"], textColor=fg)
    return Paragraph(status.value, s)


def _results_table(items, details: list[str], st: dict, scale: float) -> Table:
    header = [Paragraph(h, st["th"]) for h in ("TEST", "RESULT", "REQUIREMENT", "STATUS")]
    data = [header]
    cmds = _grid_style(scale, header=True)
    for row, item in enumerate(items, start=1):
        name = item.name + (" *" if item.mandatory else "")
        requirement = _p(item.requirement_text)
        if item.status == Status.REVIEW and item.note:
            requirement += f"<br/><font size='{6.6 * scale:.1f}' color='#9A4A00'>{_p(item.note)}</font>"
        data.append([
            Paragraph(_p(name), st["cell_bold"]),
            Paragraph(_p(item.result_text), st["cell"]),
            Paragraph(requirement, st["cell"]),
            _status_cell(item.status, st),
        ])
        cmds.append(("BACKGROUND", (3, row), (3, row), STATUS_COLORS[item.status.value][1]))
    for text in details:
        data.append([Paragraph(text, st["detail"]), "", "", ""])
        r = len(data) - 1
        cmds += [("SPAN", (0, r), (-1, r)), ("TOPPADDING", (0, r), (-1, r), 1.8 * scale),
                 ("BOTTOMPADDING", (0, r), (-1, r), 1.8 * scale)]
    t = Table(data, colWidths=_widths(RESULT_COLS), repeatRows=0)
    t.setStyle(TableStyle(cmds))
    return t


def _text_box(text: str, st: dict, scale: float, style="body") -> Table:
    t = Table([[Paragraph(_p(text), st[style])]], colWidths=[CONTENT_W])
    t.setStyle(TableStyle(_grid_style(scale) + [
        ("TOPPADDING", (0, 0), (-1, -1), 3.5 * scale),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3.5 * scale),
        ("LEFTPADDING", (0, 0), (-1, -1), 5),
    ]))
    return t


def _overall(c: ReportContent, st: dict, scale: float) -> Table:
    fg, bg = STATUS_COLORS[c.overall.value]
    value_style = ParagraphStyle("ov", parent=st["overall_value"], textColor=fg)
    reasons = "<br/>".join(_p(r) for r in c.overall_reasons[:4])
    t = Table(
        [[Paragraph("OVERALL<br/>RESULT", st["overall_label"]),
          Paragraph(c.overall.value, value_style),
          Paragraph(reasons, st["overall_reason"])]],
        colWidths=_widths([0.14, 0.30, 0.56]),
    )
    t.setStyle(TableStyle([
        ("BOX", (0, 0), (-1, -1), 1.4, NAVY),
        ("LINEAFTER", (0, 0), (1, 0), 0.6, RULE),
        ("BACKGROUND", (0, 0), (0, 0), NAVY),
        ("BACKGROUND", (1, 0), (1, 0), bg),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 6 * scale),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6 * scale),
        ("LEFTPADDING", (0, 0), (-1, -1), 5),
        ("RIGHTPADDING", (0, 0), (-1, -1), 5),
    ]))
    return t


def _signatures(c: ReportContent, st: dict, scale: float) -> Table:
    sig_h = 9 * mm * scale
    data = [
        [Paragraph("INSPECTED BY", st["th"]), "", Paragraph("REVIEWED BY", st["th"]), ""],
        [Paragraph("Name", st["label"]), Paragraph(_p(c.inspector), st["value"]),
         Paragraph("Name", st["label"]), ""],
        [Paragraph("Signature", st["label"]), "", Paragraph("Signature", st["label"]), ""],
        [Paragraph("Date", st["label"]), "", Paragraph("Date", st["label"]), ""],
    ]
    t = Table(data, colWidths=_widths([0.12, 0.38, 0.12, 0.38]),
              rowHeights=[None, None, sig_h, None])
    t.setStyle(TableStyle(_grid_style(scale, label_cols=(0, 2), header=True) + [
        ("SPAN", (0, 0), (1, 0)),
        ("SPAN", (2, 0), (3, 0)),
    ]))
    return t


def _build_story(c: ReportContent, scale: float) -> list:
    st = _styles(scale)
    gap = Spacer(1, 4.2 * mm * scale)
    small = Spacer(1, 1.2 * mm * scale)

    story = _header(c, st, scale)
    story += [gap, _section("Report Information", st, scale), small,
              _info_table(c.info_rows, st, scale)]

    details = []
    if c.tensile_details:
        details.append(f"<b>Tensile:</b> {_p(c.tensile_details)}")
    if c.hardness_details:
        details.append(f"<b>Hardness:</b> {_p(c.hardness_details)}")
    if c.criteria_source:
        details.append(f"<b>Acceptance criteria source:</b> {_p(c.criteria_source)}")
    story += [gap, _section("Mechanical Testing", st, scale), small,
              _results_table(c.mechanical, details, st, scale)]

    metal = _info_table(c.metallography_rows, st, scale)
    wide_rows = [("Preparation", c.preparation)] if c.preparation else []
    wide_rows.append(("Microstructure Observation", c.microstructure))
    micro = Table(
        [[Paragraph(_p(label), st["label"]), Paragraph(_p(text), st["body"])] for label, text in wide_rows],
        colWidths=_widths([INFO_COLS[0], 1 - INFO_COLS[0]]),
    )
    micro.setStyle(TableStyle(_grid_style(scale, label_cols=(0,))))
    story += [gap, _section("Metallography", st, scale), small,
              _results_table(c.metallography, [], st, scale), metal, micro]

    story += [Spacer(1, 1.2 * mm * scale), Paragraph(_p(c.footnote), st["footnote"])]

    story += [gap, _section("Inspection Summary", st, scale), small, _text_box(c.summary, st, scale)]
    if c.remarks:
        story += [small, _text_box(f"Remarks: {c.remarks}", st, scale)]

    story += [gap, KeepTogether([_overall(c, st, scale), gap, _signatures(c, st, scale)])]
    return story


def _make_page_decorator(c: ReportContent, total_pages: int, page_counter: list):
    regular, bold = _register_fonts()
    generated = datetime.now().strftime("%Y-%m-%d %H:%M")

    def on_page(canvas, doc):
        page_counter[0] = max(page_counter[0], canvas.getPageNumber())
        canvas.saveState()
        if c.is_sample:
            canvas.saveState()
            canvas.setFont(bold, 70)
            canvas.setFillColor(colors.Color(0.8, 0.1, 0.1, alpha=0.08))
            canvas.translate(PAGE_W / 2, PAGE_H / 2)
            canvas.rotate(40)
            canvas.drawCentredString(0, -20, "SAMPLE DATA")
            canvas.restoreState()
        y = MARGIN_BOTTOM - 6 * mm
        canvas.setStrokeColor(RULE)
        canvas.setLineWidth(0.5)
        canvas.line(MARGIN_X, y + 3.2 * mm, PAGE_W - MARGIN_X, y + 3.2 * mm)
        canvas.setFont(regular, 6.3)
        canvas.setFillColor(MUTED)
        canvas.drawString(MARGIN_X, y, f"Form {settings.FORM_NUMBER}")
        note = "Test status calculated deterministically from stated criteria"
        if c.ai_used:
            note += " · AI-assisted wording reviewed by inspector"
        canvas.drawString(MARGIN_X, y - 3 * mm, note)
        canvas.drawRightString(PAGE_W - MARGIN_X, y, f"Generated {generated} · Page {canvas.getPageNumber()} of {total_pages}")
        canvas.restoreState()

    return on_page


def _render(c: ReportContent, scale: float, total_pages: int = 1) -> tuple[bytes, int]:
    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf, pagesize=A4,
        leftMargin=MARGIN_X, rightMargin=MARGIN_X,
        topMargin=MARGIN_TOP, bottomMargin=MARGIN_BOTTOM,
        title=f"Metal Inspection Report {c.report_number}",
        author=c.inspector or settings.LAB_NAME,
        subject="Metal Inspection Report",
        creator="Metal Inspection Report Generator",
    )
    pages = [0]
    decorator = _make_page_decorator(c, total_pages, pages)
    doc.build(_build_story(c, scale), onFirstPage=decorator, onLaterPages=decorator)
    return buf.getvalue(), pages[0]


def generate_pdf(report: InspectionReport, evaluation: EvaluationResult) -> PdfResult:
    """Render the report, shrinking typography if needed to keep it on one page."""
    content = build_content(report, evaluation)
    data, pages = b"", 0
    for scale in SCALES:
        data, pages = _render(content, scale)
        if pages <= 1:
            return PdfResult(data, pages, scale)
    # Still too long at the most compact scale: re-render with the real page total.
    data, pages = _render(content, SCALES[-1], total_pages=pages)
    return PdfResult(data, pages, SCALES[-1])

