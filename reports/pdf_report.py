"""
pdf_report.py
=============
Generates a professional, branded P&L PDF report.
YOUR branding only — no third-party labels.

100% local — zero network calls.
"""

from pathlib import Path
from datetime import datetime
from decimal import Decimal
from typing import Dict, List, Optional

from reportlab.lib.pagesizes import LETTER
from reportlab.lib.units import inch
from reportlab.lib.colors import HexColor
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_LEFT, TA_CENTER, TA_RIGHT
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
    HRFlowable, PageBreak, KeepTogether,
)

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from financials.calculator import PLStatement


# ── Colors ──────────────────────────────────────────────────────

HEADER_BG   = HexColor("#1a1a2e")
ACCENT      = HexColor("#e94560")
WHITE       = HexColor("#ffffff")
BLACK       = HexColor("#000000")
GRAY        = HexColor("#666666")
LIGHT_GRAY  = HexColor("#cccccc")
GREEN       = HexColor("#28a745")
YELLOW_BG   = HexColor("#fff8e1")
RED_BG      = HexColor("#fff0f0")
GREEN_BG    = HexColor("#f0fff0")
ROW_ALT     = HexColor("#f5f5f5")

FLAG_COLORS = {
    "green": GREEN_BG,
    "yellow": YELLOW_BG,
    "red": RED_BG,
}


def _styles():
    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle("Title2", parent=styles["Title"],
        fontSize=22, textColor=HEADER_BG, spaceAfter=4))
    styles.add(ParagraphStyle("Sub", parent=styles["Normal"],
        fontSize=10, textColor=GRAY, spaceAfter=14))
    styles.add(ParagraphStyle("Section", parent=styles["Heading2"],
        fontSize=14, textColor=HEADER_BG, spaceBefore=18, spaceAfter=8))
    styles.add(ParagraphStyle("Body", parent=styles["Normal"],
        fontSize=10, textColor=BLACK))
    styles.add(ParagraphStyle("Small", parent=styles["Normal"],
        fontSize=8, textColor=GRAY))
    styles.add(ParagraphStyle("BigNum", parent=styles["Normal"],
        fontSize=18, textColor=HEADER_BG, alignment=TA_CENTER))
    styles.add(ParagraphStyle("BigLabel", parent=styles["Normal"],
        fontSize=9, textColor=GRAY, alignment=TA_CENTER))
    styles.add(ParagraphStyle("GreenBold", parent=styles["Normal"],
        fontSize=10, textColor=GREEN))
    styles.add(ParagraphStyle("RedBold", parent=styles["Normal"],
        fontSize=10, textColor=ACCENT))
    return styles


def _money(val) -> str:
    """Format a Decimal as $X,XXX.XX"""
    v = float(val)
    if v < 0:
        return f"-${abs(v):,.2f}"
    return f"${v:,.2f}"


def _pct(val) -> str:
    return f"{float(val):.1f}%"


# ════════════════════════════════════════════════════════════════
#  Main PDF generator
# ════════════════════════════════════════════════════════════════

