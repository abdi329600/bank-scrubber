"""
calculator.py
=============
SOURCE OF TRUTH for all P&L math.
Uses Decimal everywhere — zero float rounding errors.
Every derived value is a @property so it can never go stale.

Blueprintv2: float-rejecting D() constructor, basis_label/assumptions
for disclosure, interest_expense/taxes separated from principal,
string-only serialization (RFC 8259 safe), identity validation.
"""

from dataclasses import dataclass, field
from decimal import Decimal, ROUND_HALF_UP, InvalidOperation
from typing import Dict, List, Optional

MONEY_Q = Decimal("0.01")
PCT_Q = Decimal("0.01")


def D(x) -> Decimal:
    """
    Canonical Decimal constructor: accept Decimal, int, str.
    Reject float to prevent binary artifacts entering the ledger.
    """
    if isinstance(x, float):
        raise TypeError("float is forbidden for money; pass str/int/Decimal")
    if isinstance(x, Decimal):
        return x
    return Decimal(str(x))


def q_money(x: Decimal) -> Decimal:
    """Quantize to 2 decimal places (USD cents)."""
    return x.quantize(MONEY_Q, rounding=ROUND_HALF_UP)


def q_pct(x: Decimal) -> Decimal:
    """Quantize percentage for display (2 decimal places)."""
    return x.quantize(PCT_Q, rounding=ROUND_HALF_UP)


def _cents(value) -> Decimal:
    """Legacy helper — delegates to q_money(D(v))."""
    if isinstance(value, float):
        return q_money(Decimal(str(value)))
    return q_money(D(value))


# Money fields that __post_init__ will coerce + quantize
_MONEY_FIELDS = (
    "gross_revenue", "refunds", "inventory_costs", "direct_labor",
    "rent", "utilities", "insurance", "marketing", "software",
    "bank_fees", "other_opex", "interest_expense", "taxes",
    "uncategorized_income", "uncategorized_expense",
)


