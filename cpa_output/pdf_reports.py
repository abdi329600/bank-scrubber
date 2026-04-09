"""
pdf_reports.py — Professional CPA-grade PDF report generation.
Generates P&L, Trial Balance, Flagged Items, and Schedule C PDFs.
100% local — zero network calls.
"""

from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional

from reportlab.lib.pagesizes import LETTER
from reportlab.lib.units import inch
from reportlab.lib.colors import HexColor
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_LEFT, TA_CENTER, TA_RIGHT
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
    HRFlowable, PageBreak,
)

HEADER_BG = HexColor("#1a1a2e")
ACCENT = HexColor("#e94560")
WHITE = HexColor("#ffffff")
BLACK = HexColor("#000000")
GRAY = HexColor("#666666")
LIGHT_GRAY = HexColor("#cccccc")
GREEN = HexColor("#28a745")
RED = HexColor("#dc3545")
YELLOW_BG = HexColor("#fff8e1")
RED_BG = HexColor("#fff0f0")
GREEN_BG = HexColor("#f0fff0")
ROW_ALT = HexColor("#f5f5f5")


def _money(val) -> str:
    v = float(val)
    return f"-${abs(v):,.2f}" if v < 0 else f"${v:,.2f}"


def _styles():
    s = getSampleStyleSheet()
    s.add(ParagraphStyle("Title2", parent=s["Title"],
        fontSize=20, textColor=HEADER_BG, spaceAfter=4))
    s.add(ParagraphStyle("Sub", parent=s["Normal"],
        fontSize=10, textColor=GRAY, spaceAfter=12))
    s.add(ParagraphStyle("Section", parent=s["Heading2"],
        fontSize=13, textColor=HEADER_BG, spaceBefore=16, spaceAfter=6))
    s.add(ParagraphStyle("Body", parent=s["Normal"],
        fontSize=9, textColor=BLACK))
    s.add(ParagraphStyle("Small", parent=s["Normal"],
        fontSize=8, textColor=GRAY))
    return s


