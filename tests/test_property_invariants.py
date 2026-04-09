"""
test_property_invariants.py
===========================
Property-based tests: generate random transactions and assert
invariants always hold (identity never breaks, JEs always balance).
Uses hypothesis if available, falls back to manual random if not.
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import random
from decimal import Decimal
from financials.calculator import PLStatement, q_money

try:
    from hypothesis import given, strategies as st, settings
    HAS_HYPOTHESIS = True
except ImportError:
    HAS_HYPOTHESIS = False

import pytest


# ── Manual property tests (always run) ────────────────────────

class TestManualPropertyInvariants:
    """Manually-generated random inputs to verify identity always holds."""

    def _random_pl(self, seed):
        rng = random.Random(seed)
        def rmoney():
            return str(Decimal(rng.randint(0, 100000)) / Decimal(100))

        return PLStatement(
            period_label=f"Seed-{seed}",
            gross_revenue=rmoney(),
            refunds=rmoney(),
            inventory_costs=rmoney(),
            direct_labor=rmoney(),
            rent=rmoney(),
            utilities=rmoney(),
            insurance=rmoney(),
            marketing=rmoney(),
            software=rmoney(),
            bank_fees=rmoney(),
            other_opex=rmoney(),
            interest_expense=rmoney(),
            taxes=rmoney(),
        )

    def test_identity_holds_100_seeds(self):
        """Run 100 random seeds and verify MATH_ERROR never appears."""
        for seed in range(100):
            pl = self._random_pl(seed)
            warnings = pl.validate()
            math_errors = [w for w in warnings if "MATH_ERROR" in w]
            assert not math_errors, f"Seed {seed}: {math_errors}"

    def test_net_profit_equals_formula(self):
        """Verify net_profit = net_revenue - cogs - opex - interest - taxes."""
        for seed in range(50):
            pl = self._random_pl(seed)
            expected = q_money(
                pl.net_revenue - pl.total_cogs - pl.total_opex
                - pl.interest_expense - pl.taxes
            )
            assert pl.net_profit == expected, f"Seed {seed}: {pl.net_profit} != {expected}"

    def test_margins_never_exceed_bounds_for_positive_revenue(self):
        """If net_revenue > 0, gross_margin_pct should be <= 100 when cogs >= 0."""
        for seed in range(50):
            pl = self._random_pl(seed)
            if pl.net_revenue > 0 and pl.total_cogs >= 0:
                # gross_profit = net_revenue - cogs, so margin <= 100%
                assert pl.gross_margin_pct <= Decimal("100.01"), \
                    f"Seed {seed}: margin {pl.gross_margin_pct}%"

    def test_to_dict_all_money_fields_are_strings(self):
        """No float values in serialized output."""
        for seed in range(20):
            pl = self._random_pl(seed)
            d = pl.to_dict()
            for key, val in d.items():
                if key in ("period", "basis", "assumptions", "warnings",
                           "transaction_count", "flagged_count"):
                    continue
                assert not isinstance(val, float), \
                    f"Seed {seed}: to_dict()['{key}'] is float"


# ── Hypothesis property tests (run if hypothesis installed) ───

if HAS_HYPOTHESIS:
    _money = st.integers(min_value=0, max_value=10_000_00).map(
        lambda c: Decimal(c) / Decimal(100)
    )

    class TestHypothesisInvariants:
        """Property-based tests using hypothesis."""

        @given(
            rev=_money, refunds=_money, cogs=_money, opex=_money, interest=_money
        )
        @settings(max_examples=200)
        def test_identity_always_holds(self, rev, refunds, cogs, opex, interest):
            pl = PLStatement(
                period_label="P",
                gross_revenue=str(rev),
                refunds=str(refunds),
                inventory_costs=str(cogs),
                direct_labor="0.00",
                rent=str(opex),
                utilities="0.00",
                insurance="0.00",
                marketing="0.00",
                software="0.00",
                bank_fees="0.00",
                other_opex="0.00",
                interest_expense=str(interest),
                taxes="0.00",
            )
            assert all("MATH_ERROR" not in w for w in pl.validate())