def generate_pl_pdf(
    pl: PLStatement,
    scorecard: Optional[Dict] = None,
    comparisons: Optional[List[Dict]] = None,
    output_path: str = "output/pl_report.pdf",
    business_name: str = "",
    preparer_name: str = "",
) -> str:
    """
    Generate a multi-page P&L PDF:
    - Page 1: Executive summary with 3 big numbers + scorecard
    - Page 2: Full P&L line-item breakdown
    - Page 3: Trends (if multi-period comparisons provided)
    - Page 4: Recommendations + warnings

    Returns path to generated PDF.
    """
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    styles = _styles()

    doc = SimpleDocTemplate(
        str(output_path),
        pagesize=LETTER,
        leftMargin=0.75 * inch,
        rightMargin=0.75 * inch,
        topMargin=0.6 * inch,
        bottomMargin=0.6 * inch,
        title=f"P&L Report — {pl.period_label}",
        author=preparer_name or "Financial Analyst",
    )

    story = []

    # ════════════════════════════════════════════════════════════
    #  PAGE 1 — Executive Summary
    # ════════════════════════════════════════════════════════════

    story.append(Paragraph(
        f"PROFIT &amp; LOSS STATEMENT", styles["Title2"]
    ))
    meta_parts = [pl.period_label]
    if business_name:
        meta_parts.insert(0, business_name)
    meta_parts.append(f"Generated {datetime.now().strftime('%Y-%m-%d')}")
    if preparer_name:
        meta_parts.append(f"Prepared by {preparer_name}")
    story.append(Paragraph(" &nbsp;|&nbsp; ".join(meta_parts), styles["Sub"]))

    story.append(HRFlowable(width="100%", thickness=2, color=HEADER_BG, spaceAfter=16))

    # ── 3 Big Numbers ───────────────────────────────────────────

    big_data = [
        [
            Paragraph(_money(pl.net_revenue), styles["BigNum"]),
            Paragraph(_money(pl.gross_profit), styles["BigNum"]),
            Paragraph(_money(pl.net_profit), styles["BigNum"]),
        ],
        [
            Paragraph("NET REVENUE", styles["BigLabel"]),
            Paragraph(f"GROSS PROFIT ({_pct(pl.gross_margin_pct)})", styles["BigLabel"]),
            Paragraph(f"NET PROFIT ({_pct(pl.net_margin_pct)})", styles["BigLabel"]),
        ],
    ]
    big_table = Table(big_data, colWidths=[2.3 * inch] * 3)
    big_table.setStyle(TableStyle([
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 10),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 10),
        ("BOX", (0, 0), (-1, -1), 1, LIGHT_GRAY),
        ("LINEBELOW", (0, 0), (-1, 0), 0.5, LIGHT_GRAY),
    ]))
    story.append(big_table)
    story.append(Spacer(1, 20))

    # ── Scorecard ───────────────────────────────────────────────

    if scorecard and scorecard.get("metrics"):
        story.append(Paragraph("PERFORMANCE SCORECARD", styles["Section"]))

        sc_data = [["Metric", "Value", "Status", "Action"]]
        for metric, data in scorecard["metrics"].items():
            label = metric.replace("_", " ").title()
            val = f"{data.get('value', '')}%"
            status = data.get("status", "")
            action = data.get("action", "—")
            sc_data.append([label, val, status, action])

        sc_table = Table(sc_data, colWidths=[1.5*inch, 0.8*inch, 1.2*inch, 3.4*inch])
        sc_style = [
            ("BACKGROUND", (0, 0), (-1, 0), HEADER_BG),
            ("TEXTCOLOR", (0, 0), (-1, 0), WHITE),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, -1), 9),
            ("GRID", (0, 0), (-1, -1), 0.5, LIGHT_GRAY),
            ("TOPPADDING", (0, 0), (-1, -1), 6),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
            ("LEFTPADDING", (0, 0), (-1, -1), 8),
        ]
        # Color rows by flag
        for i, (metric, data) in enumerate(scorecard["metrics"].items(), start=1):
            bg = FLAG_COLORS.get(data.get("flag", ""), WHITE)
            sc_style.append(("BACKGROUND", (0, i), (-1, i), bg))

        sc_table.setStyle(TableStyle(sc_style))
        story.append(sc_table)

        overall = scorecard.get("overall", "")
        if overall:
            style_name = "GreenBold" if overall == "HEALTHY" else "RedBold"
            story.append(Spacer(1, 8))
            story.append(Paragraph(f"Overall: {overall}", styles[style_name]))

    # ════════════════════════════════════════════════════════════
    #  PAGE 2 — Full P&L Breakdown
    # ════════════════════════════════════════════════════════════

    story.append(PageBreak())
    story.append(Paragraph("DETAILED P&amp;L BREAKDOWN", styles["Title2"]))
    story.append(Paragraph(pl.period_label, styles["Sub"]))
    story.append(HRFlowable(width="100%", thickness=1, color=LIGHT_GRAY, spaceAfter=12))

    def _row(label, amount, pct_val=None, bold=False, indent=0):
        prefix = "&nbsp;" * (indent * 4)
        font = "Helvetica-Bold" if bold else "Helvetica"
        cells = [
            Paragraph(f"{prefix}{label}", ParagraphStyle("r", fontName=font, fontSize=9)),
            _money(amount),
        ]
        if pct_val is not None:
            cells.append(_pct(pct_val))
        else:
            cells.append("")
        return cells

    pl_rows = [
        ["", "Amount", "% Rev"],
        _row("Gross Revenue", pl.gross_revenue, bold=True),
        _row("Less: Refunds", pl.refunds, indent=1),
        _row("NET REVENUE", pl.net_revenue, Decimal("100"), bold=True),
        ["", "", ""],
        _row("Inventory / Materials", pl.inventory_costs, indent=1),
        _row("Direct Labor", pl.direct_labor, indent=1),
        _row("TOTAL COGS", pl.total_cogs, pl.cogs_pct, bold=True),
        ["", "", ""],
        _row("GROSS PROFIT", pl.gross_profit, pl.gross_margin_pct, bold=True),
        ["", "", ""],
        _row("Rent", pl.rent, pl.rent_pct, indent=1),
        _row("Utilities", pl.utilities, indent=1),
        _row("Insurance", pl.insurance, indent=1),
        _row("Marketing", pl.marketing, indent=1),
        _row("Software / Subscriptions", pl.software, indent=1),
        _row("Bank Fees", pl.bank_fees, indent=1),
        _row("Other Operating", pl.other_opex, indent=1),
        _row("TOTAL OPERATING EXPENSES", pl.total_opex, pl.opex_pct, bold=True),
        ["", "", ""],
        _row("OPERATING INCOME", pl.operating_income, pl.operating_margin_pct, bold=True),
        ["", "", ""],
        _row("Loan / Debt Payments", pl.loan_payments, indent=1),
        ["", "", ""],
        _row("NET PROFIT (BOTTOM LINE)", pl.net_profit, pl.net_margin_pct, bold=True),
    ]

    pl_table = Table(pl_rows, colWidths=[4.0*inch, 1.5*inch, 1.0*inch])
    pl_style = [
        ("BACKGROUND", (0, 0), (-1, 0), HEADER_BG),
        ("TEXTCOLOR", (0, 0), (-1, 0), WHITE),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("ALIGN", (1, 0), (-1, -1), "RIGHT"),
        ("GRID", (0, 0), (-1, -1), 0.3, LIGHT_GRAY),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [WHITE, ROW_ALT]),
    ]

    # Highlight the bottom line row
    pl_style.append(("BACKGROUND", (0, -1), (-1, -1), HexColor("#e8e8e8")))
    pl_style.append(("FONTNAME", (0, -1), (-1, -1), "Helvetica-Bold"))

    pl_table.setStyle(TableStyle(pl_style))
    story.append(pl_table)

    # ════════════════════════════════════════════════════════════
    #  PAGE 3 — Trends (optional)
    # ════════════════════════════════════════════════════════════

    if comparisons:
        story.append(PageBreak())
        story.append(Paragraph("PERIOD COMPARISON", styles["Title2"]))
        story.append(HRFlowable(width="100%", thickness=1, color=LIGHT_GRAY, spaceAfter=12))

        trend_data = [["From", "To", "Rev Change", "Profit Change", "Margin Δ"]]
        for c in comparisons:
            trend_data.append([
                c["from"],
                c["to"],
                f"{c['revenue_change_pct']:+.1f}%",
                f"{c['profit_change_pct']:+.1f}%",
                f"{c['margin_change']:+.1f}%",
            ])

        trend_table = Table(trend_data, colWidths=[1.3*inch]*5)
        trend_table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), HEADER_BG),
            ("TEXTCOLOR", (0, 0), (-1, 0), WHITE),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, -1), 9),
            ("ALIGN", (2, 0), (-1, -1), "CENTER"),
            ("GRID", (0, 0), (-1, -1), 0.5, LIGHT_GRAY),
            ("TOPPADDING", (0, 0), (-1, -1), 6),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ]))
        story.append(trend_table)

    # ════════════════════════════════════════════════════════════
    #  PAGE 4 — Warnings & Recommendations
    # ════════════════════════════════════════════════════════════

    warnings = pl.validate()
    recs = []
    if scorecard:
        for metric, data in scorecard.get("metrics", {}).items():
            if data.get("flag") in ("red", "yellow") and data.get("action"):
                recs.append(data["action"])

    if warnings or recs:
        story.append(PageBreak())
        story.append(Paragraph("FINDINGS &amp; RECOMMENDATIONS", styles["Title2"]))
        story.append(HRFlowable(width="100%", thickness=1, color=LIGHT_GRAY, spaceAfter=12))

        if warnings:
            story.append(Paragraph("VALIDATION WARNINGS", styles["Section"]))
            for w in warnings:
                story.append(Paragraph(f"&#9888; {w}", styles["Body"]))
                story.append(Spacer(1, 4))

        if recs:
            story.append(Spacer(1, 12))
            story.append(Paragraph("ACTION ITEMS", styles["Section"]))
            for i, r in enumerate(recs, 1):
                story.append(Paragraph(f"{i}. {r}", styles["Body"]))
                story.append(Spacer(1, 4))

    # ── Footer ──────────────────────────────────────────────────

    story.append(Spacer(1, 30))
    story.append(HRFlowable(width="100%", thickness=1, color=LIGHT_GRAY, spaceAfter=8))
    story.append(Paragraph(
        "CONFIDENTIAL — Generated locally. "
        "No data was transmitted over any network. "
        "Delete after review if required.",
        styles["Small"],
    ))

    doc.build(story)
    return str(output_path)
