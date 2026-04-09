"""
pl_builder.py
=============
Takes categorized transactions and assembles a verified
PLStatement. This is the bridge between raw data and the
math core.
"""

from decimal import Decimal
from typing import List, Dict
from .calculator import PLStatement, _cents, q_money, D
from .categorizer import Transaction


class PLBuilder:
    """
    Takes categorized Transaction objects.
    Builds a verified P&L statement.
    """

    # Map subcategory → PLStatement field for OPEX items
    OPEX_FIELD_MAP = {
        "rent":                  "rent",
        "utilities":             "utilities",
        "insurance":             "insurance",
        "marketing":             "marketing",
        "software":              "software",
        "bank_fees":             "bank_fees",
        "vehicle":               "other_opex",
        "office":                "other_opex",
        "meals_entertainment":   "other_opex",
        "professional_services": "other_opex",
        "other_opex":            "other_opex",
    }

    def build(
        self,
        transactions: List[Transaction],
        period_label: str,
        basis_label: str = "cash_basis_from_bank_activity",
    ) -> PLStatement:
        """Build a single-period P&L from categorized transactions."""

        pl = PLStatement(period_label=period_label, basis_label=basis_label)
        pl.transaction_count = len(transactions)
        pl.flagged_count = sum(1 for t in transactions if t.confidence == "flagged")

        for t in transactions:
            amount = Decimal(str(abs(t.amount)))
            cat = t.category or ""
            sub = t.subcategory or ""

            # ── SKIP TRANSFERS ──
            if cat == "transfer":
                continue

            # ── REVENUE ──
            if cat == "revenue":
                if sub == "uncategorized_income":
                    pl.uncategorized_income += amount
                pl.gross_revenue += amount

            # ── REFUNDS OUT ──
            elif cat == "refund_out":
                pl.refunds += amount

            # ── COGS ──
            elif cat == "cogs":
                if sub == "inventory":
                    pl.inventory_costs += amount
                elif sub == "direct_labor":
                    pl.direct_labor += amount
                else:
                    pl.inventory_costs += amount  # default COGS bucket

            # ── OPEX ──
            elif cat == "opex":
                field_name = self.OPEX_FIELD_MAP.get(sub, "other_opex")
                if sub == "other_opex" or sub not in self.OPEX_FIELD_MAP:
                    pl.uncategorized_expense += amount
                current = getattr(pl, field_name)
                setattr(pl, field_name, current + amount)

            # ── DEBT SERVICE (interest only hits P&L) ──
            elif cat == "debt":
                pl.interest_expense += amount

            # ── ANYTHING ELSE → other_opex ──
            else:
                pl.other_opex += amount
                pl.uncategorized_expense += amount

        # Disclosure assumptions
        pl.assumptions.append("P&L derived from bank-statement categorization (cash basis).")
        pl.assumptions.append("COGS is bank-proxy only; no inventory adjustments applied.")
        if pl.interest_expense > 0:
            pl.assumptions.append("Loan interest routed to expense; principal excluded from P&L.")

        return pl

    def build_multi_period(
        self,
        periods: Dict[str, List[Transaction]],
    ) -> List[PLStatement]:
        """Build P&L for each period. Dict keys are period labels."""
        return [
            self.build(txns, label)
            for label, txns in periods.items()
        ]

    def compare_periods(
        self,
        statements: List[PLStatement],
    ) -> List[Dict]:
        """
        Month-over-month comparison.
        Shows growth or decline for key metrics.
        """
        if len(statements) < 2:
            return []

        comparisons = []
        for i in range(1, len(statements)):
            prev = statements[i - 1]
            curr = statements[i]

            def pct_change(current: Decimal, previous: Decimal) -> Decimal:
                if previous == 0:
                    return Decimal("0")
                return _cents(((current - previous) / previous) * 100)

            comparisons.append({
                "from": prev.period_label,
                "to": curr.period_label,
                "revenue_change_pct": str(pct_change(
                    curr.net_revenue, prev.net_revenue
                )),
                "profit_change_pct": str(pct_change(
                    curr.net_profit, prev.net_profit
                )),
                "margin_change": str(
                    curr.net_margin_pct - prev.net_margin_pct
                ),
                "cogs_change_pct": str(pct_change(
                    curr.total_cogs, prev.total_cogs
                )),
                "opex_change_pct": str(pct_change(
                    curr.total_opex, prev.total_opex
                )),
            })

        return comparisons
