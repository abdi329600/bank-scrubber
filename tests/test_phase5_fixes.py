"""
Tests for Phase 5 fixes:
  Fix 1: Misc bucket reduction (intelligent fallback)
  Fix 2: Reimbursement separation (contra-expense routing)
  Fix 3: Deterministic inflow locking
  Fix 4: Schedule C consistency (no float, no double-counting)
  Fix 5: Capex false positive elimination
"""

import sys
import os
import pytest
from decimal import Decimal

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from engine.transaction import Transaction
from categorization.categorizer_engine import CategorizerEngine
from categorization.exact_match import ExactMatchLayer
from categorization.chart_of_accounts import CHART_OF_ACCOUNTS
from accounting.schedule_c import ScheduleCMapper, SCHEDULE_C_MAPPING
from accounting.capex_classifier import CapexClassifier, CAPEX_EXCLUSIONS


def _make_txn(desc, amount, direction="DEBIT", date="2025-01-15"):
    return Transaction(
        date=date,
        description=desc,
        amount=Decimal(str(amount)),
        direction=direction,
    )


# ═══════════════════════════════════════════════════════════════════
#  Fix 1: Misc bucket reduction
# ═══════════════════════════════════════════════════════════════════

class TestMiscBucketReduction:
    """Verify the intelligent fallback breaks misc into subtypes."""

    def setup_method(self):
        self.engine = CategorizerEngine(client_id="test_phase5")

    def test_credit_insurance_keyword_goes_to_4500(self):
        """Insurance keyword on CREDIT → 4500, not 4900."""
        txn = _make_txn("RANDOM INSURANCE CLAIM XYZ", 500, "CREDIT")
        result = self.engine.categorize(txn)
        assert result.account_code == "4500"
        assert "Insurance Reimbursement" in result.account_name

    def test_credit_refund_keyword_goes_to_4510(self):
        """Refund keyword on CREDIT → 4510, not 4900."""
        txn = _make_txn("SOME VENDOR REFUND 12345", 75, "CREDIT")
        result = self.engine.categorize(txn)
        assert result.account_code == "4510"

    def test_credit_reimbursement_keyword_goes_to_4520(self):
        """Reimbursement keyword on CREDIT → 4520, not 4900."""
        txn = _make_txn("EMPLOYEE REIMBURSEMENT Q1", 200, "CREDIT")
        result = self.engine.categorize(txn)
        assert result.account_code == "4520"

    def test_credit_payment_keyword_goes_to_4000(self):
        """Payment-like keyword on CREDIT → 4000 revenue, not 4900."""
        txn = _make_txn("RANDOM CUSTOMER DEPOSIT XYZ", 1500, "CREDIT")
        result = self.engine.categorize(txn)
        assert result.account_code == "4000"

    def test_debit_insurance_keyword_goes_to_6200(self):
        """Insurance keyword on DEBIT → 6200, not 6900."""
        txn = _make_txn("UNKNOWN INSURANCE PREMIUM CO", 300, "DEBIT")
        result = self.engine.categorize(txn)
        assert result.account_code == "6200"

    def test_debit_rent_keyword_goes_to_6100(self):
        """Rent keyword on DEBIT → 6100, not 6900."""
        txn = _make_txn("ABC PROPERTY RENT PAYMENT", 2500, "DEBIT")
        result = self.engine.categorize(txn)
        assert result.account_code == "6100"

    def test_debit_utility_keyword_goes_to_6110(self):
        """Utility keyword on DEBIT → 6110, not 6900."""
        txn = _make_txn("CITY ELECTRIC BILL 02/2025", 180, "DEBIT")
        result = self.engine.categorize(txn)
        assert result.account_code == "6110"

    def test_truly_unknown_debit_stays_6900(self):
        """Truly unknown DEBIT → 6900 misc (but less often now)."""
        txn = _make_txn("XJQZF CORP 99881", 42, "DEBIT")
        result = self.engine.categorize(txn)
        assert result.account_code == "6900"

    def test_truly_unknown_credit_stays_4900(self):
        """Truly unknown CREDIT with no keyword hints → 4900."""
        txn = _make_txn("XJQZF CORP 99881", 42, "CREDIT")
        result = self.engine.categorize(txn)
        assert result.account_code == "4900"


# ═══════════════════════════════════════════════════════════════════
#  Fix 2: Reimbursement separation
# ═══════════════════════════════════════════════════════════════════

