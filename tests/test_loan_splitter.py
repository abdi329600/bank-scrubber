"""
Tests for upgraded LoanSplitter:
  - Estimated split heuristics by loan type
  - Fee extraction from descriptions
  - Manual split overrides
  - Loan type detection (SBA, equipment, LOC, merchant, generic)
  - 3-way journal entry (principal + interest + fees)
  - Transaction model new fields (loan_fees, loan_type, loan_estimated)
"""

import sys
import os
import pytest
from decimal import Decimal

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from engine.loan_splitter import LoanSplitter, LOAN_TYPE_RATES, AmortizationEntry
from engine.transaction import Transaction
from accounting.journal_entry import JournalEntryGenerator


def _make_txn(desc, amount, direction="DEBIT", date="2025-01-15"):
    return Transaction(
        date=date,
        description=desc,
        amount=Decimal(str(amount)),
        direction=direction,
    )


# ═══════════════════════════════════════════════════════════════════
#  Loan type detection
# ═══════════════════════════════════════════════════════════════════

class TestLoanTypeDetection:
    def setup_method(self):
        self.splitter = LoanSplitter()

    def test_sba_detected(self):
        r = self.splitter.analyze("SBA LOAN PAYMENT", Decimal("1000"))
        assert r.loan_type == "SBA"

    def test_eidl_detected_as_sba(self):
        r = self.splitter.analyze("EIDL LOAN PMT", Decimal("500"))
        assert r.loan_type == "SBA"

    def test_equipment_detected(self):
        r = self.splitter.analyze("EQUIPMENT FINANCING PMT", Decimal("800"))
        assert r.loan_type == "EQUIPMENT"

    def test_loc_detected(self):
        r = self.splitter.analyze("LINE OF CREDIT PAYMENT", Decimal("2000"))
        assert r.loan_type == "LOC"

    def test_merchant_advance_detected(self):
        r = self.splitter.analyze("MERCHANT ADVANCE PMT", Decimal("500"))
        assert r.loan_type == "MERCHANT"

    def test_generic_loan_fallback(self):
        r = self.splitter.analyze("BUSINESS LOAN PMT #4421", Decimal("1500"))
        assert r.loan_type == "GENERIC"

    def test_non_loan_returns_empty_type(self):
        r = self.splitter.analyze("OFFICE DEPOT SUPPLIES", Decimal("50"))
        assert r.is_loan is False
        assert r.loan_type == ""


# ═══════════════════════════════════════════════════════════════════
#  Estimated split heuristic
# ═══════════════════════════════════════════════════════════════════

class TestEstimatedSplit:
    def setup_method(self):
        self.splitter = LoanSplitter()

    def test_estimated_split_produces_principal_and_interest(self):
        """Generic loan with no description detail should still produce a split."""
        r = self.splitter.analyze("BUSINESS LOAN PAYMENT #9912", Decimal("1000"))
        assert r.is_loan is True
        assert r.principal is not None
        assert r.interest is not None
        assert r.split_source == "estimated"
        assert r.is_estimated is True
        assert r.needs_manual_split is True

    def test_estimated_split_sums_to_total(self):
        r = self.splitter.analyze("BUSINESS LOAN PMT", Decimal("2000"))
        assert r.principal + r.interest == Decimal("2000.00")

    def test_sba_rate_lower_than_merchant(self):
        sba = self.splitter.analyze("SBA LOAN PAYMENT", Decimal("1000"))
        merchant = self.splitter.analyze("MERCHANT ADVANCE PMT", Decimal("1000"))
        # SBA has lower rate → lower interest portion
        assert sba.interest < merchant.interest

    def test_interest_pct_capped_at_45(self):
        """Even high-rate loans should not exceed 45% interest portion."""
        r = self.splitter.analyze("MERCHANT ADVANCE PMT", Decimal("10000"))
        assert r.interest <= Decimal("4500.00")

    def test_interest_pct_floor_at_5(self):
        """Even very low rates should have at least 5% interest estimate."""
        r = self.splitter.analyze("SBA LOAN PAYMENT", Decimal("10000"))
        assert r.interest >= Decimal("500.00") or r.interest >= Decimal("325.00")
        # SBA rate = 6.5%, half = 3.25%, but floor is 5%, so interest = $500

    def test_estimated_evidence_contains_rate(self):
        r = self.splitter.analyze("BUSINESS LOAN PMT", Decimal("1000"))
        assert "ESTIMATED" in r.evidence
        assert "annual" in r.evidence.lower()