class CPAPDFGenerator:
    """Generates the full multi-page CPA PDF package."""

    def generate(
        self,
        package: Dict,
        output_path: str = "output/cpa_report.pdf",
        business_name: str = "",
    ) -> str:
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        styles = _styles()

        doc = SimpleDocTemplate(
            str(output_path), pagesize=LETTER,
            leftMargin=0.6 * inch, rightMargin=0.6 * inch,
            topMargin=0.5 * inch, bottomMargin=0.5 * inch,
        )
        story = []

        cover = package.get("cover_sheet", {})
        name = business_name or cover.get("business_name", "Client")
        period = cover.get("period", "")

        # ═══ COVER PAGE ═══
        story.extend(self._cover_page(styles, cover, name, period))

        # ═══ P&L ═══
        story.append(PageBreak())
        story.extend(self._pnl_page(styles, package.get("profit_and_loss", {}), period))

        # ═══ TRIAL BALANCE ═══
        story.append(PageBreak())
        story.extend(self._tb_page(styles, package.get("trial_balance", {})))

        # ═══ SCHEDULE C ═══
        story.append(PageBreak())
        story.extend(self._schedule_c_page(styles, package.get("schedule_c_map", {})))

        # ═══ FLAGGED ITEMS ═══
        story.append(PageBreak())
        story.extend(self._flags_page(styles, package.get("flagged_items_report", {})))

        # ═══ CATEGORY SUMMARY ═══
        story.append(PageBreak())
        story.extend(self._category_page(styles, package.get("category_summary", {})))

        # Footer
        story.append(Spacer(1, 20))
        story.append(HRFlowable(width="100%", thickness=1, color=LIGHT_GRAY))
        story.append(Paragraph(
            "CONFIDENTIAL — Generated locally. No data transmitted.",
            styles["Small"],
        ))

        doc.build(story)
        return str(output_path)

    # ── Cover ───────────────────────────────────────────────────

    def _cover_page(self, s, cover, name, period):
        els = []
        els.append(Spacer(1, 60))
        els.append(Paragraph("CPA WORKPAPER PACKAGE", s["Title2"]))
        els.append(Paragraph(
            f"{name} &nbsp;|&nbsp; {period} &nbsp;|&nbsp; "
            f"Generated {datetime.now().strftime('%Y-%m-%d')}",
            s["Sub"],
        ))
        els.append(HRFlowable(width="100%", thickness=2, color=HEADER_BG, spaceAfter=20))

        data = [
            ["Field", "Value"],
            ["Business Name", name],
            ["Period", period],
            ["Source Document", cover.get("source_document", "")],
            ["Document Type", cover.get("document_type", "")],
            ["Transactions", str(cover.get("transaction_count", 0))],
            ["Total Debits", _money(cover.get("total_debits", 0))],
            ["Total Credits", _money(cover.get("total_credits", 0))],
            ["Trial Balance", cover.get("trial_balance_status", "")],
            ["Flagged Items", str(cover.get("flagged_items", 0))],
            ["Critical Flags", str(cover.get("critical_flags", 0))],
        ]
        t = Table(data, colWidths=[2.5 * inch, 4 * inch])
        t.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), HEADER_BG),
            ("TEXTCOLOR", (0, 0), (-1, 0), WHITE),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, -1), 10),
            ("GRID", (0, 0), (-1, -1), 0.5, LIGHT_GRAY),
            ("TOPPADDING", (0, 0), (-1, -1), 6),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
            ("LEFTPADDING", (0, 0), (-1, -1), 10),
        ]))
        els.append(t)
        return els

    # ── P&L ─────────────────────────────────────────────────────

    def _pnl_page(self, s, pnl, period):
        els = []
        els.append(Paragraph("PROFIT &amp; LOSS STATEMENT", s["Title2"]))
        els.append(Paragraph(period, s["Sub"]))
        els.append(HRFlowable(width="100%", thickness=1, color=LIGHT_GRAY, spaceAfter=10))

        rows = [["", "Amount"]]
        rows.append(["REVENUE", ""])
        for line in pnl.get("revenue", {}).get("lines", []):
            rows.append([f"  {line['code']}  {line['name']}", _money(line["amount"])])
        rows.append(["  TOTAL REVENUE", _money(pnl.get("revenue", {}).get("total", 0))])
        rows.append(["", ""])

        rows.append(["COST OF GOODS SOLD", ""])
        for line in pnl.get("cogs", {}).get("lines", []):
            rows.append([f"  {line['code']}  {line['name']}", _money(line["amount"])])
        rows.append(["  TOTAL COGS", _money(pnl.get("cogs", {}).get("total", 0))])
        rows.append(["", ""])

        rows.append(["GROSS PROFIT", _money(pnl.get("gross_profit", 0))])
        rows.append(["GROSS MARGIN", f"{pnl.get('gross_margin_pct', 0)}%"])
        rows.append(["", ""])

        rows.append(["OPERATING EXPENSES", ""])
        for line in pnl.get("operating_expenses", {}).get("lines", []):
            rows.append([f"  {line['code']}  {line['name']}", _money(line["amount"])])
        rows.append(["  TOTAL OPEX", _money(pnl.get("operating_expenses", {}).get("total", 0))])
        rows.append(["", ""])
        rows.append(["NET INCOME (Before Tax)", _money(pnl.get("net_income", 0))])

        t = Table(rows, colWidths=[4.5 * inch, 2 * inch])
        style = [
            ("BACKGROUND", (0, 0), (-1, 0), HEADER_BG),
            ("TEXTCOLOR", (0, 0), (-1, 0), WHITE),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, -1), 9),
            ("ALIGN", (1, 0), (1, -1), "RIGHT"),
            ("GRID", (0, 0), (-1, -1), 0.3, LIGHT_GRAY),
            ("TOPPADDING", (0, 0), (-1, -1), 3),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
            ("BACKGROUND", (0, -1), (-1, -1), HexColor("#e8e8e8")),
            ("FONTNAME", (0, -1), (-1, -1), "Helvetica-Bold"),
        ]
        t.setStyle(TableStyle(style))
        els.append(t)
        return els

    # ── Trial Balance ───────────────────────────────────────────

    def _tb_page(self, s, tb):
        els = []
        els.append(Paragraph("TRIAL BALANCE", s["Title2"]))
        els.append(HRFlowable(width="100%", thickness=1, color=LIGHT_GRAY, spaceAfter=10))

        rows = [["Account", "Name", "Debit", "Credit"]]
        for acct in tb.get("accounts", []):
            dr = _money(acct["total_debit"]) if float(acct["total_debit"]) else ""
            cr = _money(acct["total_credit"]) if float(acct["total_credit"]) else ""
            rows.append([acct["code"], acct["name"], dr, cr])
        rows.append(["", "TOTALS", _money(tb.get("total_debits", 0)),
                      _money(tb.get("total_credits", 0))])

        t = Table(rows, colWidths=[0.8 * inch, 3.2 * inch, 1.3 * inch, 1.3 * inch])
        style = [
            ("BACKGROUND", (0, 0), (-1, 0), HEADER_BG),
            ("TEXTCOLOR", (0, 0), (-1, 0), WHITE),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, -1), 8),
            ("ALIGN", (2, 0), (-1, -1), "RIGHT"),
            ("GRID", (0, 0), (-1, -1), 0.3, LIGHT_GRAY),
            ("TOPPADDING", (0, 0), (-1, -1), 3),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
            ("BACKGROUND", (0, -1), (-1, -1), HexColor("#e8e8e8")),
            ("FONTNAME", (0, -1), (-1, -1), "Helvetica-Bold"),
        ]
        t.setStyle(TableStyle(style))
        els.append(t)

        status = "BALANCED" if tb.get("is_balanced") else "OUT OF BALANCE"
        color = GREEN if tb.get("is_balanced") else RED
        els.append(Spacer(1, 8))
        els.append(Paragraph(
            f"<font color='{color}'>{status}</font>",
            ParagraphStyle("tb_status", fontSize=12, textColor=color),
        ))
        return els

    # ── Schedule C ──────────────────────────────────────────────

    def _schedule_c_page(self, s, sc):
        els = []
        els.append(Paragraph("IRS SCHEDULE C MAPPING", s["Title2"]))
        els.append(HRFlowable(width="100%", thickness=1, color=LIGHT_GRAY, spaceAfter=10))

        rows = [["Schedule C Line", "Amount", "Txns"]]
        for line_name, data in sc.get("lines", {}).items():
            rows.append([line_name, _money(data["total"]),
                         str(data["transaction_count"])])

        if len(rows) > 1:
            t = Table(rows, colWidths=[3.5 * inch, 1.5 * inch, 0.8 * inch])
            t.setStyle(TableStyle([
                ("BACKGROUND", (0, 0), (-1, 0), HEADER_BG),
                ("TEXTCOLOR", (0, 0), (-1, 0), WHITE),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, -1), 9),
                ("ALIGN", (1, 0), (-1, -1), "RIGHT"),
                ("GRID", (0, 0), (-1, -1), 0.3, LIGHT_GRAY),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ]))
            els.append(t)

        summary = sc.get("summary", {})
        if summary:
            els.append(Spacer(1, 12))
            els.append(Paragraph("SCHEDULE C SUMMARY", s["Section"]))
            srows = [
                ["Gross Receipts (Line 1)", _money(summary.get("gross_receipts", 0))],
                ["Less: COGS (Line 4)", _money(summary.get("cogs", 0))],
                ["Gross Profit (Line 7)", _money(summary.get("gross_profit", 0))],
                ["Total Expenses", _money(summary.get("total_expenses", 0))],
                ["NET PROFIT (Line 31)", _money(summary.get("net_profit", 0))],
            ]
            st = Table(srows, colWidths=[3.5 * inch, 2 * inch])
            st.setStyle(TableStyle([
                ("FONTSIZE", (0, 0), (-1, -1), 10),
                ("ALIGN", (1, 0), (1, -1), "RIGHT"),
                ("FONTNAME", (0, -1), (-1, -1), "Helvetica-Bold"),
                ("LINEABOVE", (0, -1), (-1, -1), 1, BLACK),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ]))
            els.append(st)
        return els

    # ── Flagged Items ───────────────────────────────────────────

    def _flags_page(self, s, flags):
        els = []
        els.append(Paragraph("FLAGGED ITEMS — CPA REVIEW REQUIRED", s["Title2"]))
        els.append(HRFlowable(width="100%", thickness=1, color=LIGHT_GRAY, spaceAfter=10))

        by_sev = flags.get("by_severity", {})
        els.append(Paragraph(
            f"Critical: {by_sev.get('CRITICAL', 0)} | "
            f"High: {by_sev.get('HIGH', 0)} | "
            f"Medium: {by_sev.get('MEDIUM', 0)} | "
            f"Low: {by_sev.get('LOW', 0)}",
            s["Body"],
        ))
        els.append(Spacer(1, 10))

        flagged = flags.get("flagged_list", [])
        if flagged:
            rows = [["Date", "Description", "Amount", "Flags"]]
            for t in flagged[:50]:
                desc = t.description[:35] if isinstance(t, object) and hasattr(t, 'description') else str(t)[:35]
                date = t.date if hasattr(t, 'date') else ""
                amt = _money(t.amount) if hasattr(t, 'amount') else ""
                fl = ", ".join(t.flags) if hasattr(t, 'flags') else ""
                rows.append([date, desc, amt, fl[:40]])

            t = Table(rows, colWidths=[0.9 * inch, 2.3 * inch, 1.1 * inch, 2.3 * inch])
            t.setStyle(TableStyle([
                ("BACKGROUND", (0, 0), (-1, 0), HEADER_BG),
                ("TEXTCOLOR", (0, 0), (-1, 0), WHITE),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, -1), 8),
                ("ALIGN", (2, 0), (2, -1), "RIGHT"),
                ("GRID", (0, 0), (-1, -1), 0.3, LIGHT_GRAY),
                ("TOPPADDING", (0, 0), (-1, -1), 3),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
            ]))
            els.append(t)
        else:
            els.append(Paragraph("No flagged items.", s["Body"]))
        return els

    # ── Category Summary ────────────────────────────────────────

    def _category_page(self, s, cats):
        els = []
        els.append(Paragraph("CATEGORY SUMMARY", s["Title2"]))
        els.append(HRFlowable(width="100%", thickness=1, color=LIGHT_GRAY, spaceAfter=10))

        rows = [["Category", "Account", "Count", "Total"]]
        for name, data in cats.items():
            rows.append([
                name, data.get("account", ""),
                str(data.get("count", 0)), _money(data.get("total", 0)),
            ])

        if len(rows) > 1:
            t = Table(rows, colWidths=[3 * inch, 0.8 * inch, 0.7 * inch, 1.5 * inch])
            t.setStyle(TableStyle([
                ("BACKGROUND", (0, 0), (-1, 0), HEADER_BG),
                ("TEXTCOLOR", (0, 0), (-1, 0), WHITE),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, -1), 9),
                ("ALIGN", (2, 0), (-1, -1), "RIGHT"),
                ("GRID", (0, 0), (-1, -1), 0.3, LIGHT_GRAY),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [WHITE, ROW_ALT]),
            ]))
            els.append(t)
        return els