@dataclass
class PLStatement:
    period_label: str
    basis_label: str = "cash_basis_from_bank_activity"

    # ═══ REVENUE ═══
    gross_revenue: Decimal = field(default_factory=lambda: Decimal("0"))
    refunds: Decimal = field(default_factory=lambda: Decimal("0"))

    # ═══ COGS ═══
    inventory_costs: Decimal = field(default_factory=lambda: Decimal("0"))
    direct_labor: Decimal = field(default_factory=lambda: Decimal("0"))

    # ═══ OPERATING EXPENSES ═══
    rent: Decimal = field(default_factory=lambda: Decimal("0"))
    utilities: Decimal = field(default_factory=lambda: Decimal("0"))
    insurance: Decimal = field(default_factory=lambda: Decimal("0"))
    marketing: Decimal = field(default_factory=lambda: Decimal("0"))
    software: Decimal = field(default_factory=lambda: Decimal("0"))
    bank_fees: Decimal = field(default_factory=lambda: Decimal("0"))
    other_opex: Decimal = field(default_factory=lambda: Decimal("0"))

    # ═══ BELOW THE LINE ═══
    interest_expense: Decimal = field(default_factory=lambda: Decimal("0"))
    taxes: Decimal = field(default_factory=lambda: Decimal("0"))

    # ═══ UNCATEGORIZED (flagged for review) ═══
    uncategorized_income: Decimal = field(default_factory=lambda: Decimal("0"))
    uncategorized_expense: Decimal = field(default_factory=lambda: Decimal("0"))

    # ─── transaction counts for audit ───
    transaction_count: int = 0
    flagged_count: int = 0

    # ─── disclosure artifacts ───
    assumptions: List[str] = field(default_factory=list)

    def __post_init__(self):
        """Coerce and quantize all money fields once at construction."""
        for f in _MONEY_FIELDS:
            v = getattr(self, f)
            if isinstance(v, float):
                v = Decimal(str(v))
            elif not isinstance(v, Decimal):
                v = Decimal(str(v))
            setattr(self, f, q_money(v))

    @property
    def loan_payments(self) -> Decimal:
        """Backward-compatible alias: interest is the P&L expense."""
        return self.interest_expense

    # ═══════════════════════════════════════════════════════════
    #  CALCULATED FIELDS — derived, never manually set
    # ═══════════════════════════════════════════════════════════

    @property
    def net_revenue(self) -> Decimal:
        return _cents(self.gross_revenue - self.refunds)

    @property
    def total_cogs(self) -> Decimal:
        return _cents(self.inventory_costs + self.direct_labor)

    @property
    def gross_profit(self) -> Decimal:
        return _cents(self.net_revenue - self.total_cogs)

    @property
    def total_opex(self) -> Decimal:
        return _cents(
            self.rent + self.utilities + self.insurance
            + self.marketing + self.software + self.bank_fees
            + self.other_opex
        )

    @property
    def operating_income(self) -> Decimal:
        return _cents(self.gross_profit - self.total_opex)

    @property
    def net_profit(self) -> Decimal:
        return _cents(self.operating_income - self.interest_expense - self.taxes)

    # ═══════════════════════════════════════════════════════════
    #  MARGIN CALCULATIONS
    # ═══════════════════════════════════════════════════════════

    def _pct(self, numerator: Decimal, denominator: Decimal) -> Decimal:
        """Safe margin calc: suppress to 0% if denominator <= 0."""
        if denominator <= 0:
            return Decimal("0.00")
        return q_pct((numerator / denominator) * Decimal("100"))

    @property
    def gross_margin_pct(self) -> Decimal:
        return self._pct(self.gross_profit, self.net_revenue)

    @property
    def operating_margin_pct(self) -> Decimal:
        return self._pct(self.operating_income, self.net_revenue)

    @property
    def net_margin_pct(self) -> Decimal:
        return self._pct(self.net_profit, self.net_revenue)

    @property
    def cogs_pct(self) -> Decimal:
        """COGS as % of net revenue."""
        if self.net_revenue == 0:
            return Decimal("0")
        return _cents((self.total_cogs / self.net_revenue) * 100)

    @property
    def opex_pct(self) -> Decimal:
        """Total OPEX as % of net revenue."""
        if self.net_revenue == 0:
            return Decimal("0")
        return _cents((self.total_opex / self.net_revenue) * 100)

    @property
    def rent_pct(self) -> Decimal:
        """Rent as % of net revenue — critical benchmark metric."""
        if self.net_revenue == 0:
            return Decimal("0")
        return _cents((self.rent / self.net_revenue) * 100)

    # ═══════════════════════════════════════════════════════════
    #  VALIDATION
    # ═══════════════════════════════════════════════════════════

    def validate(self) -> List[str]:
        """
        Cross-check the math. Returns list of warnings
        if something doesn't add up.
        """
        warnings: List[str] = []

        # Core accounting identity (cash-basis P&L view)
        recalc = q_money(
            self.net_revenue - self.total_cogs - self.total_opex
            - self.interest_expense - self.taxes
        )
        if recalc != self.net_profit:
            warnings.append(
                f"MATH_ERROR: recomputed net_profit {recalc} != {self.net_profit}"
            )

        # Refunds exceed gross revenue
        if self.refunds > self.gross_revenue and self.gross_revenue > 0:
            warnings.append(
                "SEMANTIC: refunds exceed gross revenue; check refund classification."
            )

        # Revenue <= 0 with expenses
        if self.net_revenue <= 0 and (self.total_opex > 0 or self.total_cogs > 0):
            warnings.append(
                "DISCLOSURE: net revenue <= 0; margins suppressed to 0%. Review deposits/refunds."
            )

        # Unrealistically high margin
        if self.net_revenue > 0 and self.gross_margin_pct > Decimal("90.00"):
            warnings.append(
                "SEMANTIC: gross margin unusually high; verify COGS categorization."
            )

        # Gross profit can't exceed net revenue
        if self.gross_profit > self.net_revenue:
            warnings.append(
                f"WARNING: Gross profit ${self.gross_profit} "
                f"exceeds net revenue ${self.net_revenue} — check COGS"
            )

        # Operating at a loss
        if self.net_profit < 0:
            warnings.append(
                f"ALERT: Business operating at a loss "
                f"of ${abs(self.net_profit)}"
            )

        # Flagged transactions
        if self.flagged_count > 0:
            pct = round(self.flagged_count / max(self.transaction_count, 1) * 100)
            warnings.append(
                f"REVIEW: {self.flagged_count} of {self.transaction_count} "
                f"transactions ({pct}%) need manual review"
            )

        # Uncategorized amounts
        if self.uncategorized_income > 0:
            warnings.append(
                f"UNCATEGORIZED: ${self.uncategorized_income} income "
                f"could not be auto-classified"
            )
        if self.uncategorized_expense > 0:
            warnings.append(
                f"UNCATEGORIZED: ${self.uncategorized_expense} expenses "
                f"could not be auto-classified"
            )

        return warnings

    # ═══════════════════════════════════════════════════════════
    #  SERIALIZATION
    # ═══════════════════════════════════════════════════════════

    def to_dict(self) -> Dict:
        """String serialization prevents float reintroduction (RFC 8259 safe)."""
        return {
            "period": self.period_label,
            "basis": self.basis_label,
            # Revenue
            "gross_revenue": str(self.gross_revenue),
            "refunds": str(self.refunds),
            "net_revenue": str(self.net_revenue),
            # COGS
            "inventory_costs": str(self.inventory_costs),
            "direct_labor": str(self.direct_labor),
            "total_cogs": str(self.total_cogs),
            # Gross
            "gross_profit": str(self.gross_profit),
            "gross_margin_pct": str(self.gross_margin_pct),
            # OPEX breakdown
            "rent": str(self.rent),
            "utilities": str(self.utilities),
            "insurance": str(self.insurance),
            "marketing": str(self.marketing),
            "software": str(self.software),
            "bank_fees": str(self.bank_fees),
            "other_opex": str(self.other_opex),
            "total_opex": str(self.total_opex),
            # Operating
            "operating_income": str(self.operating_income),
            "operating_margin_pct": str(self.operating_margin_pct),
            # Below the line
            "interest_expense": str(self.interest_expense),
            "taxes": str(self.taxes),
            "net_profit": str(self.net_profit),
            "net_margin_pct": str(self.net_margin_pct),
            # Audit
            "transaction_count": self.transaction_count,
            "flagged_count": self.flagged_count,
            "uncategorized_income": str(self.uncategorized_income),
            "uncategorized_expense": str(self.uncategorized_expense),
            # Disclosure
            "assumptions": self.assumptions,
            "warnings": self.validate(),
        }

    def summary_line(self) -> str:
        """One-line summary for CLI display."""
        status = "PROFIT" if self.net_profit >= 0 else "LOSS"
        return (
            f"{self.period_label}: "
            f"Rev ${self.net_revenue:,.2f}  |  "
            f"GP ${self.gross_profit:,.2f} ({self.gross_margin_pct}%)  |  "
            f"Net ${self.net_profit:,.2f} ({self.net_margin_pct}%)  [{status}]"
        )
