"""
cogs_engine.py
==============
Inventory-aware COGS computation.

Two modes:
  1. COGS (bank-proxy): purchases from inventory vendors + direct materials
     Cash approximation — labeled clearly as preliminary.
  2. COGS (inventory-based): Beginning Inventory + Purchases - Ending Inventory
     Matches IRS Schedule C COGS section. Requires inventory values.

For consulting "100% right," bank-proxy COGS is preliminary unless
the client provides beginning/ending inventory.
"""

from decimal import Decimal, ROUND_HALF_UP
from typing import Dict, List, Optional
from dataclasses import dataclass, field


def _cents(v) -> Decimal:
    return Decimal(str(v)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


COGS_ACCOUNT_CODES = {"5000", "5100", "5110", "5120", "5130", "5140"}


@dataclass
class COGSResult:
    mode: str = "bank_proxy"          # "bank_proxy" or "inventory_based"
    is_preliminary: bool = True
    cogs_total: Decimal = field(default_factory=lambda: Decimal("0"))
    label: str = ""

    # Bank-proxy fields
    purchases_total: Decimal = field(default_factory=lambda: Decimal("0"))
    direct_materials: Decimal = field(default_factory=lambda: Decimal("0"))
    subcontractor_costs: Decimal = field(default_factory=lambda: Decimal("0"))

    # Inventory-based fields (IRS Schedule C Part III)
    beginning_inventory: Optional[Decimal] = None
    ending_inventory: Optional[Decimal] = None
    purchases_for_period: Decimal = field(default_factory=lambda: Decimal("0"))
    labor_costs: Decimal = field(default_factory=lambda: Decimal("0"))
    materials_supplies: Decimal = field(default_factory=lambda: Decimal("0"))
    other_costs: Decimal = field(default_factory=lambda: Decimal("0"))

    warnings: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict:
        return {
            "mode": self.mode,
            "is_preliminary": self.is_preliminary,
            "cogs_total": str(self.cogs_total),
            "label": self.label,
            "purchases_total": str(self.purchases_total),
            "beginning_inventory": str(self.beginning_inventory) if self.beginning_inventory is not None else None,
            "ending_inventory": str(self.ending_inventory) if self.ending_inventory is not None else None,
            "warnings": self.warnings,
        }


class COGSEngine:
    """
    Computes COGS using two modes. Default is bank-proxy (always available).
    Inventory-based requires explicit inventory values from the client.
    """

    def compute_bank_proxy(self, transactions) -> COGSResult:
        """
        COGS from bank activity only. Preliminary — labeled clearly.
        Sums all debits to COGS account codes as cash-basis proxy.
        """
        result = COGSResult(
            mode="bank_proxy",
            is_preliminary=True,
            label="COGS (Bank-Proxy) — Cash-basis estimate from bank activity. "
                  "Does NOT account for inventory timing. Preliminary until "
                  "inventory values are provided.",
        )

        purchases = Decimal("0")
        materials = Decimal("0")
        subcontractor = Decimal("0")

        for txn in transactions:
            if txn.direction != "DEBIT":
                continue
            code = txn.account_code
            if code in COGS_ACCOUNT_CODES:
                if code in ("5110", "5120"):
                    materials += txn.amount
                elif code == "5130":
                    subcontractor += txn.amount
                else:
                    purchases += txn.amount

        result.purchases_total = _cents(purchases)
        result.direct_materials = _cents(materials)
        result.subcontractor_costs = _cents(subcontractor)
        result.cogs_total = _cents(purchases + materials + subcontractor)

        # Flag if COGS is large relative to no inventory info
        if result.cogs_total > Decimal("0"):
            result.warnings.append(
                "Bank-proxy COGS does not reflect inventory changes. "
                "If business holds inventory, provide beginning/ending "
                "inventory values for accurate COGS."
            )

        return result

    def compute_inventory_based(
        self,
        transactions,
        beginning_inventory: Decimal,
        ending_inventory: Decimal,
        labor_costs: Decimal = Decimal("0"),
        materials_supplies: Decimal = Decimal("0"),
        other_costs: Decimal = Decimal("0"),
    ) -> COGSResult:
        """
        COGS per IRS Schedule C Part III:
        Beginning Inventory + Purchases + Labor + Materials + Other - Ending Inventory
        """
        # Sum purchases from bank
        purchases = Decimal("0")
        for txn in transactions:
            if txn.direction == "DEBIT" and txn.account_code in COGS_ACCOUNT_CODES:
                purchases += txn.amount

        bi = _cents(beginning_inventory)
        ei = _cents(ending_inventory)
        purch = _cents(purchases)
        labor = _cents(labor_costs)
        mats = _cents(materials_supplies)
        other = _cents(other_costs)

        cogs = _cents(bi + purch + labor + mats + other - ei)

        result = COGSResult(
            mode="inventory_based",
            is_preliminary=False,
            cogs_total=cogs,
            label="COGS (Inventory-Based) — Per IRS Schedule C Part III. "
                  "Beginning Inventory + Purchases + Labor + Materials - Ending Inventory.",
            beginning_inventory=bi,
            ending_inventory=ei,
            purchases_for_period=purch,
            labor_costs=labor,
            materials_supplies=mats,
            other_costs=other,
        )

        # Sanity checks
        if cogs < Decimal("0"):
            result.warnings.append(
                "Computed COGS is negative. Verify inventory values and "
                "purchase amounts. Ending inventory may be overstated."
            )
        if ei > bi + purch:
            result.warnings.append(
                "Ending inventory exceeds beginning + purchases. "
                "Verify no inventory was received without a bank transaction."
            )

        return result

    def detect_inventory_spikes(self, transactions, monthly: bool = True) -> List[Dict]:
        """Flag months where inventory purchases spike but sales don't."""
        from collections import defaultdict
        monthly_purchases = defaultdict(lambda: Decimal("0"))
        monthly_revenue = defaultdict(lambda: Decimal("0"))

        for txn in transactions:
            month = txn.date[:7] if txn.date else "unknown"
            if txn.direction == "DEBIT" and txn.account_code in COGS_ACCOUNT_CODES:
                monthly_purchases[month] += txn.amount
            elif txn.direction == "CREDIT" and txn.account_type == "REVENUE":
                monthly_revenue[month] += txn.amount

        alerts = []
        months = sorted(set(list(monthly_purchases.keys()) + list(monthly_revenue.keys())))
        for m in months:
            purch = monthly_purchases[m]
            rev = monthly_revenue[m]
            if purch > Decimal("0") and (rev == Decimal("0") or purch > rev * Decimal("2")):
                alerts.append({
                    "month": m,
                    "purchases": str(purch),
                    "revenue": str(rev),
                    "alert": "Inventory purchases significantly exceed revenue. "
                             "Possible stock build-up or timing difference.",
                })

        return alerts
