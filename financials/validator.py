"""
validator.py
============
Deep validation layer for P&L statements.
Catches math errors, unrealistic margins, and data quality issues
BEFORE they reach a client report.
"""

from decimal import Decimal
from typing import List, Dict
from .calculator import PLStatement, _cents


class PLValidator:
    """
    Run a full suite of checks on a PLStatement.
    Returns structured results — pass/fail with explanations.
    """

    def __init__(self, industry: str = "general"):
        self.industry = industry

    def run_all(self, pl: PLStatement) -> Dict:
        """Run every check and return a structured report."""
        checks = [
            self._check_accounting_equation(pl),
            self._check_revenue_sign(pl),
            self._check_margin_bounds(pl),
            self._check_cogs_ratio(pl),
            self._check_rent_ratio(pl),
            self._check_uncategorized(pl),
            self._check_flagged_ratio(pl),
            self._check_zero_revenue(pl),
        ]

        passed = [c for c in checks if c["status"] == "pass"]
        warned = [c for c in checks if c["status"] == "warn"]
        failed = [c for c in checks if c["status"] == "fail"]

        return {
            "total_checks": len(checks),
            "passed": len(passed),
            "warnings": len(warned),
            "failures": len(failed),
            "checks": checks,
            "overall": "FAIL" if failed else ("REVIEW" if warned else "PASS"),
        }

    # ── Individual checks ───────────────────────────────────────

    def _check_accounting_equation(self, pl: PLStatement) -> Dict:
        """Net Revenue - COGS - OPEX - Interest - Taxes must equal Net Profit."""
        recalc = _cents(
            pl.net_revenue - pl.total_cogs - pl.total_opex
            - pl.interest_expense - pl.taxes
        )
        ok = recalc == pl.net_profit
        return {
            "name": "Accounting Equation",
            "status": "pass" if ok else "fail",
            "detail": (
                "Equation balances"
                if ok
                else f"Recalculated ${recalc} ≠ reported ${pl.net_profit}"
            ),
        }

    def _check_revenue_sign(self, pl: PLStatement) -> Dict:
        """Gross revenue should never be negative."""
        ok = pl.gross_revenue >= 0
        return {
            "name": "Revenue Sign",
            "status": "pass" if ok else "fail",
            "detail": (
                "Revenue is non-negative"
                if ok
                else f"Negative revenue ${pl.gross_revenue} — likely misclassified debits"
            ),
        }

    def _check_margin_bounds(self, pl: PLStatement) -> Dict:
        """Margins should be between -100% and 100%."""
        gm = pl.gross_margin_pct
        if pl.net_revenue == 0:
            return {"name": "Margin Bounds", "status": "pass", "detail": "No revenue — skipped"}

        if gm > Decimal("95"):
            return {
                "name": "Margin Bounds",
                "status": "warn",
                "detail": f"Gross margin {gm}% is unusually high — verify COGS",
            }
        if gm < Decimal("-50"):
            return {
                "name": "Margin Bounds",
                "status": "warn",
                "detail": f"Gross margin {gm}% is deeply negative — verify revenue classification",
            }
        return {"name": "Margin Bounds", "status": "pass", "detail": f"Gross margin {gm}% within range"}

    def _check_cogs_ratio(self, pl: PLStatement) -> Dict:
        """COGS shouldn't exceed revenue (>100%)."""
        if pl.net_revenue == 0:
            return {"name": "COGS Ratio", "status": "pass", "detail": "No revenue — skipped"}
        if pl.cogs_pct > Decimal("100"):
            return {
                "name": "COGS Ratio",
                "status": "warn",
                "detail": f"COGS is {pl.cogs_pct}% of revenue — business is losing money on production",
            }
        return {"name": "COGS Ratio", "status": "pass", "detail": f"COGS {pl.cogs_pct}% of revenue"}

    def _check_rent_ratio(self, pl: PLStatement) -> Dict:
        """Rent over 15% of revenue is a red flag."""
        if pl.net_revenue == 0:
            return {"name": "Rent Ratio", "status": "pass", "detail": "No revenue — skipped"}
        if pl.rent_pct > Decimal("15"):
            return {
                "name": "Rent Ratio",
                "status": "warn",
                "detail": f"Rent is {pl.rent_pct}% of revenue — above 15% threshold",
            }
        return {"name": "Rent Ratio", "status": "pass", "detail": f"Rent {pl.rent_pct}% of revenue"}

    def _check_uncategorized(self, pl: PLStatement) -> Dict:
        """Flag if uncategorized amounts are significant."""
        total_uncat = pl.uncategorized_income + pl.uncategorized_expense
        if total_uncat == 0:
            return {"name": "Uncategorized", "status": "pass", "detail": "All transactions categorized"}

        if pl.net_revenue > 0:
            pct = _cents((total_uncat / pl.net_revenue) * 100)
            if pct > Decimal("10"):
                return {
                    "name": "Uncategorized",
                    "status": "warn",
                    "detail": f"${total_uncat} uncategorized ({pct}% of revenue) — needs review",
                }
        return {
            "name": "Uncategorized",
            "status": "pass",
            "detail": f"${total_uncat} uncategorized — minor",
        }

    def _check_flagged_ratio(self, pl: PLStatement) -> Dict:
        """If > 20% of transactions are flagged, data quality is low."""
        if pl.transaction_count == 0:
            return {"name": "Flagged Ratio", "status": "pass", "detail": "No transactions"}
        pct = round(pl.flagged_count / pl.transaction_count * 100)
        if pct > 20:
            return {
                "name": "Flagged Ratio",
                "status": "warn",
                "detail": f"{pct}% of transactions flagged — consider tuning categories.json",
            }
        return {"name": "Flagged Ratio", "status": "pass", "detail": f"{pct}% flagged — acceptable"}

    def _check_zero_revenue(self, pl: PLStatement) -> Dict:
        """Zero revenue with expenses is suspicious."""
        if pl.net_revenue == 0 and pl.total_opex > 0:
            return {
                "name": "Zero Revenue",
                "status": "warn",
                "detail": f"Zero revenue but ${pl.total_opex} in expenses — "
                          f"check if income deposits were misclassified",
            }
        return {"name": "Zero Revenue", "status": "pass", "detail": "Revenue present"}
