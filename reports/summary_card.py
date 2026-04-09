"""
summary_card.py
===============
One-page snapshot PDF — the quick-hit deliverable.
Shows 3 big numbers, health score, and top 3 action items.
"""

from pathlib import Path
from datetime import datetime
from typing import Dict, Optional

from reportlab.lib.pagesizes import LETTER
from reportlab.lib.units import inch
from reportlab.lib.colors import HexColor
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
    HRFlowable,
)

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from financials.calculator import PLStatement


HEADER_BG  = HexColor("#1a1a2e")
WHITE      = HexColor("#ffffff")
GRAY       = HexColor("#666666")
LIGHT_GRAY = HexColor("#cccccc")
GREEN      = HexColor("#28a745")
YELLOW     = HexColor("#ffc107")
RED        = HexColor("#dc3545")


def _money(val) -> str:
    from decimal import Decimal
    v = Decimal(str(val))
    abs_v = abs(v)
    formatted = f"{abs_v:,.2f}"
    return f"-${formatted}" if v < 0 else f"${formatted}"


def generate_summary_card(
    pl: PLStatement,
    scorecard: Optional[Dict] = None,
    output_path: str = "output/summary_card.pdf",
    business_name: str = "",
) -> str:
    """One-page executive snapshot."""

    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle("CardTitle", parent=styles["Title"],
        fontSize=24, textColor=HEADER_BG, spaceAfter=4))
    styles.add(ParagraphStyle("CardSub", parent=styles["Normal"],
        fontSize=11, textColor=GRAY, spaceAfter=16))
    styles.add(ParagraphStyle("BigNum", parent=styles["Normal"],
        fontSize=28, textColor=HEADER_BG, alignment=TA_CENTER))
    styles.add(ParagraphStyle("BigLabel", parent=styles["Normal"],
        fontSize=10, textColor=GRAY, alignment=TA_CENTER, spaceAfter=8))
    styles.add(ParagraphStyle("HealthGreen", parent=styles["Normal"],
        fontSize=14, textColor=GREEN, alignment=TA_CENTER))
    styles.add(ParagraphStyle("HealthYellow", parent=styles["Normal"],
        fontSize=14, textColor=YELLOW, alignment=TA_CENTER))
    styles.add(ParagraphStyle("HealthRed", parent=styles["Normal"],
        fontSize=14, textColor=RED, alignment=TA_CENTER))
    styles.add(ParagraphStyle("Action", parent=styles["Normal"],
        fontSize=10, textColor=HexColor("#333333"), spaceBefore=4))
    styles.add(ParagraphStyle("Footer", parent=styles["Normal"],
        fontSize=8, textColor=GRAY))

    doc = SimpleDocTemplate(
        str(output_path), pagesize=LETTER,
        leftMargin=1*inch, rightMargin=1*inch,
        topMargin=0.8*inch, bottomMargin=0.8*inch,
    )

    story = []

    # Title
    title = business_name or "Business"
    story.append(Paragraph(f"{title} — Financial Snapshot", styles["CardTitle"]))
    story.append(Paragraph(
        f"{pl.period_label} &nbsp;|&nbsp; {datetime.now().strftime('%Y-%m-%d')}",
        styles["CardSub"],
    ))
    story.append(HRFlowable(width="100%", thickness=2, color=HEADER_BG, spaceAfter=24))

    # 3 Big Numbers
    nums = [
        [
            Paragraph(_money(pl.net_revenue), styles["BigNum"]),
            Paragraph(_money(pl.gross_profit), styles["BigNum"]),
            Paragraph(_money(pl.net_profit), styles["BigNum"]),
        ],
        [
            Paragraph("Net Revenue", styles["BigLabel"]),
            Paragraph(f"Gross Profit ({int(pl.gross_margin_pct)}%)", styles["BigLabel"]),
            Paragraph(f"Net Profit ({int(pl.net_margin_pct)}%)", styles["BigLabel"]),
        ],
    ]
    t = Table(nums, colWidths=[2.1*inch]*3)
    t.setStyle(TableStyle([
        ("ALIGN", (0,0), (-1,-1), "CENTER"),
        ("VALIGN", (0,0), (-1,-1), "MIDDLE"),
        ("BOX", (0,0), (-1,-1), 1, LIGHT_GRAY),
        ("LINEBELOW", (0,0), (-1,0), 0.5, LIGHT_GRAY),
        ("TOPPADDING", (0,0), (-1,-1), 14),
        ("BOTTOMPADDING", (0,0), (-1,-1), 14),
    ]))
    story.append(t)
    story.append(Spacer(1, 24))

    # Health Score
    overall = "N/A"
    if scorecard:
        overall = scorecard.get("overall", "N/A")

    health_style = "HealthGreen"
    if overall in ("NEEDS ATTENTION",):
        health_style = "HealthRed"
    elif overall in ("ROOM FOR IMPROVEMENT",):
        health_style = "HealthYellow"

    story.append(Paragraph(f"Business Health: {overall}", styles[health_style]))
    story.append(Spacer(1, 20))

    # Key Metrics Table
    story.append(HRFlowable(width="100%", thickness=1, color=LIGHT_GRAY, spaceAfter=12))
    metrics_data = [
        ["Metric", "Value"],
        ["Gross Margin", f"{pl.gross_margin_pct:.1f}%"],
        ["Operating Margin", f"{pl.operating_margin_pct:.1f}%"],
        ["Net Margin", f"{pl.net_margin_pct:.1f}%"],
        ["COGS % of Revenue", f"{pl.cogs_pct:.1f}%"],
        ["Rent % of Revenue", f"{pl.rent_pct:.1f}%"],
        ["Total OPEX", _money(pl.total_opex)],
        ["Transactions", str(pl.transaction_count)],
        ["Flagged for Review", str(pl.flagged_count)],
    ]

    mt = Table(metrics_data, colWidths=[3.5*inch, 2.8*inch])
    mt.setStyle(TableStyle([
        ("BACKGROUND", (0,0), (-1,0), HEADER_BG),
        ("TEXTCOLOR", (0,0), (-1,0), WHITE),
        ("FONTNAME", (0,0), (-1,0), "Helvetica-Bold"),
        ("FONTSIZE", (0,0), (-1,-1), 10),
        ("ALIGN", (1,0), (1,-1), "RIGHT"),
        ("GRID", (0,0), (-1,-1), 0.5, LIGHT_GRAY),
        ("TOPPADDING", (0,0), (-1,-1), 6),
        ("BOTTOMPADDING", (0,0), (-1,-1), 6),
        ("LEFTPADDING", (0,0), (-1,-1), 10),
        ("RIGHTPADDING", (0,0), (-1,-1), 10),
    ]))
    story.append(mt)
    story.append(Spacer(1, 20))

    # Top Action Items
    recs = []
    if scorecard:
        for _m, data in scorecard.get("metrics", {}).items():
            if data.get("flag") in ("red", "yellow") and data.get("action"):
                recs.append(data["action"])

    if recs:
        story.append(HRFlowable(width="100%", thickness=1, color=LIGHT_GRAY, spaceAfter=12))
        story.append(Paragraph("TOP ACTION ITEMS", ParagraphStyle(
            "AH", fontSize=12, textColor=HEADER_BG, spaceBefore=4, spaceAfter=8,
        )))
        for i, rec in enumerate(recs[:3], 1):
            story.append(Paragraph(f"{i}. {rec}", styles["Action"]))

    # Footer
    story.append(Spacer(1, 30))
    story.append(HRFlowable(width="100%", thickness=1, color=LIGHT_GRAY, spaceAfter=8))
    story.append(Paragraph(
        "CONFIDENTIAL — 100% local processing. No data transmitted.",
        styles["Footer"],
    ))

    doc.build(story)
    return str(output_path)
