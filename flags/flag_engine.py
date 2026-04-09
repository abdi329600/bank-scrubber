"""
flag_engine.py
==============
All flag rules: mathematical, tax/IRS, confidence, and business structure.
Flags get escalated to the CPA for human review.
"""

from decimal import Decimal
from typing import List, Dict
from collections import defaultdict

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from engine.transaction import Transaction, TransactionBatch


FLAG_RULES: Dict[str, Dict] = {
    # ── MATHEMATICAL FLAGS ──────────────────────────────────────
    "BALANCE_MISMATCH": {
        "severity": "CRITICAL",
        "message": "Bank statement math does not reconcile. "
                   "Possible missing transactions or extraction error.",
    },
    "DUPLICATE_TRANSACTION": {
        "severity": "HIGH",
        "message": "Potential duplicate — same date + amount + merchant within 48h.",
    },
    # ── TAX / IRS FLAGS ─────────────────────────────────────────
    "MEALS_OVER_75": {
        "severity": "MEDIUM",
        "message": "IRS requires documentation for meals > $75. "
                   "CPA needs: who, business purpose, where, when.",
        "irs_ref": "IRC Section 274(d)",
    },
    "LARGE_CASH_WITHDRAWAL": {
        "severity": "MEDIUM",
        "message": "Cash > $500 requires business purpose documentation.",
    },
    "ROUND_NUMBER_SUSPICIOUS": {
        "severity": "LOW",
        "message": "Round number expense may indicate estimate vs actual receipt.",
    },
    "CASH_NEAR_10K": {
        "severity": "HIGH",
        "message": "Transaction near $10,000 threshold. Bank may file CTR. "
                   "Ensure proper documentation.",
    },
    "PERSONAL_EXPENSE_MIXED": {
        "severity": "MEDIUM",
        "message": "Potential personal expense in business account. "
                   "IRS disallows personal expenses as business deductions.",
    },
    # ── CONFIDENCE FLAGS ────────────────────────────────────────
    "LOW_CONFIDENCE_CATEGORY": {
        "severity": "MEDIUM",
        "message": "System could not reliably categorize. CPA review required.",
    },
    "AMBIGUOUS_VENDOR": {
        "severity": "MEDIUM",
        "message": "Vendor sells across many categories. Receipt needed.",
    },
    # ── BUSINESS STRUCTURE FLAGS ────────────────────────────────
    "POSSIBLE_CAPITAL_EXPENSE": {
        "severity": "HIGH",
        "message": "Purchase > $2,500 may need capitalization vs expensing. "
                   "CPA to apply Section 179 or Bonus Depreciation.",
        "irs_ref": "IRC Section 179 / 168(k)",
    },
    "LOAN_PAYMENT_DETECTED": {
        "severity": "MEDIUM",
        "message": "Loan payments must be split: principal reduces liability "
                   "(not deductible), interest is deductible.",
    },
}

PERSONAL_KEYWORDS = [
    "NETFLIX", "SPOTIFY", "HULU", "DISNEY+", "HBO",
    "GROCERY", "KROGER", "PUBLIX", "WHOLE FOODS",
    "NORDSTROM", "GAP", "OLD NAVY", "ZARA",
    "PLANET FITNESS", "GYM",
]

ROUND_AMOUNTS = {
    Decimal("500"), Decimal("1000"), Decimal("2500"),
    Decimal("5000"), Decimal("10000"),
}

AMBIGUOUS_VENDORS = ["AMAZON", "WALMART", "TARGET", "HOME DEPOT", "COSTCO"]


class FlagEngine:
    """Applies all flag rules to transactions."""

    def flag_batch(self, batch: TransactionBatch) -> Dict:
        """Run all flags against a batch. Returns summary."""
        txns = batch.transactions

        # 1. Balance mismatch
        if not batch.balance_reconciles():
            for t in txns:
                if "BALANCE_MISMATCH" not in t.flags:
                    t.flags.append("BALANCE_MISMATCH")
                    t.flag_notes.append(FLAG_RULES["BALANCE_MISMATCH"]["message"])

        # 2. Per-transaction flags
        for txn in txns:
            self._flag_transaction(txn)

        # 3. Duplicate detection
        self._detect_duplicates(txns)

        # Build summary
        flag_counts: Dict[str, int] = defaultdict(int)
        flagged = []
        for t in txns:
            for f in t.flags:
                flag_counts[f] += 1
            if t.is_flagged:
                flagged.append(t)

        by_severity: Dict[str, List] = {"CRITICAL": [], "HIGH": [], "MEDIUM": [], "LOW": []}
        for t in flagged:
            worst = self._worst_severity(t.flags)
            by_severity[worst].append(t)

        return {
            "total_flags": sum(flag_counts.values()),
            "flagged_transactions": len(flagged),
            "flag_counts": dict(flag_counts),
            "by_severity": {k: len(v) for k, v in by_severity.items()},
            "flagged_list": flagged,
        }

    def _flag_transaction(self, txn: Transaction):
        desc_upper = txn.description.upper()
        amt = txn.amount

        # Meals > $75
        if txn.account_code == "6150" and amt > Decimal("75"):
            self._add_flag(txn, "MEALS_OVER_75")

        # Large cash withdrawal
        if ("ATM" in desc_upper or "CASH" in desc_upper) and amt > Decimal("500"):
            self._add_flag(txn, "LARGE_CASH_WITHDRAWAL")

        # Cash near $10K
        if Decimal("8000") <= amt <= Decimal("10000"):
            if "CASH" in desc_upper or "DEPOSIT" in desc_upper or "WITHDRAWAL" in desc_upper:
                self._add_flag(txn, "CASH_NEAR_10K")

        # Round number suspicious
        if amt in ROUND_AMOUNTS and txn.direction == "DEBIT":
            self._add_flag(txn, "ROUND_NUMBER_SUSPICIOUS")

        # Personal expense in business account
        if any(kw in desc_upper for kw in PERSONAL_KEYWORDS):
            self._add_flag(txn, "PERSONAL_EXPENSE_MIXED")

        # Capital expense > $2,500
        if amt > Decimal("2500") and txn.account_type == "EXPENSE" and txn.direction == "DEBIT":
            self._add_flag(txn, "POSSIBLE_CAPITAL_EXPENSE")

        # Loan payment
        if txn.account_code in ("2300", "2400"):
            self._add_flag(txn, "LOAN_PAYMENT_DETECTED")

        # Ambiguous vendor
        if any(v in desc_upper for v in AMBIGUOUS_VENDORS):
            self._add_flag(txn, "AMBIGUOUS_VENDOR")

    def _detect_duplicates(self, txns: List[Transaction]):
        seen: Dict[str, List[Transaction]] = defaultdict(list)
        for t in txns:
            key = f"{t.date}|{t.amount}|{t.direction}"
            seen[key].append(t)
        for key, group in seen.items():
            if len(group) >= 2:
                for t in group:
                    self._add_flag(t, "DUPLICATE_TRANSACTION")

    def _add_flag(self, txn: Transaction, flag_id: str):
        if flag_id not in txn.flags:
            txn.flags.append(flag_id)
            rule = FLAG_RULES.get(flag_id, {})
            txn.flag_notes.append(rule.get("message", flag_id))

    def _worst_severity(self, flags: List[str]) -> str:
        order = ["CRITICAL", "HIGH", "MEDIUM", "LOW"]
        worst = "LOW"
        for f in flags:
            sev = FLAG_RULES.get(f, {}).get("severity", "LOW")
            if order.index(sev) < order.index(worst):
                worst = sev
        return worst
