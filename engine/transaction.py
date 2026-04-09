"""
transaction.py
==============
Universal Transaction Schema.
Every transaction from ANY document type becomes this standard object.
All amounts use Decimal — zero float rounding errors.
"""

import uuid
from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal, ROUND_HALF_UP
from typing import Optional, List, Dict


def _cents(value) -> Decimal:
    return Decimal(str(value)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


@dataclass
class Transaction:
    # ── Identity ────────────────────────────────────────────────
    transaction_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    source_document: str = ""
    source_page: int = 0

    # ── Dates ───────────────────────────────────────────────────
    date: str = ""                    # Transaction date YYYY-MM-DD
    post_date: str = ""               # When it posted (can differ)

    # ── Description ─────────────────────────────────────────────
    description: str = ""             # Raw description from bank
    merchant_clean: str = ""          # Cleaned/normalized merchant name

    # ── Amounts ─────────────────────────────────────────────────
    amount: Decimal = field(default_factory=lambda: Decimal("0"))  # Always positive
    direction: str = "DEBIT"          # "DEBIT" or "CREDIT"
    running_balance: Optional[Decimal] = None

    # ── Bank metadata ───────────────────────────────────────────
    raw_category: str = ""            # Bank's own category if present
    account_number: str = ""          # Source account (last 4 only)
    check_number: str = ""
    reference_number: str = ""

    # ── Inflow / outflow classification (before categorization) ──
    inflow_type: str = ""             # REVENUE / FINANCING / EQUITY / TRANSFER / REFUND / UNKNOWN
    inflow_evidence: str = ""         # Why this inflow classification was chosen

    # ── Merchant normalization ─────────────────────────────────
    canonical_merchant_id: str = ""   # Normalized merchant identity
    merchant_tokens: List[str] = field(default_factory=list)

    # ── Categorization (filled by categorizer engine) ───────────
    account_code: str = ""            # CoA account number (e.g. "6120")
    account_name: str = ""            # CoA account name
    account_type: str = ""            # ASSET/LIABILITY/EQUITY/REVENUE/COGS/EXPENSE
    category: str = ""                # High-level bucket
    subcategory: str = ""             # Detailed bucket
    categorization_layer: str = ""    # "exact_match" / "pattern_match" / "ml" / "manual"

    # ── Explainability (every decision has evidence) ───────────
    categorization_evidence: List[str] = field(default_factory=list)
    matched_rule_id: str = ""         # Which rule fired
    matched_tokens: List[str] = field(default_factory=list)
    required_review: bool = False     # Policy-derived: must a human verify?

    # ── Confidence & flags ──────────────────────────────────────
    confidence_score: float = 0.0     # 0.0–1.0
    flags: List[str] = field(default_factory=list)
    flag_notes: List[str] = field(default_factory=list)

    # ── Tax ─────────────────────────────────────────────────────
    deductible: bool = False
    deduction_limit: Optional[float] = None  # e.g. 0.50 for meals
    deductible_pct: Decimal = field(default_factory=lambda: Decimal("1.00"))  # 1.00=100%, 0.50=50% meals
    irs_ref: str = ""                 # e.g. "Schedule C Line 9"
    schedule_c_line: str = ""

    # ── Loan split (filled by LoanSplitter) ────────────────────
    loan_principal: Optional[Decimal] = None
    loan_interest: Optional[Decimal] = None
    loan_fees: Optional[Decimal] = None
    loan_type: str = ""               # "SBA" / "EQUIPMENT" / "LOC" / "MERCHANT" / "GENERIC"
    loan_split_source: str = ""       # "amortization" / "description" / "manual" / "estimated" / ""
    loan_estimated: bool = False      # True if split used heuristic rate assumption

    # ── Capital expenditure ────────────────────────────────────
    is_capex: bool = False
    capex_asset_class: str = ""       # "vehicle" / "equipment" / "computer" / ""
    depreciation_eligible: bool = False

    # ── Journal entry (filled by JE generator) ──────────────────
    debit_account: str = ""
    credit_account: str = ""

    @property
    def signed_amount(self) -> Decimal:
        """Negative for debits, positive for credits."""
        return self.amount if self.direction == "CREDIT" else -self.amount

    @property
    def is_flagged(self) -> bool:
        return len(self.flags) > 0

    @property
    def needs_review(self) -> bool:
        return self.confidence_score < 0.70 or self.is_flagged or self.required_review

    def to_dict(self) -> Dict:
        """Decimal-safe serialization: all money as string, never float."""
        return {
            "transaction_id": self.transaction_id,
            "source_document": self.source_document,
            "date": self.date,
            "post_date": self.post_date,
            "description": self.description,
            "merchant_clean": self.merchant_clean,
            "canonical_merchant_id": self.canonical_merchant_id,
            "amount": str(self.amount),
            "direction": self.direction,
            "inflow_type": self.inflow_type,
            "account_code": self.account_code,
            "account_name": self.account_name,
            "account_type": self.account_type,
            "category": self.category,
            "subcategory": self.subcategory,
            "categorization_layer": self.categorization_layer,
            "categorization_evidence": self.categorization_evidence,
            "matched_rule_id": self.matched_rule_id,
            "required_review": self.required_review,
            "confidence_score": self.confidence_score,
            "flags": self.flags,
            "flag_notes": self.flag_notes,
            "deductible": self.deductible,
            "deductible_pct": str(self.deductible_pct),
            "deduction_limit": self.deduction_limit,
            "irs_ref": self.irs_ref,
            "schedule_c_line": self.schedule_c_line,
            "is_capex": self.is_capex,
            "loan_principal": str(self.loan_principal) if self.loan_principal is not None else None,
            "loan_interest": str(self.loan_interest) if self.loan_interest is not None else None,
            "loan_fees": str(self.loan_fees) if self.loan_fees is not None else None,
            "loan_type": self.loan_type,
            "loan_split_source": self.loan_split_source,
            "loan_estimated": self.loan_estimated,
            "debit_account": self.debit_account,
            "credit_account": self.credit_account,
        }


@dataclass
class TransactionBatch:
    """Container for a batch of transactions from a single document."""
    transactions: List[Transaction] = field(default_factory=list)
    source_document: str = ""
    document_type: str = ""
    period_start: str = ""
    period_end: str = ""
    beginning_balance: Optional[Decimal] = None
    ending_balance: Optional[Decimal] = None
    account_number_last4: str = ""

    # ── Method & integrity labels ──────────────────────────────
    accounting_method: str = "cash"    # "cash" or "accrual"
    method_label: str = "Cash-basis operational P&L from bank activity"
    ruleset_version: str = "1.0.0"
    source_hash: str = ""             # SHA-256 of source file
    parser_version: str = "3.0.0"

    @property
    def total_credits(self) -> Decimal:
        return _cents(sum(t.amount for t in self.transactions if t.direction == "CREDIT"))

    @property
    def total_debits(self) -> Decimal:
        return _cents(sum(t.amount for t in self.transactions if t.direction == "DEBIT"))

    @property
    def net_change(self) -> Decimal:
        return _cents(self.total_credits - self.total_debits)

    @property
    def count(self) -> int:
        return len(self.transactions)

    @property
    def flagged_count(self) -> int:
        return sum(1 for t in self.transactions if t.is_flagged)

    def balance_reconciles(self) -> bool:
        """Check if beginning + net change = ending balance."""
        if self.beginning_balance is None or self.ending_balance is None:
            return True  # Can't check without balances
        expected = _cents(self.beginning_balance + self.net_change)
        return expected == self.ending_balance

    @property
    def reconciliation_difference(self) -> Optional[Decimal]:
        if self.beginning_balance is None or self.ending_balance is None:
            return None
        expected = _cents(self.beginning_balance + self.net_change)
        return _cents(expected - self.ending_balance)

    @property
    def reconciliation_status(self) -> str:
        """Stoplight gate: GREEN / YELLOW / RED."""
        if self.beginning_balance is None or self.ending_balance is None:
            return "YELLOW"  # Can't verify — warn but don't block
        diff = abs(self.reconciliation_difference or Decimal("0"))
        if diff == Decimal("0"):
            return "GREEN"
        elif diff <= Decimal("0.10"):
            return "YELLOW"
        else:
            return "RED"

    @property
    def review_queue_count(self) -> int:
        return sum(1 for t in self.transactions if t.needs_review)

    @property
    def unresolved_flags(self) -> int:
        return sum(1 for t in self.transactions if t.is_flagged)

    def to_dict(self) -> Dict:
        """Decimal-safe serialization: all money as string, never float."""
        return {
            "source_document": self.source_document,
            "document_type": self.document_type,
            "accounting_method": self.accounting_method,
            "method_label": self.method_label,
            "ruleset_version": self.ruleset_version,
            "period": f"{self.period_start} to {self.period_end}",
            "transaction_count": self.count,
            "total_credits": str(self.total_credits),
            "total_debits": str(self.total_debits),
            "net_change": str(self.net_change),
            "beginning_balance": str(self.beginning_balance) if self.beginning_balance is not None else None,
            "ending_balance": str(self.ending_balance) if self.ending_balance is not None else None,
            "reconciliation_status": self.reconciliation_status,
            "reconciliation_difference": str(self.reconciliation_difference) if self.reconciliation_difference is not None else None,
            "review_queue_count": self.review_queue_count,
            "flagged_count": self.flagged_count,
            "transactions": [t.to_dict() for t in self.transactions],
        }
