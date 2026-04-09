"""
reconciliation.py
=================
Bank reconciliation stoplight gate.
Purpose: explain differences between the bank's record and the computed ledger.

Stoplight:
  GREEN  — Reconciles exactly (difference == 0)
  YELLOW — Difference <= $0.10 tolerance (rounding) OR balances not provided
  RED    — Does not reconcile → analysis cannot be marked "full"

A reconciliation gate is the hard prerequisite before trusting totals.
"""

from decimal import Decimal, ROUND_HALF_UP
from typing import Dict, List, Optional
from dataclasses import dataclass, field


def _cents(v) -> Decimal:
    return Decimal(str(v)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


TOLERANCE = Decimal("0.10")


@dataclass
class ReconciliationResult:
    status: str = "YELLOW"          # GREEN / YELLOW / RED
    beginning_balance: Optional[str] = None
    ending_balance_stated: Optional[str] = None
    ending_balance_computed: Optional[str] = None
    total_credits: str = "0.00"
    total_debits: str = "0.00"
    net_change: str = "0.00"
    difference: Optional[str] = None
    balances_provided: bool = False
    issues: List[str] = field(default_factory=list)
    recommendations: List[str] = field(default_factory=list)


class ReconciliationEngine:
    """
    Performs bank reconciliation as a stoplight gate.
    Must pass before a "Full Analysis" can be issued.
    """

    def reconcile(self, batch) -> ReconciliationResult:
        """Run reconciliation checks on a TransactionBatch."""
        result = ReconciliationResult()

        total_cr = batch.total_credits
        total_dr = batch.total_debits
        net = batch.net_change

        result.total_credits = str(total_cr)
        result.total_debits = str(total_dr)
        result.net_change = str(net)

        bb = batch.beginning_balance
        eb = batch.ending_balance

        if bb is not None:
            result.beginning_balance = str(bb)
        if eb is not None:
            result.ending_balance_stated = str(eb)

        # ── Check 1: Are statement balances provided? ────────────
        if bb is None or eb is None:
            result.balances_provided = False
            result.status = "YELLOW"
            result.issues.append(
                "Statement beginning/ending balances not provided. "
                "Cannot verify completeness of imported transactions."
            )
            result.recommendations.append(
                "Provide statement summary page with beginning and ending balances "
                "for full reconciliation."
            )
            return result

        result.balances_provided = True

        # ── Check 2: Beginning + net change = ending? ────────────
        computed_ending = _cents(bb + net)
        result.ending_balance_computed = str(computed_ending)
        diff = _cents(computed_ending - eb)
        result.difference = str(diff)
        abs_diff = abs(diff)

        if abs_diff == Decimal("0"):
            result.status = "GREEN"
        elif abs_diff <= TOLERANCE:
            result.status = "YELLOW"
            result.issues.append(
                f"Minor difference of ${abs_diff} (within ${TOLERANCE} tolerance). "
                f"Likely rounding or pending transaction."
            )
        else:
            result.status = "RED"
            result.issues.append(
                f"Reconciliation failed: difference of ${abs_diff}. "
                f"Computed ending: ${computed_ending}, stated ending: ${eb}."
            )

            # ── Diagnose possible causes ─────────────────────────
            if diff > 0:
                result.recommendations.append(
                    f"Computed ending exceeds stated by ${abs_diff}. "
                    "Possible causes: duplicate transactions imported, "
                    "or credits (deposits) included that don't belong to this period."
                )
            else:
                result.recommendations.append(
                    f"Computed ending is less than stated by ${abs_diff}. "
                    "Possible causes: missing transactions, "
                    "debits not captured, or wrong date range."
                )

            result.recommendations.append(
                "Verify: (1) date range matches statement period exactly, "
                "(2) no transactions were excluded by parsing, "
                "(3) no duplicate imports from overlapping files."
            )

        # ── Check 3: Transaction-level sanity ────────────────────
        txn_count = batch.count
        if txn_count == 0:
            result.status = "RED"
            result.issues.append("No transactions found in batch.")

        # Check for possible duplicates
        seen = {}
        dup_count = 0
        for t in batch.transactions:
            key = f"{t.date}|{t.amount}|{t.direction}|{t.description[:20]}"
            seen[key] = seen.get(key, 0) + 1
            if seen[key] > 1:
                dup_count += 1
        if dup_count > 0:
            result.issues.append(
                f"{dup_count} possible duplicate transaction(s) detected. "
                "This may cause reconciliation mismatch."
            )

        return result

    def can_issue_full_analysis(self, result: ReconciliationResult) -> bool:
        """Only GREEN or YELLOW allows a Full Analysis to be issued."""
        return result.status in ("GREEN", "YELLOW")

    def format_report(self, result: ReconciliationResult) -> List[str]:
        """Human-readable reconciliation report lines."""
        lines = [
            "=" * 65,
            f"{'BANK RECONCILIATION':^65}",
            "=" * 65,
        ]

        status_icon = {"GREEN": "GREEN PASS", "YELLOW": "YELLOW WARN", "RED": "RED FAIL"}
        lines.append(f"  Status: {status_icon.get(result.status, result.status)}")
        lines.append("")

        if result.beginning_balance:
            lines.append(f"  Beginning Balance:        ${result.beginning_balance}")
        lines.append(f"  Total Credits (deposits): ${result.total_credits}")
        lines.append(f"  Total Debits (payments):  ${result.total_debits}")
        lines.append(f"  Net Change:               ${result.net_change}")

        if result.ending_balance_computed:
            lines.append(f"  Computed Ending Balance:  ${result.ending_balance_computed}")
        if result.ending_balance_stated:
            lines.append(f"  Stated Ending Balance:    ${result.ending_balance_stated}")
        if result.difference:
            lines.append(f"  Difference:               ${result.difference}")

        if result.issues:
            lines.append("")
            lines.append("  ISSUES:")
            for issue in result.issues:
                lines.append(f"    - {issue}")

        if result.recommendations:
            lines.append("")
            lines.append("  RECOMMENDATIONS:")
            for rec in result.recommendations:
                lines.append(f"    - {rec}")

        lines.append("=" * 65)
        return lines
