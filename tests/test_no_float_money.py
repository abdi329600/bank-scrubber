"""
test_no_float_money.py
======================
Guardrail test: D() must reject float inputs to prevent
binary artifacts entering the money pipeline.
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest
from financials.calculator import D, PLStatement


class TestRejectFloat:
    """Floats must never enter the money pipeline via D()."""

    def test_D_rejects_float(self):
        with pytest.raises(TypeError, match="float is forbidden"):
            D(100.10)

    def test_D_rejects_float_negative(self):
        with pytest.raises(TypeError, match="float is forbidden"):
            D(-50.5)

    def test_D_rejects_float_zero(self):
        with pytest.raises(TypeError, match="float is forbidden"):
            D(0.0)


class TestPLStatementCoercion:
    """PLStatement __post_init__ coerces string/int inputs safely."""

    def test_string_inputs_accepted(self):
        pl = PLStatement(period_label="X", gross_revenue="100.00")
        from decimal import Decimal
        assert pl.gross_revenue == Decimal("100.00")

    def test_int_inputs_accepted(self):
        pl = PLStatement(period_label="X", gross_revenue=100)
        from decimal import Decimal
        assert pl.gross_revenue == Decimal("100.00")

    def test_to_dict_never_contains_float(self):
        pl = PLStatement(
            period_label="X",
            gross_revenue="5000.00",
            refunds="100.00",
            rent="500.00",
            interest_expense="50.00",
        )
        d = pl.to_dict()
        for key, val in d.items():
            if key in ("period", "basis", "assumptions", "warnings",
                       "transaction_count", "flagged_count"):
                continue
            assert not isinstance(val, float), \
                f"to_dict()['{key}'] is float ({val}); must be str"
