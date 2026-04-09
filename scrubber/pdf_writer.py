"""
pdf_writer.py
=============
Generates professional PDF documents from scrubbed text and reports.
Uses reportlab — 100% local, zero network.
"""

from pathlib import Path
from datetime import datetime

from reportlab.lib.pagesizes import LETTER
from reportlab.lib.units import inch
from reportlab.lib.colors import HexColor
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_LEFT, TA_CENTER
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
    HRFlowable, PageBreak,
)


# ── Colors ──────────────────────────────────────────────────────

DARK_BG     = HexColor("#1a1a2e")
ACCENT      = HexColor("#e94560")
HEADER_BG   = HexColor("#16213e")
ROW_ALT     = HexColor("#f0f0f0")
WHITE       = HexColor("#ffffff")
BLACK       = HexColor("#000000")
GRAY        = HexColor("#666666")
LIGHT_GRAY  = HexColor("#cccccc")
GREEN       = HexColor("#28a745")
RED_LIGHT   = HexColor("#fff0f0")


def _build_styles():
    """Create custom paragraph styles."""
    styles = getSampleStyleSheet()

    styles.add(ParagraphStyle(
        "DocTitle",
        parent=styles["Title"],
        fontSize=20,
        textColor=HEADER_BG,
        spaceAfter=6,
    ))
    styles.add(ParagraphStyle(
        "DocSubtitle",
        parent=styles["Normal"],
        fontSize=10,
        textColor=GRAY,
        spaceAfter=16,
    ))
    styles.add(ParagraphStyle(
        "SectionHead",
        parent=styles["Heading2"],
        fontSize=13,
        textColor=HEADER_BG,
        spaceBefore=16,
        spaceAfter=8,
    ))
    styles.add(ParagraphStyle(
        "BodyMono",
        parent=styles["Normal"],
        fontName="Courier",
        fontSize=8,
        leading=11,
        textColor=BLACK,
    ))
    styles.add(ParagraphStyle(
        "SmallGray",
        parent=styles["Normal"],
        fontSize=8,
        textColor=GRAY,
    ))
    styles.add(ParagraphStyle(
        "Privacy",
        parent=styles["Normal"],
        fontSize=9,
        textColor=GREEN,
        spaceBefore=8,
    ))

    return styles


def generate_scrubbed_pdf(
    scrubbed_text: str,
    report_text: str,
    output_path: str | Path,
    source_filename: str = "",
    detections_summary: dict | None = None,
) -> str:
    """
    Generate a professional PDF containing:
    - Cover header with metadata
    - Scrubbed statement content
    - Redaction report with breakdown table
    - Privacy footer

    Returns the path to the generated PDF.
    """
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    styles = _build_styles()

    doc = SimpleDocTemplate(
        str(output_path),
        pagesize=LETTER,
        leftMargin=0.75 * inch,
        rightMargin=0.75 * inch,
        topMargin=0.75 * inch,
        bottomMargin=0.75 * inch,
        title="Scrubbed Bank Statement",
        author="Bank Statement Scrubber v2.0",
    )

    story = []

    # ── Page 1: Cover + Scrubbed Content ────────────────────────

    # Header
    story.append(Paragraph("SCRUBBED BANK STATEMENT", styles["DocTitle"]))
    story.append(Paragraph(
        f"Source: {source_filename or 'N/A'} &nbsp;|&nbsp; "
        f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} &nbsp;|&nbsp; "
        f"Tool: Bank Statement Scrubber v2.0",
        styles["DocSubtitle"],
    ))

    # Privacy badge
    story.append(Paragraph(
        "&#9989; ALL PROCESSING WAS LOCAL — NO DATA WAS TRANSMITTED",
        styles["Privacy"],
    ))
    story.append(Spacer(1, 12))

    # Horizontal rule
    story.append(HRFlowable(
        width="100%", thickness=1, color=LIGHT_GRAY, spaceAfter=12,
    ))

    # Scrubbed content
    story.append(Paragraph("SCRUBBED CONTENT", styles["SectionHead"]))

    # Split into lines and render as monospace paragraphs
    for line in scrubbed_text.split("\n"):
        # Escape XML characters for reportlab
        safe = (
            line
            .replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
        )
        if not safe.strip():
            story.append(Spacer(1, 6))
        else:
            story.append(Paragraph(safe, styles["BodyMono"]))

    # ── Page 2: Redaction Report ────────────────────────────────

    story.append(PageBreak())
    story.append(Paragraph("REDACTION REPORT", styles["DocTitle"]))
    story.append(Paragraph(
        "Audit log — review then delete this page if not needed.",
        styles["DocSubtitle"],
    ))
    story.append(HRFlowable(
        width="100%", thickness=1, color=LIGHT_GRAY, spaceAfter=12,
    ))

    # Summary table
    if detections_summary:
        story.append(Paragraph("DETECTION BREAKDOWN", styles["SectionHead"]))

        table_data = [["Data Type", "Count"]]
        total = 0
        for dtype, count in sorted(detections_summary.items()):
            table_data.append([dtype, str(count)])
            total += count
        table_data.append(["TOTAL", str(total)])

        t = Table(table_data, colWidths=[4 * inch, 1.5 * inch])
        t.setStyle(TableStyle([
            ("BACKGROUND",  (0, 0), (-1, 0), HEADER_BG),
            ("TEXTCOLOR",   (0, 0), (-1, 0), WHITE),
            ("FONTNAME",    (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE",    (0, 0), (-1, 0), 10),
            ("FONTNAME",    (0, 1), (-1, -1), "Helvetica"),
            ("FONTSIZE",    (0, 1), (-1, -1), 9),
            ("ALIGN",       (1, 0), (1, -1), "CENTER"),
            ("BACKGROUND",  (0, -1), (-1, -1), HexColor("#e8e8e8")),
            ("FONTNAME",    (0, -1), (-1, -1), "Helvetica-Bold"),
            ("GRID",        (0, 0), (-1, -1), 0.5, LIGHT_GRAY),
            ("ROWBACKGROUNDS", (0, 1), (-1, -2), [WHITE, ROW_ALT]),
            ("TOPPADDING",  (0, 0), (-1, -1), 6),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
            ("LEFTPADDING", (0, 0), (-1, -1), 10),
        ]))
        story.append(t)
        story.append(Spacer(1, 16))

    # Full report text
    story.append(Paragraph("FULL REPORT LOG", styles["SectionHead"]))
    for line in report_text.split("\n"):
        safe = (
            line
            .replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
        )
        if not safe.strip():
            story.append(Spacer(1, 4))
        else:
            story.append(Paragraph(safe, styles["BodyMono"]))

    # ── Footer ──────────────────────────────────────────────────

    story.append(Spacer(1, 24))
    story.append(HRFlowable(
        width="100%", thickness=1, color=LIGHT_GRAY, spaceAfter=8,
    ))
    story.append(Paragraph(
        "REVIEW CHECKLIST: "
        "[ ] Account numbers masked &nbsp; "
        "[ ] Client name removed &nbsp; "
        "[ ] No addresses remain &nbsp; "
        "[ ] Delete this file after review",
        styles["SmallGray"],
    ))
    story.append(Paragraph(
        "Generated by Bank Statement Scrubber v2.0 — "
        "100% local processing, zero network transmission.",
        styles["SmallGray"],
    ))

    # Build PDF
    doc.build(story)
    return str(output_path)
