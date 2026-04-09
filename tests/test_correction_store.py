"""
test_correction_store.py
========================
Tests for the correction learning system (Phase 4A).
Validates: storage, lookup, confidence compounding, override tracking,
bulk import, and integration with the categorizer engine.
"""
import sys, os
import tempfile
import shutil
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from decimal import Decimal
from engine.correction_store import CorrectionStore, CorrectionRule
from engine.transaction import Transaction
from categorization.categorizer_engine import CategorizerEngine
from categorization.pattern_match import PatternMatchLayer


class TestCorrectionStore:
    """Core correction store operations."""

    def setup_method(self):
        self.tmpdir = tempfile.mkdtemp()
        self.store = CorrectionStore(client_id="test", store_dir=self.tmpdir)

    def teardown_method(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_add_and_match(self):
        self.store.add_correction(
            description="ACME WHOLESALE SUPPLY #1234",
            account_code="5000",
            account_name="COGS - Supplies",
            account_type="COGS",
        )
        result = self.store.match("ACME WHOLESALE SUPPLY #5678")
        assert result.matched is True
        assert result.rule.account_code == "5000"
        assert result.rule.account_type == "COGS"

    def test_confidence_increases_on_confirm(self):
        self.store.add_correction(
            description="MYSTERY VENDOR INC",
            account_code="6350",
            account_name="Office Supplies",
            account_type="EXPENSE",
        )
        base_conf = self.store.rules[list(self.store.rules.keys())[0]].confidence
        # Confirm same correction again
        self.store.add_correction(
            description="MYSTERY VENDOR INC",
            account_code="6350",
            account_name="Office Supplies",
            account_type="EXPENSE",
        )
        new_conf = self.store.rules[list(self.store.rules.keys())[0]].confidence
        assert new_conf >= base_conf

    def test_confidence_decreases_on_override(self):
        self.store.add_correction(
            description="WRONG GUESS CO",
            account_code="6350",
            account_name="Office Supplies",
            account_type="EXPENSE",
        )
        rule_id = list(self.store.rules.keys())[0]
        base_conf = self.store.rules[rule_id].confidence
        self.store.record_override("WRONG GUESS CO")
        new_conf = self.store.rules[rule_id].confidence
        assert new_conf < base_conf

    def test_no_match_returns_false(self):
        result = self.store.match("TOTALLY UNKNOWN VENDOR")
        assert result.matched is False

    def test_persistence(self):
        self.store.add_correction(
            description="PERSISTED VENDOR",
            account_code="6100",
            account_name="Rent",
            account_type="EXPENSE",
        )
        # Reload from disk
        store2 = CorrectionStore(client_id="test", store_dir=self.tmpdir)
        result = store2.match("PERSISTED VENDOR PAYMENT")
        assert result.matched is True
        assert result.rule.account_code == "6100"

    def test_direction_constraint(self):
        self.store.add_correction(
            description="AMBIGUOUS TRANSFER",
            account_code="4000",
            account_name="Sales Revenue",
            account_type="REVENUE",
            direction="CREDIT",
        )
        # Should match credits
        result = self.store.match("AMBIGUOUS TRANSFER RECEIVED", direction="CREDIT")
        assert result.matched is True
        # Should NOT match debits
        result = self.store.match("AMBIGUOUS TRANSFER SENT", direction="DEBIT")
        assert result.matched is False

    def test_bulk_import(self):
        corrections = [
            {"description": "VENDOR A", "account_code": "5000", "account_name": "COGS", "account_type": "COGS"},
            {"description": "VENDOR B", "account_code": "6100", "account_name": "Rent", "account_type": "EXPENSE"},
            {"description": "VENDOR C", "account_code": "6200", "account_name": "Insurance", "account_type": "EXPENSE"},
        ]
        count = self.store.bulk_import(corrections)
        assert count == 3
        assert len(self.store.rules) == 3

    def test_stats(self):
        self.store.add_correction(
            description="STATS TEST",
            account_code="6350",
            account_name="Office",
            account_type="EXPENSE",
        )
        stats = self.store.stats
        assert stats["total_rules"] == 1
        assert stats["high_confidence_rules"] == 1

    def test_longest_match_wins(self):
        """More specific patterns should take priority."""
        self.store.add_correction(
            description="SYSCO",
            account_code="5000",
            account_name="COGS General",
            account_type="COGS",
        )
        self.store.add_correction(
            description="SYSCO FOOD SERVICE DELIVERY",
            account_code="5000",
            account_name="COGS - Food Delivery",
            account_type="COGS",
        )
        result = self.store.match("SYSCO FOOD SERVICE DELIVERY #1234")
        assert result.matched is True
        assert result.rule.account_name == "COGS - Food Delivery"


class TestAmbiguousVendorHeuristics:
    """Amazon/Walmart amount-based heuristic matching."""

    def setup_method(self):
        self.layer = PatternMatchLayer()

    def test_amazon_small_is_supplies(self):
        result = self.layer.match("AMZN MKTP US*ABCD", amount=15.99)
        assert result is not None
        assert result.account == "6350"

    def test_amazon_medium_is_supplies(self):
        result = self.layer.match("AMZN MKTP US*EFGH", amount=89.00)
        assert result is not None
        assert result.account == "6350"

    def test_amazon_large_is_tech(self):
        result = self.layer.match("AMZN MKTP US*IJKL", amount=350.00)
        assert result is not None
        assert result.account == "6410"

    def test_amazon_very_large_is_misc(self):
        result = self.layer.match("AMZN MKTP US*MNOP", amount=1200.00)
        assert result is not None
        assert result.account == "6900"
        assert result.confidence < 0.50

    def test_best_buy_small_is_tech(self):
        result = self.layer.match("BEST BUY #1234", amount=79.00)
        assert result is not None
        assert result.account == "6410"

    def test_walmart_small_is_supplies(self):
        result = self.layer.match("WALMART SUPERCENTER #5678", amount=25.00)
        assert result is not None
        assert result.account == "6350"


class TestCorrectionIntegration:
    """Correction store integrates with categorizer engine."""

    def setup_method(self):
        self.tmpdir = tempfile.mkdtemp()

    def teardown_method(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_learned_rule_fires_in_engine(self):
        # Pre-load a correction
        store = CorrectionStore(client_id="test_int", store_dir=self.tmpdir)
        store.add_correction(
            description="WEIRD LOCAL SHOP XYZ",
            account_code="5120",
            account_name="Parts & Materials - COGS",
            account_type="COGS",
        )

        # Create engine with same client
        engine = CategorizerEngine(mode="full", client_id="test_int")
        # Override the correction store's path
        engine.correction_store = CorrectionStore(client_id="test_int", store_dir=self.tmpdir)

        txn = Transaction(
            description="WEIRD LOCAL SHOP XYZ Purchase #9999",
            direction="DEBIT",
            amount=Decimal("250.00"),
        )
        txn.inflow_type = "OUTFLOW"
        txn.inflow_evidence = "Standard business outflow"
        engine.categorize(txn)

        assert txn.categorization_layer == "learned_match"
        assert txn.account_type == "COGS"
        assert txn.account_code == "5120"
