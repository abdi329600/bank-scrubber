"""
test_classification.py
======================
Tests for the classification intelligence layer:
- Pre-classifier routing (transfers, equity, financing → balance sheet)
- Inflow bucketing (processor payouts → REVENUE at high confidence)
- Capex exclusion gate (payroll/rent/utilities never trip capex)
- Loan splitter preservation (categorizer respects LIABILITY routing)
- Multi-signal confidence boosting
- Vendor normalization determinism
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from decimal import Decimal
from engine.transaction import Transaction
from engine.inflow_classifier import InflowClassifier
from engine.merchant_normalizer import MerchantNormalizer
from categorization.categorizer_engine import CategorizerEngine
from accounting.capex_classifier import CapexClassifier


class TestInflowBucketing:
    """Processor payouts and known inflows should be classified correctly."""

    def setup_method(self):
        self.clf = InflowClassifier()

    def test_stripe_payout_is_revenue(self):
        r = self.clf.classify("Stripe Payout 04/01")
        assert r.inflow_type == "REVENUE"
        assert r.confidence >= 0.90

    def test_square_deposit_is_revenue(self):
        r = self.clf.classify("Square Deposit 03/15")
        assert r.inflow_type == "REVENUE"
        assert r.confidence >= 0.90

    def test_paypal_transfer_is_revenue(self):
        r = self.clf.classify("PayPal Transfer 04/01")
        assert r.inflow_type == "REVENUE"

    def test_zelle_payment_is_revenue(self):
        r = self.clf.classify("Zelle Payment From John Smith")
        assert r.inflow_type == "REVENUE"

    def test_transfer_from_savings_is_transfer(self):
        r = self.clf.classify("Transfer from Savings Account")
        assert r.inflow_type == "TRANSFER"
        assert r.confidence >= 0.90

    def test_loan_proceeds_is_financing(self):
        r = self.clf.classify("SBA Loan Proceed Deposit")
        assert r.inflow_type == "FINANCING"

    def test_owner_contribution_is_equity(self):
        r = self.clf.classify("Owner Contribution Deposit")
        assert r.inflow_type == "EQUITY"

    def test_insurance_claim_is_refund(self):
        r = self.clf.classify("Insurance Claim Payment GEICO")
        assert r.inflow_type == "REFUND"

    def test_generic_deposit_is_unknown(self):
        r = self.clf.classify("Deposit 12345")
        assert r.inflow_type == "UNKNOWN"
        assert r.requires_review


class TestOutflowPreClassification:
    """Debit transactions should also get pre-classified for transfers/equity."""

    def setup_method(self):
        self.clf = InflowClassifier()

    def test_transfer_to_savings(self):
        r = self.clf._classify_outflow("Transfer to Savings Account")
        assert r.inflow_type == "TRANSFER"

    def test_owner_draw(self):
        r = self.clf._classify_outflow("Owner Draw #1234")
        assert r.inflow_type == "EQUITY"

    def test_sales_tax_payment(self):
        r = self.clf._classify_outflow("Sales Tax Payment State of CA")
        assert r.inflow_type == "TAX_LIABILITY"

    def test_normal_expense_is_outflow(self):
        r = self.clf._classify_outflow("Shell Oil Gas Station")
        assert r.inflow_type == "OUTFLOW"


class TestPreClassifierGate:
    """Categorizer should respect pre-classification and NOT overwrite it."""

    def setup_method(self):
        self.engine = CategorizerEngine(mode="full")

    def _make_txn(self, desc, direction="CREDIT", amount="1000.00"):
        return Transaction(
            description=desc,
            direction=direction,
            amount=Decimal(amount),
        )

    def test_transfer_not_overwritten_to_revenue(self):
        txn = self._make_txn("Transfer from Savings Account")
        txn.inflow_type = "TRANSFER"
        txn.inflow_evidence = "Inter-account transfer"
        self.engine.categorize(txn)
        assert txn.account_type == "ASSET"
        assert txn.categorization_layer == "pre_classifier"

    def test_financing_not_overwritten_to_revenue(self):
        txn = self._make_txn("SBA Loan Proceed Deposit")
        txn.inflow_type = "FINANCING"
        txn.inflow_evidence = "Financing"
        self.engine.categorize(txn)
        assert txn.account_type == "LIABILITY"
        assert txn.categorization_layer == "pre_classifier"

    def test_equity_not_overwritten_to_expense(self):
        txn = self._make_txn("Owner Draw March", direction="DEBIT")
        txn.inflow_type = "EQUITY"
        txn.inflow_evidence = "Owner draw"
        self.engine.categorize(txn)
        assert txn.account_type == "EQUITY"
        assert txn.account_code == "3100"
        assert txn.deductible is False

    def test_loan_splitter_preserved(self):
        txn = self._make_txn("SBA Loan Payment", direction="DEBIT")
        txn.account_type = "LIABILITY"
        txn.account_code = "2300"
        txn.loan_split_source = "unsplit"
        txn.loan_principal = Decimal("500.00")
        txn.loan_interest = Decimal("0")
        self.engine.categorize(txn)
        assert txn.account_type == "LIABILITY"
        assert txn.categorization_layer == "loan_splitter"

    def test_revenue_inflow_still_categorized(self):
        """Revenue inflows should pass through to exact/pattern match."""
        txn = self._make_txn("Stripe Payout 04/01")
        txn.inflow_type = "REVENUE"
        txn.inflow_evidence = "Processor payout"
        self.engine.categorize(txn)
        # Should be categorized by exact match as Sales Revenue
        assert txn.account_type == "REVENUE"
        assert txn.account_code == "4000"


class TestCapexExclusionGate:
    """Capex should NEVER fire on payroll, rent, utilities, or transfers."""

    def setup_method(self):
        self.clf = CapexClassifier()

    def test_payroll_not_capex(self):
        r = self.clf.classify("ADP Payroll Run", Decimal("15000"), "EXPENSE")
        assert r.is_capex is False
        assert r.recommendation == ""

    def test_rent_not_capex(self):
        r = self.clf.classify("Monthly Rent Payment", Decimal("12000"), "EXPENSE")
        assert r.is_capex is False
        assert r.recommendation == ""

    def test_transfer_not_capex(self):
        r = self.clf.classify("Transfer to Savings", Decimal("50000"), "")
        assert r.is_capex is False

    def test_utilities_not_capex(self):
        r = self.clf.classify("Duke Energy Electric Bill", Decimal("3000"), "EXPENSE")
        assert r.is_capex is False

    def test_equipment_purchase_still_detected(self):
        r = self.clf.classify("Industrial Equipment Purchase", Decimal("8000"), "EXPENSE")
        assert r.is_capex is True
        assert r.asset_class == "equipment"

    def test_small_equipment_de_minimis(self):
        r = self.clf.classify("Office Equipment Purchase", Decimal("1500"), "EXPENSE")
        assert r.is_capex is False
        assert r.de_minimis_eligible is True


class TestVendorNormalization:
    """Known vendors should resolve to deterministic canonical IDs."""

    def setup_method(self):
        self.norm = MerchantNormalizer()

    def test_sysco_normalized(self):
        r = self.norm.normalize("SYSCO FOOD SERVICE #1234")
        assert r.canonical_id == "SYSCO"

    def test_us_foods_normalized(self):
        r = self.norm.normalize("US FOODS ORDER #5678")
        assert r.canonical_id == "US_FOODS"

    def test_stripe_payout_normalized(self):
        r = self.norm.normalize("STRIPE PAYOUT 04/01")
        assert r.canonical_id == "STRIPE_PAYOUT"

    def test_square_deposit_normalized(self):
        r = self.norm.normalize("SQUARE DEPOSIT 03/15")
        assert r.canonical_id == "SQUARE_DEPOSIT"

    def test_autozone_normalized(self):
        r = self.norm.normalize("AUTOZONE Parts Store #999")
        assert r.canonical_id == "AUTOZONE"

    def test_quickbooks_variants(self):
        for desc in ["INTUIT *QUICKBOOKS", "QB ONLINE", "QUICKBOOKS SUB"]:
            r = self.norm.normalize(desc)
            assert r.canonical_id == "QUICKBOOKS"


class TestCOGSRouting:
    """COGS vendors should be routed to COGS accounts, not EXPENSE."""

    def setup_method(self):
        self.engine = CategorizerEngine(mode="full")

    def _make_txn(self, desc, direction="DEBIT", amount="500.00"):
        txn = Transaction(
            description=desc,
            direction=direction,
            amount=Decimal(amount),
        )
        txn.inflow_type = "OUTFLOW"
        txn.inflow_evidence = "Standard business outflow"
        return txn

    def test_us_foods_is_cogs(self):
        txn = self._make_txn("US Foods Invoice #1234")
        self.engine.categorize(txn)
        assert txn.account_type == "COGS"

    def test_sysco_is_cogs(self):
        txn = self._make_txn("SYSCO Food Service")
        self.engine.categorize(txn)
        assert txn.account_type == "COGS"

    def test_autozone_is_cogs(self):
        txn = self._make_txn("AutoZone Parts Purchase")
        self.engine.categorize(txn)
        assert txn.account_type == "COGS"

    def test_napa_is_cogs(self):
        txn = self._make_txn("NAPA Auto Parts #500")
        self.engine.categorize(txn)
        assert txn.account_type == "COGS"


class TestCategorizeBatchStats:
    """categorize_batch should report pre_classified and loan_split counts."""

    def test_stats_include_new_layers(self):
        engine = CategorizerEngine(mode="full")
        txns = [
            Transaction(description="Transfer to Savings", direction="DEBIT",
                        amount=Decimal("1000")),
            Transaction(description="Stripe Payout", direction="CREDIT",
                        amount=Decimal("5000")),
            Transaction(description="Random Mystery Charge", direction="DEBIT",
                        amount=Decimal("100")),
        ]
        result = engine.categorize_batch(txns)
        assert "pre_classified" in result
        assert "auto_categorized" in result
        assert result["auto_categorized"] >= result["exact_match"] + result["pattern_match"]