class TestReimbursementSeparation:
    """Insurance credits must NOT collide with insurance expense."""

    def test_coa_has_contra_accounts(self):
        assert "4500" in CHART_OF_ACCOUNTS  # Insurance Reimbursements
        assert "4510" in CHART_OF_ACCOUNTS  # Vendor Refunds
        assert "4520" in CHART_OF_ACCOUNTS  # Other Reimbursements
        assert "9000" in CHART_OF_ACCOUNTS  # Suspense

    def test_insurance_debit_and_credit_go_to_different_accounts(self):
        """DEBIT insurance → 6200, CREDIT insurance → 4500."""
        engine = CategorizerEngine(client_id="test_reimb")
        debit = _make_txn("PROGRESSIVE INSURANCE PREMIUM", 350, "DEBIT")
        credit = _make_txn("PROGRESSIVE INSURANCE CLAIM PAYMENT", 800, "CREDIT")
        engine.categorize(debit)
        engine.categorize(credit)
        # Debit should be expense account 6200
        assert debit.account_code == "6200"
        # Credit should be reimbursement account 4500
        assert credit.account_code == "4500"

    def test_exact_match_insurance_claim_routes_to_4500(self):
        """Exact match for insurance claim on CREDIT → 4500."""
        layer = ExactMatchLayer()
        result = layer.match("INSURANCE CLAIM FROM GEICO", direction="CREDIT")
        assert result is not None
        assert result.account == "4500"

    def test_exact_match_vendor_refund_routes_to_4510(self):
        """Exact match for vendor refund → 4510."""
        layer = ExactMatchLayer()
        result = layer.match("VENDOR REFUND FROM STAPLES", direction="CREDIT")
        assert result is not None
        assert result.account == "4510"

    def test_geico_debit_goes_to_expense(self):
        """GEICO on DEBIT side → 6200 expense."""
        layer = ExactMatchLayer()
        result = layer.match("GEICO PREMIUM PAYMENT", direction="DEBIT")
        assert result is not None
        assert result.account == "6200"

    def test_geico_credit_skips_expense_rule(self):
        """GEICO on CREDIT side → should NOT match 6200 expense rule."""
        layer = ExactMatchLayer()
        result = layer.match("GEICO CLAIM PAYMENT", direction="CREDIT")
        # Should match INSURANCE CLAIM or CLAIM PAYMENT (4500), not GEICO (6200)
        assert result is not None
        assert result.account == "4500"


# ═══════════════════════════════════════════════════════════════════
#  Fix 3: Deterministic inflow locking
# ═══════════════════════════════════════════════════════════════════

class TestDeterministicInflows:
    """Revenue patterns that should be near-locks."""

    def setup_method(self):
        self.layer = ExactMatchLayer()

    def test_pos_sale_batch(self):
        r = self.layer.match("POS SALE BATCH 0215")
        assert r is not None
        assert r.account == "4000"
        assert r.confidence == 0.99

    def test_daily_sales_deposit(self):
        r = self.layer.match("CASH DEPOSIT - DAILY SALES")
        assert r is not None
        assert r.account == "4000"

    def test_customer_payment_invoice(self):
        r = self.layer.match("CUSTOMER PAYMENT - INVOICE 4421")
        assert r is not None
        assert r.account == "4000"

    def test_zelle_from_customer(self):
        r = self.layer.match("ZELLE FROM JOHN DOE")
        assert r is not None
        assert r.account == "4000"

    def test_venmo_cashout(self):
        r = self.layer.match("VENMO CASHOUT TO CHECKING")
        assert r is not None
        assert r.account == "4000"

    def test_check_deposit(self):
        r = self.layer.match("CHECK DEPOSIT 3391")
        assert r is not None
        assert r.account == "4000"

    def test_wire_transfer_in(self):
        r = self.layer.match("WIRE TRANSFER IN FROM CLIENT")
        assert r is not None
        assert r.account == "4000"

    def test_ach_credit(self):
        r = self.layer.match("ACH CREDIT - ACME CORP")
        assert r is not None
        assert r.account == "4000"

    def test_invoice_payment(self):
        r = self.layer.match("INVOICE PAYMENT #2841")
        assert r is not None
        assert r.account == "4000"

    def test_service_payment(self):
        r = self.layer.match("SERVICE PAYMENT - JAN 2025")
        assert r is not None
        assert r.account == "4200"

    def test_consulting_fee(self):
        r = self.layer.match("CONSULTING FEE - PROJECT ALPHA")
        assert r is not None
        assert r.account == "4300"


