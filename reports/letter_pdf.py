"""Covering letter PDF (ReportLab Platypus).

Letterhead, margins, typography and signature block are defined here,
independently of the inspection report. Fonts and colours are shared with
reports.pdf_generator for a consistent look.

The letter is built at normal size first; if it overflows A4 it is rebuilt
with tighter spacing and only slightly smaller type (never below ~9.6 pt).
"""

from __future__ import annotations

import base64
import io
from dataclasses import dataclass

from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY, TA_LEFT, TA_RIGHT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.lib.utils import ImageReader
from reportlab.platypus import Image, KeepTogether, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from reports.letter_content import LetterContent
from reports.pdf_generator import INK, MUTED, NAVY, RULE, _p, _register_fonts

PAGE_W, PAGE_H = A4
MARGIN_X = 22 * mm
MARGIN_TOP = 14 * mm
MARGIN_BOTTOM = 18 * mm
CONTENT_W = PAGE_W - 2 * MARGIN_X - 12  # minus the frame's default 6 pt padding each side
SCALES = (1.0, 0.96, 0.92)
LOGO_H = 15 * mm


@dataclass
class LetterPdfResult:
    data: bytes
    page_count: int


def _styles(scale: float) -> dict[str, ParagraphStyle]:
    regular, bold = _register_fonts()

    def style(name, size, font=regular, color=INK, align=TA_LEFT, leading=1.4, after=0.0):
        return ParagraphStyle(name, fontName=font, fontSize=size * scale,
                              leading=size * scale * leading, textColor=color, alignment=align,
                              spaceAfter=after * scale)

    return {
        "company": style("company", 17, bold, NAVY, TA_CENTER, leading=1.15),
        "tagline": style("tagline", 8.5, regular, MUTED, TA_CENTER, leading=1.4),
        "contact": style("contact", 7.8, regular, MUTED, TA_CENTER, leading=1.35),
        "meta": style("meta", 10.5),
        "meta_right": style("meta_right", 10.5, align=TA_RIGHT),
        "body": style("body", 10.5, align=TA_JUSTIFY, leading=1.45, after=7),
        "plain": style("plain", 10.5),
        "subject": style("subject", 10.5, bold, leading=1.4),
        "ref": style("ref", 9.5, regular, MUTED),
        "bold": style("bold", 10.5, bold),
        "small": style("small", 9.5, leading=1.4),
        "footer": style("footer", 7.5, regular, MUTED),
    }


def _logo(c: LetterContent):
    if not c.company.logo_base64:
        return None
    try:
        raw = base64.b64decode(c.company.logo_base64)
        w, h = ImageReader(io.BytesIO(raw)).getSize()
        return Image(io.BytesIO(raw), width=LOGO_H * w / h, height=LOGO_H)
    except Exception:  # unreadable image: letter is still produced without it
        return None


def letterhead_lines(c: LetterContent) -> list[str]:
    """Address and contact lines under the name; only details that were provided."""
    lines = []
    address = ", ".join(line.strip() for line in c.company.address.splitlines() if line.strip())
    if address:
        lines.append(address)
    if c.company.contact_line:
        lines.append(c.company.contact_line)
    return lines


def _letterhead(c: LetterContent, st: dict) -> Table:
    """Centred letterhead: name, tagline, address/contact; optional logo on the left."""
    logo = _logo(c)
    name_style = st["company"]
    if logo is not None:  # less width beside a logo: slightly smaller name
        name_style = ParagraphStyle("company_logo", parent=name_style,
                                    fontSize=name_style.fontSize * 0.88,
                                    leading=name_style.leading * 0.88)
    block = [Paragraph(_p(c.company.name), name_style)]
    if c.company.tagline.strip():
        block.append(Paragraph(_p(c.company.tagline), st["tagline"]))
    block += [Paragraph(_p(line), st["contact"]) for line in letterhead_lines(c)]

    if logo is not None:
        side = logo.drawWidth + 4 * mm
        # An empty column on the right of equal width keeps the text block centred.
        cells, widths = [[logo, block, ""]], [side, CONTENT_W - 2 * side, side]
    else:
        cells, widths = [[block]], [CONTENT_W]
    t = Table(cells, colWidths=widths)
    t.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ("RIGHTPADDING", (0, 0), (-1, -1), 0),
        ("TOPPADDING", (0, 0), (-1, -1), 0),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ("LINEBELOW", (0, 0), (-1, 0), 1.6, NAVY),
    ]))
    return t