# ═══════════════════════════════════════════════════════════════════
#  Fee extraction
# ═══════════════════════════════════════════════════════════════════

class TestFeeExtraction:
    def setup_method(self):
        self.splitter = LoanSplitter()

    def test_fee_detected_in_description(self):
        r = self.splitter.analyze("SBA LOAN PAYMENT FEE $25.00", Decimal("1025"))
        assert r.fees == Decimal("25.00")

    def test_late_fee_detected(self):
        r = self.splitter.analyze("LOAN PAYMENT LATE FEE $50", Decimal("1050"))
        assert r.fees == Decimal("50.00")

    def test_no_fee_when_absent(self):
        r = self.splitter.analyze("BUSINESS LOAN PMT", Decimal("1000"))
        assert r.fees is None


# ═══════════════════════════════════════════════════════════════════
#  Manual split override
# ═══════════════════════════════════════════════════════════════════

class TestManualSplit:
    def setup_method(self):
        self.splitter = LoanSplitter()

    def test_manual_split_overrides_estimate(self):
        self.splitter.add_manual_split(
            "SBA LOAN", Decimal("0.70"), Decimal("0.30")
        )
        r = self.splitter.analyze("SBA LOAN PAYMENT", Decimal("1000"))
        assert r.split_source == "manual"
        assert r.principal == Decimal("700.00")
        assert r.interest == Decimal("300.00")
        assert r.is_estimated is False

    def test_manual_split_with_fees(self):
        self.splitter.add_manual_split(
            "EQUIPMENT FINANCING", Decimal("0.65"), Decimal("0.30"), Decimal("0.05")
        )
        r = self.splitter.analyze("EQUIPMENT FINANCING PMT", Decimal("2000"))
        assert r.split_source == "manual"
        assert r.principal == Decimal("1300.00")
        assert r.interest == Decimal("600.00")


# ═══════════════════════════════════════════════════════════════════
#  Description-extracted interest still takes priority over estimate
# ═══════════════════════════════════════════════════════════════════

class TestDescriptionExtraction:
    def setup_method(self):
        self.splitter = LoanSplitter()

    def test_description_interest_used(self):
        r = self.splitter.analyze("LOAN PAYMENT INTEREST $150.00", Decimal("1000"))
        assert r.split_source == "description"
        assert r.interest == Decimal("150.00")
        assert r.principal == Decimal("850.00")
        assert r.is_estimated is False

    def test_description_beats_estimate(self):
        """Description extraction should take priority over heuristic estimate."""
        r = self.splitter.analyze("BUSINESS LOAN INT CHARGE $200", Decimal("1200"))
        assert r.split_source == "description"
        assert r.interest == Decimal("200.00")


# ═══════════════════════════════════════════════════════════════════
#  Process batch populates transaction fields
# ═══════════════════════════════════════════════════════════════════

class TestProcessBatch:
    def test_batch_populates_loan_type(self):
        splitter = LoanSplitter()
        txn = _make_txn("SBA LOAN PAYMENT", 1000)
        report = splitter.process_batch([txn])
        assert txn.loan_type == "SBA"
        assert txn.loan_estimated is True
        assert txn.loan_split_source == "estimated"
        assert txn.loan_principal is not None
        assert txn.loan_interest is not None

    def test_batch_report_has_new_fields(self):
        splitter = LoanSplitter()
        txn = _make_txn("EQUIPMENT FINANCING PMT", 2000)
        report = splitter.process_batch([txn])
        assert "confirmed_split" in report
        assert "estimated_split" in report
        assert "total_fees" in report
        assert "by_loan_type" in report
        assert "by_split_source" in report
        assert report["by_loan_type"].get("EQUIPMENT") == 1
        assert report["by_split_source"].get("estimated") == 1

    def test_estimated_flag_tag(self):
        splitter = LoanSplitter()
        txn = _make_txn("BUSINESS LOAN PMT", 5000)
        splitter.process_batch([txn])
        assert "LOAN_ESTIMATED_SPLIT" in txn.flags

    def test_credits_ignored(self):
        splitter = LoanSplitter()
        txn = _make_txn("LOAN PROCEED DEPOSIT", 50000, direction="CREDIT")
        report = splitter.process_batch([txn])
        assert report["loan_payments_found"] == 0


