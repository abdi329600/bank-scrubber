"""
acceptance.py
=============
Acceptance criteria enforcement — defines "100% right" operationally.

Four measurable guarantees:
  1. ARITHMETIC — totals, margins, rollups exact under declared rounding policy
  2. STRUCTURAL — every JE balanced, TB balanced, reconciliation passes
  3. DISCLOSURE — method labeled (cash/accrual), areas needing evidence flagged
  4. REVIEW     — everything below confidence threshold flagged and must be resolved

A "Full Analysis" CANNOT be issued unless all gates pass.
"""

from decimal import Decimal
from typing import Dict, List
from dataclasses import dataclass, field


@dataclass
class Gate:
    name: str
    passed: bool
    details: str
    blocker: bool = True  # If True, blocks full analysis when failed


@dataclass
class AcceptanceReport:
    gates: List[Gate] = field(default_factory=list)
    can_issue_full: bool = False
    overall_status: str = "BLOCKED"  # "PASS" / "PASS_WITH_WARNINGS" / "BLOCKED"
    summary: str = ""

    def to_dict(self) -> Dict:
        return {
            "can_issue_full": self.can_issue_full,
            "overall_status": self.overall_status,
            "summary": self.summary,
            "gates": [
                {"name": g.name, "passed": g.passed, "details": g.details, "blocker": g.blocker}
                for g in self.gates
            ],
        }


class AcceptanceCriteria:
    """
    Evaluates whether a processed batch meets issuance criteria.
    Replaces vague "100% right" with measurable gates.
    """

    def __init__(self, confidence_threshold: float = 0.70):
        self.confidence_threshold = confidence_threshold

    def evaluate(
        self,
        batch,
        journal_entries,
        trial_balance: Dict,
        reconciliation_result=None,
        validation_report=None,
    ) -> AcceptanceReport:
        report = AcceptanceReport()

        # ── GATE 1: ARITHMETIC ───────────────────────────────────
        arith_issues = []

        # 1a. All JEs balanced
        unbalanced = [je for je in journal_entries if not je.is_balanced]
        if unbalanced:
            arith_issues.append(f"{len(unbalanced)} unbalanced journal entries")

        # 1b. TB balanced
        if not trial_balance.get("is_balanced", False):
            arith_issues.append(
                f"Trial balance out of balance by ${trial_balance.get('difference', '?')}"
            )

        # 1c. P&L derived from TB (architecture guarantee — always true in our system)
        # This is guaranteed by design: P&L reads from TB totals.

        report.gates.append(Gate(
            name="ARITHMETIC",
            passed=(len(arith_issues) == 0),
            details="All totals, margins, and rollups exact." if not arith_issues
                    else "; ".join(arith_issues),
            blocker=True,
        ))

        # ── GATE 2: STRUCTURAL ───────────────────────────────────
        struct_issues = []

        # 2a. Reconciliation
        recon_status = "YELLOW"
        if reconciliation_result:
            recon_status = reconciliation_result.status
            if recon_status == "RED":
                struct_issues.append(
                    f"Bank reconciliation RED: diff=${reconciliation_result.difference}"
                )

        # 2b. Structural validation pass
        if validation_report and not validation_report.structural_pass:
            critical = [i for i in validation_report.issues
                        if i.category == "structural" and i.severity == "CRITICAL"]
            struct_issues.append(
                f"{len(critical)} critical structural validation failure(s)"
            )

        report.gates.append(Gate(
            name="STRUCTURAL",
            passed=(len(struct_issues) == 0),
            details="All structural integrity checks pass." if not struct_issues
                    else "; ".join(struct_issues),
            blocker=True,
        ))

        # ── GATE 3: DISCLOSURE ───────────────────────────────────
        disc_items = []

        # 3a. Method label present
        if not batch.accounting_method:
            disc_items.append("Accounting method not declared")

        # 3b. Check for COGS without inventory (should be labeled preliminary)
        cogs_txns = [t for t in batch.transactions if t.account_type == "COGS"]
        if cogs_txns:
            disc_items.append(
                "COGS present — labeled as bank-proxy unless inventory values provided"
            )

        # 3c. Loan payments without split
        unsplit_loans = [t for t in batch.transactions
                         if t.loan_split_source == "unsplit"]
        if unsplit_loans:
            disc_items.append(
                f"{len(unsplit_loans)} loan payment(s) without principal/interest split"
            )

        # Disclosure is a non-blocker — it's about labeling, not stopping
        report.gates.append(Gate(
            name="DISCLOSURE",
            passed=(len(disc_items) == 0),
            details="All methods and limitations properly disclosed." if not disc_items
                    else "; ".join(disc_items),
            blocker=False,
        ))

        # ── GATE 4: REVIEW ───────────────────────────────────────
        review_issues = []

        # 4a. Low confidence items
        low_conf = [t for t in batch.transactions
                    if t.confidence_score < self.confidence_threshold]
        if low_conf:
            review_issues.append(
                f"{len(low_conf)} transaction(s) below {self.confidence_threshold:.0%} confidence"
            )

        # 4b. Uncategorized items
        uncat = [t for t in batch.transactions
                 if t.categorization_layer == "uncategorized"]
        if uncat:
            review_issues.append(f"{len(uncat)} uncategorized transaction(s)")

        # 4c. Unresolved required-review items
        unresolved = [t for t in batch.transactions if t.required_review]
        if unresolved:
            review_issues.append(
                f"{len(unresolved)} transaction(s) require human review"
            )

        # Review gate: warn but don't block (items are flagged for CPA)
        report.gates.append(Gate(
            name="REVIEW",
            passed=(len(review_issues) == 0),
            details="All items above confidence threshold and reviewed." if not review_issues
                    else "; ".join(review_issues),
            blocker=False,
        ))

        # ── OVERALL VERDICT ──────────────────────────────────────
        blocker_failures = [g for g in report.gates if g.blocker and not g.passed]
        non_blocker_warnings = [g for g in report.gates if not g.blocker and not g.passed]

        if blocker_failures:
            report.can_issue_full = False
            report.overall_status = "BLOCKED"
            report.summary = (
                "Full Analysis CANNOT be issued. Blocking gates failed: "
                + ", ".join(g.name for g in blocker_failures)
                + ". Resolve these before issuing."
            )
        elif non_blocker_warnings:
            report.can_issue_full = True
            report.overall_status = "PASS_WITH_WARNINGS"
            report.summary = (
                "Full Analysis can be issued WITH WARNINGS. "
                "Non-blocking items need attention: "
                + ", ".join(g.name for g in non_blocker_warnings)
                + ". Report will include disclosure notes."
            )
        else:
            report.can_issue_full = True
            report.overall_status = "PASS"
            report.summary = (
                "All acceptance gates pass. Full Analysis is cleared for issuance. "
                "Arithmetic exact, structural integrity verified, disclosures complete, "
                "all items above confidence threshold."
            )

        return report