def _story(c: LetterContent, scale: float) -> list:
    st = _styles(scale)
    gap = lambda h: Spacer(1, h * mm * scale)  # noqa: E731

    story = [_letterhead(c, st), gap(7)]

    meta = Table(
        [[Paragraph(f"<b>Ref. No.:</b> {_p(c.letter_number)}", st["meta"]),
          Paragraph(f"<b>Date:</b> {_p(c.date_text)}", st["meta_right"])]],
        colWidths=[CONTENT_W * 0.6, CONTENT_W * 0.4],
    )
    meta.setStyle(TableStyle([("LEFTPADDING", (0, 0), (-1, -1), 0),
                              ("RIGHTPADDING", (0, 0), (-1, -1), 0)]))
    story += [meta, gap(6)]

    if c.recipient_lines:
        story.append(Paragraph("To,", st["plain"]))
        story.append(Paragraph("<br/>".join(_p(x) for x in c.recipient_lines), st["plain"]))
        story.append(gap(6))

    story.append(Paragraph(f"Subject: {_p(c.subject)}", st["subject"]))
    for ref in c.reference_lines:
        story.append(Paragraph(_p(ref), st["ref"]))
    story += [gap(5), Paragraph(_p(c.salutation), st["plain"]), gap(3)]
    story += [Paragraph(_p(p), st["body"]) for p in c.paragraphs]

    signature = [gap(2), Paragraph(_p(c.closing), st["plain"])]
    if c.for_company:
        signature.append(Paragraph(_p(c.for_company), st["bold"]))
    signature.append(gap(18))  # space for the signature
    if c.signatory_name:
        signature.append(Paragraph(_p(c.signatory_name), st["bold"]))
    signature.append(Paragraph(_p(c.signatory_designation), st["plain"]))
    story.append(KeepTogether(signature))

    if c.enclosures:
        items = [Paragraph("<b>Enclosures:</b>", st["small"])]
        items += [Paragraph(f"{i}.&nbsp;&nbsp;{_p(e)}", st["small"])
                  for i, e in enumerate(c.enclosures, start=1)]
        story += [gap(7), KeepTogether(items)]
    return story


def _footer(c: LetterContent):
    regular, _ = _register_fonts()
    text = "  |  ".join(p for p in (c.company.name, c.company.contact_line) if p)

    def on_page(canvas, doc):
        canvas.saveState()
        y = MARGIN_BOTTOM - 9 * mm
        canvas.setStrokeColor(RULE)
        canvas.setLineWidth(0.5)
        canvas.line(MARGIN_X, y + 3.5 * mm, PAGE_W - MARGIN_X, y + 3.5 * mm)
        canvas.setFont(regular, 7.5)
        canvas.setFillColor(MUTED)
        canvas.drawCentredString(PAGE_W / 2, y, text)
        canvas.restoreState()

    return on_page


def _render(c: LetterContent, scale: float) -> tuple[bytes, int]:
    buf = io.BytesIO()
    pages = [0]
    footer = _footer(c)

    def on_page(canvas, doc):
        pages[0] = max(pages[0], canvas.getPageNumber())
        footer(canvas, doc)

    doc = SimpleDocTemplate(
        buf, pagesize=A4, leftMargin=MARGIN_X, rightMargin=MARGIN_X,
        topMargin=MARGIN_TOP, bottomMargin=MARGIN_BOTTOM,
        title=f"Covering Letter {c.letter_number}", author=c.company.name,
        subject=c.subject, creator="Metal Inspection Report Generator",
    )
    doc.build(_story(c, scale), onFirstPage=on_page, onLaterPages=on_page)
    return buf.getvalue(), pages[0]


def generate_letter_pdf(content: LetterContent) -> LetterPdfResult:
    data, pages = b"", 0
    for scale in SCALES:
        data, pages = _render(content, scale)
        if pages <= 1:
            break
    return LetterPdfResult(data, pages)
