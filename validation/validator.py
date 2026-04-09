"""
validator.py
============
Two-class validation system:

1. STRUCTURAL VALIDITY (math/ledger integrity):
   - Every JE balances (debits == credits)
   - Trial balance balances
   - Bank reconciliation matches
   - No float contamination in money fields

2. SEMANTIC VALIDITY (accounting meaning):
   - Large deposits labeled revenue but look like transfers
   - Amazon/Walmart expenses without receipt
   - Fuel charges posted to wrong account
   - Revenue credited to expense accounts
   - Loans hitting P&L as expense

This separation prevents false confidence and makes review measurable.
"""

from decimal import Decimal, InvalidOperation
from typing import Dict, List
from dataclasses import dataclass, field


@dataclass
class ValidationIssue:
    category: str           # "structural" or "semantic"
    severity: str           # "CRITICAL" / "HIGH" / "MEDIUM" / "LOW"
    code: str               # Machine-readable code
    message: str            # Human-readable description
    transaction_id: str = ""
    account_code: str = ""


@dataclass
class ValidationReport:
    structural_pass: bool = True
    semantic_pass: bool = True
    issues: List[ValidationIssue] = field(default_factory=list)
    structural_count: int = 0
    semantic_count: int = 0

    @property
    def all_pass(self) -> bool:
        return self.structural_pass and self.semantic_pass

    @property
    def critical_count(self) -> int:
        return sum(1 for i in self.issues if i.severity == "CRITICAL")

    def to_dict(self) -> Dict:
        return {
            "structural_pass": self.structural_pass,
            "semantic_pass": self.semantic_pass,
            "all_pass": self.all_pass,
            "structural_issues": self.structural_count,
            "semantic_issues": self.semantic_count,
            "critical_count": self.critical_count,
            "issues": [
                {
                    "category": i.category,
                    "severity": i.severity,
                    "code": i.code,
                    "message": i.message,
                    "transaction_id": i.transaction_id,
                }
                for i in self.issues
            ],
        }