# ═══════════════════════════════════════════════════════════════════
#  Fix 4: Schedule C consistency
# ═══════════════════════════════════════════════════════════════════

class TestScheduleCConsistency:
    """Verify Schedule C mapping is clean and consistent."""

    def test_no_account_appears_in_two_lines(self):
        """Each account code should appear in exactly one Schedule C line."""
        seen = {}
        for line, codes in SCHEDULE_C_MAPPING.items():
            for code in codes:
                assert code not in seen, (
                    f"Account {code} appears in both '{seen[code]}' and '{line}'"
                )
                seen[code] = line

    def test_reimbursement_accounts_in_other_income(self):
        """4500/4510/4520 should map to Line 6 - Other Income."""
        line6 = SCHEDULE_C_MAPPING.get("Line 6  - Other Income", [])
        assert "4500" in line6
        assert "4510" in line6
        assert "4520" in line6

    def test_insurance_accounts_in_line_15(self):
        """Both 6130 (vehicle) and 6200 (general) map to Line 15."""
        line15 = SCHEDULE_C_MAPPING.get("Line 15 - Insurance", [])
        assert "6130" in line15
        assert "6200" in line15

    def test_vehicle_insurance_not_in_line_9(self):
        """6130 should be in Line 15 (Insurance), NOT Line 9 (Car & Truck)."""
        line9 = SCHEDULE_C_MAPPING.get("Line 9  - Car & Truck", [])
        assert "6130" not in line9

    def test_summary_values_are_strings(self):
        """Schedule C summary should produce strings, not floats."""
        mapper = ScheduleCMapper()
        txn = _make_txn("STRIPE PAYOUT", 1000, "CREDIT")
        txn.account_code = "4000"
        result = mapper.map_transactions([txn])
        summary = result["summary"]
        for key, val in summary.items():
            assert isinstance(val, str), f"summary['{key}'] is {type(val)}, expected str"

    def test_line_totals_are_strings(self):
        """Line totals should be strings, not floats."""
        mapper = ScheduleCMapper()
        txn = _make_txn("OFFICE DEPOT SUPPLIES", 50, "DEBIT")
        txn.account_code = "6350"
        result = mapper.map_transactions([txn])
        for line_name, data in result.get("lines", {}).items():
            assert isinstance(data["total"], str), f"{line_name} total is not str"


# ═══════════════════════════════════════════════════════════════════
#  Fix 5: Capex false positive elimination
# ═══════════════════════════════════════════════════════════════════

class TestCapexFalsePositives:
    """Verify routine expenses never get capex/large-expense flags."""

    def setup_method(self):
        self.capex = CapexClassifier()

    def test_rent_never_flags_as_capex(self):
        r = self.capex.classify("RENT PAYMENT - 123 MAIN ST", Decimal("15000"))
        assert r.is_capex is False
        assert r.recommendation == ""

    def test_insurance_never_flags_as_capex(self):
        r = self.capex.classify("PROGRESSIVE INSURANCE PREMIUM", Decimal("12000"))
        assert r.is_capex is False
        assert r.recommendation == ""

    def test_payroll_never_flags_as_capex(self):
        r = self.capex.classify("ADP PAYROLL BATCH RUN", Decimal("50000"))
        assert r.is_capex is False
        assert r.recommendation == ""

    def test_utility_never_flags_as_capex(self):
        r = self.capex.classify("CITY ELECTRIC POWER BILL", Decimal("11000"))
        assert r.is_capex is False
        assert r.recommendation == ""

    def test_known_expense_code_suppresses_large_review(self):
        """A $15k insurance expense with code 6200 should NOT flag LARGE_EXPENSE_REVIEW."""
        r = self.capex.classify("MYSTERY VENDOR ABC", Decimal("15000"),
                                account_type="EXPENSE", account_code="6200")
        assert r.is_capex is False
        assert r.recommendation == ""

    def test_unknown_code_with_large_amount_does_flag(self):
        """A $15k misc expense (6900) SHOULD still flag for review."""
        r = self.capex.classify("MYSTERY VENDOR ABC", Decimal("15000"),
                                account_type="EXPENSE", account_code="6900")
        assert r.is_capex is False
        assert r.recommendation != ""

    def test_capex_exclusions_include_property_mgmt(self):
        assert "PROPERTY MGMT" in CAPEX_EXCLUSIONS

    def test_capex_exclusions_include_storage(self):
        assert "STORAGE UNIT" in CAPEX_EXCLUSIONS
