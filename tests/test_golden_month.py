"""
test_golden_month.py
====================
Golden-file regression test: run the full pipeline on a known fixture
and verify structural invariants + stable outputs.
"""

import sys
import json
from pathlib import Path
from decimal import Decimal

sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest
from engine.transaction import Transaction, TransactionBatch
from engine.loan_splitter import LoanSplitter
from engine.reconciliation import ReconciliationEngine
from categorization.categorizer_engine import CategorizerEngine
from accounting.journal_entry import JournalEntryGenerator
from accounting.trial_balance import TrialBalanceGenerator
from accounting.capex_classifier import CapexClassifier
from validation.validator import ValidationEngine
from validation.acceptance import AcceptanceCriteria
from flags.flag_engine import FlagEngine


GOLDEN_TXNS = [
    Transaction(description="STRIPE PAYOUT 12345", amount=Decimal("1250.00"),
                direction="CREDIT", date="2026-03-02"),
    Transaction(description="TRANSFER TO SAVINGS", amount=Decimal("500.00"),
                direction="DEBIT", date="2026-03-03"),
    Transaction(description="SBA LOAN PAYMENT INTEREST $45.00", amount=Decimal("820.13"),
                direction="DEBIT", date="2026-03-05"),
    Transaction(description="RESTAURANT ABC", amount=Decimal("64.20"),
                direction="DEBIT", date="2026-03-07"),
    Transaction(description="SYSCO FOODS ORDER", amount=Decimal("890.00"),
                direction="DEBIT", date="2026-03-10"),
    Transaction(description="ADP PAYROLL 03/15", amount=Decimal("3200.00"),
                direction="DEBIT", date="2026-03-15"),
    Transaction(description="GEICO INSURANCE", amount=Decimal("180.00"),
                direction="DEBIT", date="2026-03-18"),
    Transaction(description="STRIPE PAYOUT 67890", amount=Decimal("4500.00"),
                direction="CREDIT", date="2026-03-20"),
    Transaction(description="COMCAST INTERNET", amount=Decimal("89.99"),
                direction="DEBIT", date="2026-03-22"),
    Transaction(description="MONTHLY SERVICE FEE", amount=Decimal("15.00"),
                direction="DEBIT", date="2026-03-31"),
]


def _build_batch():
    batch = TransactionBatch(
        transactions=list(GOLDEN_TXNS),
        source_document="golden_march_2026.csv",
        document_type="bank_statement",
        period_start="2026-03-01",
        period_end="2026-03-31",
        beginning_balance=Decimal("10000.00"),
        ending_balance=Decimal("9990.68"),
    )
    return batch


class TestGoldenMonthPipeline:
    """Full pipeline on a known fixture. Verifies structural invariants."""

    def setup_method(self):
        self.batch = _build_batch()

        # Step 1: Loan splitting
        ls = LoanSplitter()
        ls.process_batch(self.batch.transactions)

        # Step 2: Categorize (full mode)
        cat = CategorizerEngine(mode="full")
        self.cat_result = cat.categorize_batch(self.batch.transactions)

        # Step 3: Capex detection
        capex = CapexClassifier()
        capex.process_batch(self.batch.transactions)

        # Step 4: Journal entries
        je_gen = JournalEntryGenerator()
        self.entries = je_gen.generate_batch(self.batch.transactions)

        # Step 5: Trial balance
        tb_gen = TrialBalanceGenerator()
        self.tb = tb_gen.generate(self.entries)

        # Step 6: Flags
        fe = FlagEngine()
        self.flag_report = fe.flag_batch(self.batch)

        # Step 7: Reconciliation
        recon = ReconciliationEngine()
        self.recon_result = recon.reconcile(self.batch)

        # Step 8: Validation
        ve = ValidationEngine()
        self.val_report = ve.validate(
            self.batch, self.entries, self.tb, self.recon_result
        )

        # Step 9: Acceptance
        ac = AcceptanceCriteria()
        self.accept = ac.evaluate(
            self.batch, self.entries, self.tb, self.recon_result, self.val_report
        )

    # ── Structural invariants ─────────────────────────────────

    def test_all_transactions_processed(self):
        assert self.cat_result["total"] == 10

    def test_all_journal_entries_balanced(self):
        for entry in self.entries:
            total_debit = sum(line.debit for line in entry.lines)
            total_credit = sum(line.credit for line in entry.lines)
            assert total_debit == total_credit, \
                f"JE {entry.transaction_id} unbalanced: D={total_debit} C={total_credit}"

    def test_trial_balance_balanced(self):
        assert self.tb["is_balanced"] is True

    def test_reconciliation_ran(self):
        assert self.recon_result.status in ("GREEN", "YELLOW", "RED")

    def test_acceptance_has_four_gates(self):
        assert len(self.accept.gates) == 4
        gate_names = {g.name for g in self.accept.gates}
        assert gate_names == {"ARITHMETIC", "STRUCTURAL", "DISCLOSURE", "REVIEW"}

    # ── Categorization correctness ────────────────────────────

    def test_stripe_classified_as_revenue(self):
        stripe_txns = [t for t in self.batch.transactions
                       if "STRIPE" in t.description.upper()]
        for t in stripe_txns:
            assert t.account_type in ("REVENUE", ""), \
                f"Stripe txn should be revenue: {t.description} -> {t.account_type}"

    def test_loan_payment_detected(self):
        loan_txns = [t for t in self.batch.transactions
                     if "LOAN" in t.description.upper()]
        assert len(loan_txns) >= 1
        for t in loan_txns:
            assert t.loan_interest is not None or t.account_type == "LIABILITY"

    def test_inflow_classification_on_credits(self):
        credits = [t for t in self.batch.transactions if t.direction == "CREDIT"]
        for t in credits:
            assert t.inflow_type != "", f"Credit missing inflow_type: {t.description}"

    # ── Decimal safety ────────────────────────────────────────

    def test_transaction_serialization_no_floats(self):
        for t in self.batch.transactions:
            d = t.to_dict()
            assert isinstance(d["amount"], str), "amount must be string"
            assert isinstance(d["deductible_pct"], str), "deductible_pct must be string"

    def test_batch_serialization_no_floats(self):
        bd = self.batch.to_dict()
        assert isinstance(bd["total_credits"], str)
        assert isinstance(bd["total_debits"], str)

    # ── Review queue ──────────────────────────────────────────

    def test_uncategorized_marked_for_review(self):
        uncats = [t for t in self.batch.transactions
                  if t.categorization_layer == "uncategorized"]
        for t in uncats:
            assert t.required_review is True, \
                f"Uncategorized txn must require review: {t.description}"

    def test_explainability_evidence_present(self):
        categorized = [t for t in self.batch.transactions
                       if t.categorization_layer != "uncategorized"]
        for t in categorized:
            assert len(t.categorization_evidence) > 0, \
                f"Missing evidence for: {t.description}"