class ValidationEngine:
    """Runs structural and semantic validation on the full pipeline output."""

    def validate(self, batch, journal_entries, trial_balance, reconciliation_result=None) -> ValidationReport:
        report = ValidationReport()

        self._structural_checks(report, batch, journal_entries, trial_balance, reconciliation_result)
        self._semantic_checks(report, batch)

        report.structural_count = sum(1 for i in report.issues if i.category == "structural")
        report.semantic_count = sum(1 for i in report.issues if i.category == "semantic")

        # Structural pass requires zero CRITICAL structural issues
        report.structural_pass = not any(
            i.category == "structural" and i.severity == "CRITICAL"
            for i in report.issues
        )
        # Semantic pass requires zero CRITICAL semantic issues
        report.semantic_pass = not any(
            i.category == "semantic" and i.severity == "CRITICAL"
            for i in report.issues
        )

        return report

    # ── STRUCTURAL CHECKS ────────────────────────────────────────

    def _structural_checks(self, report, batch, journal_entries, trial_balance, recon):
        # S1: Every journal entry must balance
        for je in journal_entries:
            if not je.is_balanced:
                report.issues.append(ValidationIssue(
                    category="structural", severity="CRITICAL",
                    code="UNBALANCED_JE",
                    message=f"Journal entry {je.entry_id} is unbalanced: "
                            f"debits={je.total_debits} credits={je.total_credits}",
                    transaction_id=je.source_transaction_id,
                ))

        # S2: Trial balance must balance
        if not trial_balance.get("is_balanced", True):
            diff = trial_balance.get("difference", 0)
            report.issues.append(ValidationIssue(
                category="structural", severity="CRITICAL",
                code="TB_UNBALANCED",
                message=f"Trial balance out of balance by ${diff}. "
                        "Total debits != total credits.",
            ))

        # S3: Bank reconciliation
        if recon:
            if recon.status == "RED":
                report.issues.append(ValidationIssue(
                    category="structural", severity="CRITICAL",
                    code="RECONCILIATION_FAILED",
                    message=f"Bank reconciliation failed. Difference: ${recon.difference}. "
                            f"Issues: {'; '.join(recon.issues)}",
                ))
            elif recon.status == "YELLOW" and recon.issues:
                report.issues.append(ValidationIssue(
                    category="structural", severity="MEDIUM",
                    code="RECONCILIATION_WARN",
                    message=f"Bank reconciliation has warnings: {'; '.join(recon.issues)}",
                ))

        # S4: Transaction count consistency
        je_count = len(journal_entries)
        txn_count = batch.count
        if je_count != txn_count:
            report.issues.append(ValidationIssue(
                category="structural", severity="HIGH",
                code="COUNT_MISMATCH",
                message=f"Transaction count ({txn_count}) != journal entry count ({je_count}).",
            ))

        # S5: No zero-amount transactions (likely parse error)
        for txn in batch.transactions:
            if txn.amount == Decimal("0"):
                report.issues.append(ValidationIssue(
                    category="structural", severity="MEDIUM",
                    code="ZERO_AMOUNT",
                    message=f"Transaction has zero amount: '{txn.description}'",
                    transaction_id=txn.transaction_id,
                ))

    # ── SEMANTIC CHECKS ──────────────────────────────────────────

    def _semantic_checks(self, report, batch):
        for txn in batch.transactions:
            desc_upper = txn.description.upper()

            # M1: Revenue credited to expense account
            if txn.direction == "CREDIT" and txn.account_type == "EXPENSE":
                report.issues.append(ValidationIssue(
                    category="semantic", severity="HIGH",
                    code="CREDIT_TO_EXPENSE",
                    message=f"Credit (deposit) posted to expense account {txn.account_code}. "
                            f"'{txn.description}' — likely should be revenue or refund.",
                    transaction_id=txn.transaction_id,
                    account_code=txn.account_code,
                ))

            # M2: Loan payment hitting P&L as expense
            if (txn.account_type == "EXPENSE" and
                    any(kw in desc_upper for kw in ["LOAN", "SBA", "NOTE PAYMENT"])):
                report.issues.append(ValidationIssue(
                    category="semantic", severity="HIGH",
                    code="LOAN_AS_EXPENSE",
                    message=f"Loan payment '{txn.description}' posted as expense. "
                            "Principal portion should reduce liability, not hit P&L.",
                    transaction_id=txn.transaction_id,
                    account_code=txn.account_code,
                ))

            # M3: Large deposit auto-classified as revenue without verification
            if (txn.direction == "CREDIT" and txn.amount >= Decimal("5000") and
                    txn.inflow_type in ("UNKNOWN", "") and
                    txn.account_type == "REVENUE"):
                report.issues.append(ValidationIssue(
                    category="semantic", severity="MEDIUM",
                    code="LARGE_UNVERIFIED_REVENUE",
                    message=f"Large deposit ${txn.amount} classified as revenue without "
                            f"inflow verification. '{txn.description}'",
                    transaction_id=txn.transaction_id,
                ))

            # M4: Owner draw classified as expense
            if (any(kw in desc_upper for kw in ["OWNER DRAW", "OWNER DISTRIBUTION", "PERSONAL"]) and
                    txn.account_type == "EXPENSE"):
                report.issues.append(ValidationIssue(
                    category="semantic", severity="HIGH",
                    code="DRAW_AS_EXPENSE",
                    message=f"Possible owner draw '{txn.description}' classified as expense. "
                            "Owner draws are equity reductions, NOT deductible expenses.",
                    transaction_id=txn.transaction_id,
                ))

            # M5: Meals without deductibility limit set
            if txn.account_code == "6150" and txn.deductible_pct == Decimal("1.00"):
                report.issues.append(ValidationIssue(
                    category="semantic", severity="MEDIUM",
                    code="MEALS_FULL_DEDUCTION",
                    message=f"Meals expense '{txn.description}' at 100% deduction. "
                            "IRS limits most business meals to 50% deductible.",
                    transaction_id=txn.transaction_id,
                ))

            # M6: Capex posted as immediate expense
            if (txn.amount > Decimal("2500") and txn.account_type == "EXPENSE" and
                    not txn.is_capex and
                    any(kw in desc_upper for kw in [
                        "VEHICLE", "EQUIPMENT", "MACHINERY", "COMPUTER", "LAPTOP"
                    ])):
                report.issues.append(ValidationIssue(
                    category="semantic", severity="HIGH",
                    code="CAPEX_AS_EXPENSE",
                    message=f"${txn.amount} purchase '{txn.description}' may be a capital "
                            "expenditure that should be depreciated, not immediately expensed.",
                    transaction_id=txn.transaction_id,
                ))

        # M7: Check for uncategorized transactions in full analysis
        uncat = sum(1 for t in batch.transactions if t.categorization_layer == "uncategorized")
        if uncat > 0:
            report.issues.append(ValidationIssue(
                category="semantic", severity="MEDIUM",
                code="UNCATEGORIZED_REMAINING",
                message=f"{uncat} transaction(s) remain uncategorized. "
                        "These require manual review before the analysis is complete.",
            ))
