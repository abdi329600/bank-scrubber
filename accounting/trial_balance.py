"""
trial_balance.py
================
Generates a trial balance from journal entries.
Total Debits MUST equal Total Credits — fundamental accounting check.
"""

from collections import defaultdict
from decimal import Decimal, ROUND_HALF_UP
from typing import List, Dict, Tuple

from .journal_entry import JournalEntry

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from categorization.chart_of_accounts import CHART_OF_ACCOUNTS, get_account


def _cents(v) -> Decimal:
    return Decimal(str(v)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


class TrialBalanceGenerator:
    """
    Aggregates journal entries into account-level debit/credit totals.
    Produces a trial balance that must balance.
    """

    def generate(self, entries: List[JournalEntry]) -> Dict:
        accounts: Dict[str, Dict] = {}

        for je in entries:
            for line in je.lines:
                code = line.account
                if code not in accounts:
                    acct = get_account(code)
                    accounts[code] = {
                        "code": code,
                        "name": line.account_name or (acct.name if acct else "Unknown"),
                        "type": acct.account_type if acct else "UNKNOWN",
                        "normal_balance": acct.normal_balance if acct else "DEBIT",
                        "total_debit": Decimal("0"),
                        "total_credit": Decimal("0"),
                    }
                accounts[code]["total_debit"] += line.debit
                accounts[code]["total_credit"] += line.credit

        # Calculate net balance for each account
        rows = []
        for code in sorted(accounts.keys()):
            a = accounts[code]
            net = _cents(a["total_debit"] - a["total_credit"])
            a["net_balance"] = net
            a["total_debit"] = _cents(a["total_debit"])
            a["total_credit"] = _cents(a["total_credit"])
            # Display in normal balance direction
            if a["normal_balance"] == "DEBIT":
                a["balance_debit"] = net if net >= 0 else Decimal("0")
                a["balance_credit"] = abs(net) if net < 0 else Decimal("0")
            else:
                a["balance_credit"] = abs(net) if net <= 0 else Decimal("0")
                a["balance_debit"] = net if net > 0 else Decimal("0")
            rows.append(a)

        total_debits = _cents(sum(r["total_debit"] for r in rows))
        total_credits = _cents(sum(r["total_credit"] for r in rows))
        is_balanced = total_debits == total_credits

        # Group by account type
        by_type: Dict[str, List] = defaultdict(list)
        for r in rows:
            by_type[r["type"]].append(r)

        return {
            "accounts": rows,
            "by_type": dict(by_type),
            "total_debits": float(total_debits),
            "total_credits": float(total_credits),
            "is_balanced": is_balanced,
            "difference": float(_cents(total_debits - total_credits)),
            "account_count": len(rows),
        }

    def generate_summary(self, tb: Dict) -> List[str]:
        """Human-readable trial balance lines."""
        lines = [
            "=" * 70,
            f"{'TRIAL BALANCE':^70}",
            "=" * 70,
            f"{'Account':<8} {'Name':<35} {'Debit':>12} {'Credit':>12}",
            "-" * 70,
        ]
        for row in tb["accounts"]:
            dr = f"${float(row['total_debit']):,.2f}" if row["total_debit"] else ""
            cr = f"${float(row['total_credit']):,.2f}" if row["total_credit"] else ""
            lines.append(
                f"{row['code']:<8} {row['name']:<35} {dr:>12} {cr:>12}"
            )
        lines.append("-" * 70)
        lines.append(
            f"{'TOTALS':<44} "
            f"${tb['total_debits']:>11,.2f} ${tb['total_credits']:>11,.2f}"
        )
        if tb["is_balanced"]:
            lines.append("BALANCED ✓")
        else:
            lines.append(f"*** OUT OF BALANCE by ${tb['difference']:,.2f} ***")
        lines.append("=" * 70)
        return lines
