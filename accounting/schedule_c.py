"""
schedule_c.py — IRS Schedule C line mapping.
Maps CoA account codes to Schedule C line numbers for tax prep.
"""

from collections import defaultdict
from decimal import Decimal, ROUND_HALF_UP
from typing import List, Dict

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from engine.transaction import Transaction


def _cents(v) -> Decimal:
    return Decimal(str(v)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


SCHEDULE_C_MAPPING: Dict[str, List[str]] = {
    "Line 1  - Gross Receipts":       ["4000", "4100", "4200", "4300"],
    "Line 4  - COGS":                 ["5000", "5100", "5110", "5120", "5130", "5140"],
    "Line 6  - Other Income":         ["4500", "4510", "4520", "4900"],
    "Line 8  - Advertising":          ["6450"],
    "Line 9  - Car & Truck":          ["6120", "6125"],
    "Line 10 - Commissions":          ["6310"],
    "Line 11 - Contract Labor":       ["6020"],
    "Line 13 - Depreciation":         ["6600"],
    "Line 14 - Employee Benefits":    ["6210"],
    "Line 15 - Insurance":            ["6130", "6200"],
    "Line 16 - Interest":             ["6700"],
    "Line 17 - Legal & Professional": ["6500"],
    "Line 18 - Shipping & Postage":   ["6360"],
    "Line 20 - Rent/Lease":           ["6100"],
    "Line 22 - Supplies":             ["6350"],
    "Line 23 - Taxes & Licenses":     ["6510"],
    "Line 24a - Travel":              ["6140"],
    "Line 24b - Meals (50%)":         ["6150"],
    "Line 25 - Utilities":            ["6110"],
    "Line 26 - Wages":                ["6000"],
    "Line 27 - Other Expenses":       ["6010", "6300", "6400", "6410", "6800", "6900"],
}


class ScheduleCMapper:
    """Maps categorized transactions to IRS Schedule C lines."""

    def map_transactions(self, txns: List[Transaction]) -> Dict:
        """Group transactions by Schedule C line and total them."""
        # Build reverse lookup: account_code → line
        reverse: Dict[str, str] = {}
        for line, codes in SCHEDULE_C_MAPPING.items():
            for code in codes:
                reverse[code] = line

        line_totals: Dict[str, Decimal] = defaultdict(lambda: Decimal("0"))
        line_items: Dict[str, List] = defaultdict(list)
        unmapped = []

        for txn in txns:
            code = txn.account_code
            sc_line = reverse.get(code, "")
            if sc_line:
                line_totals[sc_line] += txn.amount
                line_items[sc_line].append({
                    "date": txn.date,
                    "description": txn.description,
                    "amount": str(_cents(txn.amount)),
                    "account": code,
                })
            else:
                unmapped.append(txn)

        result = {
            "lines": {},
            "unmapped_count": len(unmapped),
        }
        for line in SCHEDULE_C_MAPPING:
            total = _cents(line_totals.get(line, Decimal("0")))
            if total != 0 or line_items.get(line):
                result["lines"][line] = {
                    "total": str(total),
                    "transaction_count": len(line_items.get(line, [])),
                    "transactions": line_items.get(line, []),
                }

        # Compute Schedule C summary
        gross = _cents(line_totals.get("Line 1  - Gross Receipts", Decimal("0")))
        cogs = _cents(line_totals.get("Line 4  - COGS", Decimal("0")))
        other_inc = _cents(line_totals.get("Line 6  - Other Income", Decimal("0")))
        gross_profit = _cents(gross - cogs)
        total_income = _cents(gross_profit + other_inc)

        total_expenses = Decimal("0")
        expense_lines = [k for k in SCHEDULE_C_MAPPING if k.startswith("Line") and
                         k not in ("Line 1  - Gross Receipts", "Line 4  - COGS",
                                   "Line 6  - Other Income")]
        for el in expense_lines:
            total_expenses += line_totals.get(el, Decimal("0"))
        total_expenses = _cents(total_expenses)

        net_profit = _cents(total_income - total_expenses)

        result["summary"] = {
            "gross_receipts": str(gross),
            "cogs": str(cogs),
            "gross_profit": str(gross_profit),
            "other_income": str(other_inc),
            "total_income": str(total_income),
            "total_expenses": str(total_expenses),
            "net_profit": str(net_profit),
        }
        return result

    def generate_text(self, mapping: Dict) -> List[str]:
        """Formatted Schedule C text output."""
        def _fmt(val) -> str:
            """Format a str or Decimal amount for display."""
            d = Decimal(str(val)) if val else Decimal("0")
            return f"{d:>10,.2f}"

        lines = [
            "=" * 65,
            f"{'SCHEDULE C MAPPING':^65}",
            "=" * 65,
        ]
        for line_name, data in mapping.get("lines", {}).items():
            total = data["total"]
            count = data["transaction_count"]
            lines.append(f"  {line_name:<40} ${_fmt(total)}  ({count} txns)")
        lines.append("-" * 65)
        s = mapping.get("summary", {})
        lines.append(f"  {'Gross Receipts':<40} ${_fmt(s.get('gross_receipts', '0'))}")
        lines.append(f"  {'Less: COGS':<40} ${_fmt(s.get('cogs', '0'))}")
        lines.append(f"  {'Gross Profit':<40} ${_fmt(s.get('gross_profit', '0'))}")
        lines.append(f"  {'Total Expenses':<40} ${_fmt(s.get('total_expenses', '0'))}")
        lines.append(f"  {'NET PROFIT (Line 31)':<40} ${_fmt(s.get('net_profit', '0'))}")
        lines.append("=" * 65)
        return lines
