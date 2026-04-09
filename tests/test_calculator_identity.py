"""
test_calculator_identity.py
===========================
Deterministic tests for PLStatement: identity holds, margins correct,
string serialization, basis/assumptions disclosure.
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest
from decimal import Decimal
from financials.calculator import PLStatement, D, q_money, q_pct


class TestPLIdentityAndMargins:
    """Known-input fixture where every intermediate value is asserted."""

    def setup_method(self):
        self.pl = PLStatement(
            period_label="March 2026",
            gross_revenue="10000.00",
            refunds="500.00",
            inventory_costs="4000.00",
            direct_labor="0.00",
            rent="2000.00",
            utilities="300.00",
            insurance="200.00",
            marketing="0.00",
            software="100.00",
            bank_fees="50.00",
            other_opex="0.00",
            interest_expense="150.00",
            taxes="0.00",
        )

    def test_net_revenue(self):
        assert self.pl.net_revenue == Decimal("9500.00")

    def test_total_cogs(self):
        assert self.pl.total_cogs == Decimal("4000.00")

    def test_gross_profit(self):
        assert self.pl.gross_profit == Decimal("5500.00")

    def test_total_opex(self):
        assert self.pl.total_opex == Decimal("2650.00")

    def test_operating_income(self):
        assert self.pl.operating_income == Decimal("2850.00")

    def test_net_profit(self):
        assert self.pl.net_profit == Decimal("2700.00")

    def test_gross_margin_pct(self):
        assert self.pl.gross_margin_pct == Decimal("57.89")

    def test_operating_margin_pct(self):
        assert self.pl.operating_margin_pct == Decimal("30.00")

    def test_net_margin_pct(self):
        assert self.pl.net_margin_pct == Decimal("28.42")

    def test_identity_holds(self):
        """MATH_ERROR must never appear in validate()."""
        warnings = self.pl.validate()
        assert not any("MATH_ERROR" in w for w in warnings)

    def test_basis_label_present(self):
        assert self.pl.basis_label == "cash_basis_from_bank_activity"

    def test_to_dict_string_serialization(self):
        d = self.pl.to_dict()
        for key in ("gross_revenue", "net_revenue", "total_cogs", "gross_profit",
                     "total_opex", "operating_income", "net_profit",
                     "interest_expense", "taxes"):
            assert isinstance(d[key], str), f"{key} must be string, got {type(d[key])}"

    def test_to_dict_has_basis_and_assumptions(self):
        d = self.pl.to_dict()
        assert "basis" in d
        assert "assumptions" in d
        assert "warnings" in d

    def test_backward_compat_loan_payments(self):
        """loan_payments property returns interest_expense."""
        assert self.pl.loan_payments == Decimal("150.00")


class TestEdgeCases:
    """Margin suppression, zero revenue, negative scenarios."""

    def test_zero_revenue_margins_suppressed(self):
        pl = PLStatement(period_label="Empty", gross_revenue="0", refunds="0",
                         rent="500.00")
        assert pl.gross_margin_pct == Decimal("0.00")
        assert pl.net_margin_pct == Decimal("0.00")

    def test_negative_revenue_margins_suppressed(self):
        pl = PLStatement(period_label="Refund Month", gross_revenue="100.00",
                         refunds="200.00", rent="50.00")
        # net_revenue = -100, so margins should be 0
        assert pl.net_revenue == Decimal("-100.00")
        assert pl.gross_margin_pct == Decimal("0.00")

    def test_zero_revenue_disclosure_warning(self):
        pl = PLStatement(period_label="X", gross_revenue="0", rent="100.00")
        warnings = pl.validate()
        assert any("DISCLOSURE" in w for w in warnings)

    def test_high_margin_semantic_warning(self):
        pl = PLStatement(period_label="X", gross_revenue="10000.00",
                         inventory_costs="500.00")
        warnings = pl.validate()
        assert any("SEMANTIC" in w and "gross margin" in w for w in warnings)


class TestHelpers:
    """Test D(), q_money(), q_pct() helpers."""

    def test_D_accepts_string(self):
        assert D("123.45") == Decimal("123.45")

    def test_D_accepts_int(self):
        assert D(100) == Decimal("100")

    def test_D_accepts_decimal(self):
        assert D(Decimal("99.99")) == Decimal("99.99")

    def test_q_money_rounds_correctly(self):
        assert q_money(Decimal("1.005")) == Decimal("1.01")
        assert q_money(Decimal("1.004")) == Decimal("1.00")

    def test_q_pct_rounds_correctly(self):
        assert q_pct(Decimal("33.335")) == Decimal("33.34")