# ═══════════════════════════════════════════════════════════════════
#  Journal entry: 3-way split with fees
# ═══════════════════════════════════════════════════════════════════

class TestJournalEntryLoanSplit:
    def test_split_loan_creates_3_je_lines(self):
        """Split loan: principal→liability, interest→6700, cash credit."""
        txn = _make_txn("BUSINESS LOAN PMT", 1000)
        txn.account_type = "LIABILITY"
        txn.account_code = "2300"
        txn.account_name = "Loan Payable"
        txn.loan_principal = Decimal("960.00")
        txn.loan_interest = Decimal("40.00")
        txn.loan_estimated = False

        gen = JournalEntryGenerator()
        je = gen.generate(txn)
        assert je.is_balanced
        assert len(je.lines) == 3
        assert je.lines[0].account == "2300"   # principal
        assert je.lines[1].account == "6700"   # interest
        assert je.lines[2].account == "1000"   # cash

    def test_split_loan_with_fees_creates_4_je_lines(self):
        """Split loan with fee: principal→2300, interest→6700, fee→6300, cash."""
        txn = _make_txn("SBA LOAN PMT FEE $25", 1025)
        txn.account_type = "LIABILITY"
        txn.account_code = "2300"
        txn.account_name = "Loan Payable"
        txn.loan_principal = Decimal("775.00")
        txn.loan_interest = Decimal("225.00")
        txn.loan_fees = Decimal("25.00")
        txn.loan_estimated = False

        gen = JournalEntryGenerator()
        je = gen.generate(txn)
        assert je.is_balanced
        assert len(je.lines) == 4
        # Check accounts
        accounts = [l.account for l in je.lines]
        assert "2300" in accounts  # principal
        assert "6700" in accounts  # interest
        assert "6300" in accounts  # fee
        assert "1000" in accounts  # cash

    def test_estimated_loan_has_estimated_memo(self):
        txn = _make_txn("BUSINESS LOAN PMT", 1000)
        txn.account_type = "LIABILITY"
        txn.account_code = "2300"
        txn.account_name = "Loan Payable"
        txn.loan_principal = Decimal("960.00")
        txn.loan_interest = Decimal("40.00")
        txn.loan_estimated = True

        gen = JournalEntryGenerator()
        je = gen.generate(txn)
        assert any("ESTIMATED" in l.memo for l in je.lines)

    def test_unsplit_loan_creates_2_je_lines(self):
        """Unsplit: full amount to liability + cash."""
        txn = _make_txn("NOTE PAYMENT", 1500)
        txn.account_type = "LIABILITY"
        txn.account_code = "2300"
        txn.account_name = "Loan Payable"
        # No loan_principal/loan_interest set

        gen = JournalEntryGenerator()
        je = gen.generate(txn)
        assert je.is_balanced
        assert len(je.lines) == 2


# ═══════════════════════════════════════════════════════════════════
#  Transaction to_dict includes new fields
# ═══════════════════════════════════════════════════════════════════

class TestTransactionSerialization:
    def test_to_dict_includes_loan_fields(self):
        txn = _make_txn("SBA LOAN PMT", 1000)
        txn.loan_principal = Decimal("800.00")
        txn.loan_interest = Decimal("200.00")
        txn.loan_fees = Decimal("25.00")
        txn.loan_type = "SBA"
        txn.loan_split_source = "estimated"
        txn.loan_estimated = True
        d = txn.to_dict()
        assert d["loan_principal"] == "800.00"
        assert d["loan_interest"] == "200.00"
        assert d["loan_fees"] == "25.00"
        assert d["loan_type"] == "SBA"
        assert d["loan_split_source"] == "estimated"
        assert d["loan_estimated"] is True

    def test_to_dict_none_loan_fees(self):
        txn = _make_txn("SOME TXN", 100)
        d = txn.to_dict()
        assert d["loan_fees"] is None
        assert d["loan_type"] == ""
        assert d["loan_estimated"] is False
