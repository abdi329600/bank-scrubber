"""
capex_classifier.py
===================
Detects capital expenditures that should NOT be immediately expensed.
IRS: "You generally can't deduct in one year the entire cost of property
that is a capital expenditure; you generally must depreciate it."

Routes large asset-like purchases to fixed assets (balance sheet) and
optionally flags for Section 179 / Bonus Depreciation elections.

De minimis safe harbor: $2,500 threshold (IRS Rev. Proc. 2015-20).
"""

import re
from decimal import Decimal
from typing import Dict, List
from dataclasses import dataclass, field


DE_MINIMIS_THRESHOLD = Decimal("2500")

ASSET_CLASSES = {
    "vehicle": {
        "keywords": [
            "VEHICLE", "CAR", "TRUCK", "VAN", "SUV", "AUTO",
            "COPART", "IAAI", "MANHEIM", "CARMAX", "CARVANA",
            "DEALER", "DMV", "TITLE",
        ],
        "useful_life_years": 5,
        "irs_class": "5-year property",
        "irs_ref": "MACRS 5-year; IRC 179/168(k) eligible",
    },
    "equipment": {
        "keywords": [
            "EQUIPMENT", "MACHINERY", "TOOL", "LIFT", "COMPRESSOR",
            "WELDER", "GENERATOR", "FORKLIFT", "HVAC", "OVEN",
            "MIXER", "REFRIGERATOR", "FREEZER",
        ],
        "useful_life_years": 7,
        "irs_class": "7-year property",
        "irs_ref": "MACRS 7-year; IRC 179/168(k) eligible",
    },
    "computer": {
        "keywords": [
            "COMPUTER", "LAPTOP", "MACBOOK", "IPAD", "SERVER",
            "MONITOR", "PRINTER", "APPLE STORE", "DELL", "LENOVO",
        ],
        "useful_life_years": 5,
        "irs_class": "5-year property",
        "irs_ref": "MACRS 5-year; IRC 179 eligible",
    },
    "furniture": {
        "keywords": [
            "FURNITURE", "DESK", "CHAIR", "SHELVING", "CABINET",
            "OFFICE FURNITURE",
        ],
        "useful_life_years": 7,
        "irs_class": "7-year property",
        "irs_ref": "MACRS 7-year",
    },
    "leasehold": {
        "keywords": [
            "LEASEHOLD", "TENANT IMPROVEMENT", "BUILD OUT",
            "RENOVATION", "REMODEL",
        ],
        "useful_life_years": 15,
        "irs_class": "15-year qualified improvement",
        "irs_ref": "Qualified Improvement Property; 168(k) eligible",
    },
}


@dataclass
class CapexResult:
    is_capex: bool = False
    asset_class: str = ""
    asset_class_info: Dict = field(default_factory=dict)
    amount: Decimal = field(default_factory=lambda: Decimal("0"))
    evidence: str = ""
    recommendation: str = ""
    de_minimis_eligible: bool = False


# ── Descriptions that should NEVER trigger capex ────────────────
CAPEX_EXCLUSIONS = [
    # Payroll
    "PAYROLL", "SALARY", "WAGES", "DIRECT DEPOSIT",
    "ADP", "GUSTO", "PAYCHEX", "SQUARE PAYROLL",
    # Rent / leases
    "RENT", "LEASE PAYMENT", "LEASE PMT", "PROPERTY MANAGEMENT",
    "PROPERTY MGMT", "STORAGE UNIT", "EXTRA SPACE", "PUBLIC STORAGE",
    "LIFE STORAGE",
    # Utilities / telecom
    "UTILITY", "ELECTRIC", "WATER BILL", "GAS BILL", "POWER BILL",
    "COMCAST", "SPECTRUM", "AT&T", "VERIZON", "T-MOBILE",
    "XFINITY", "COX COMM", "CENTURYLINK",
    # Insurance
    "INSURANCE", "PREMIUM", "GEICO", "STATE FARM", "PROGRESSIVE",
    "ALLSTATE", "LIBERTY MUTUAL", "NATIONWIDE", "USAA",
    # Transfers & loans
    "TRANSFER", "XFER", "BETWEEN ACCOUNTS",
    "LOAN PAYMENT", "NOTE PAYMENT", "SBA", "LINE OF CREDIT",
    # Tax
    "TAX PAYMENT", "EFTPS", "FRANCHISE TAX", "SALES TAX",
    # Owner equity
    "OWNER DRAW", "OWNER DISTRIBUTION", "MEMBER DISTRIBUTION",
    # COGS / supplies
    "US FOODS", "SYSCO", "RESTAURANT DEPOT", "GORDON FOOD",
    "PERFORMANCE FOOD",
    # Banking
    "MONTHLY SERVICE FEE", "OVERDRAFT", "NSF FEE", "WIRE FEE",
]


class CapexClassifier:
    """
    Detects capital expenditures and routes them appropriately.
    Anything over de minimis threshold ($2,500) that matches an asset
    class gets flagged for capex treatment instead of immediate expensing.
    
    IMPORTANT: Vendor/description gating runs BEFORE amount check.
    Routine expenses (payroll, rent, utilities, transfers, loans) are
    excluded regardless of amount.
    """

    def __init__(self, threshold: Decimal = DE_MINIMIS_THRESHOLD):
        self.threshold = threshold

    def classify(self, description: str, amount: Decimal, account_type: str = "",
                 account_code: str = "") -> CapexResult:
        """Check if a transaction is a capital expenditure."""
        desc_upper = description.upper()
        amt = amount

        # Only check debits / expenses
        if account_type not in ("EXPENSE", "COGS", ""):
            return CapexResult(is_capex=False, amount=amt)

        # ── EXCLUSION GATE: never flag routine expenses as capex ──
        if any(excl in desc_upper for excl in CAPEX_EXCLUSIONS):
            return CapexResult(is_capex=False, amount=amt)

        # Check against asset class keywords
        matched_class = None
        matched_keywords = []
        for cls_name, cls_info in ASSET_CLASSES.items():
            for kw in cls_info["keywords"]:
                if kw in desc_upper:
                    matched_class = cls_name
                    matched_keywords.append(kw)
                    break
            if matched_class:
                break

        if not matched_class:
            # Only flag very large expenses that passed the exclusion gate
            # AND are not already in a known specific expense category
            # (6900 = misc, empty = uncategorized — those warrant a check)
            known_expense_codes = {
                "6000", "6010", "6020", "6100", "6110", "6120", "6125",
                "6130", "6140", "6150", "6200", "6210", "6300", "6310",
                "6350", "6360", "6400", "6410", "6450", "6500", "6510",
                "6600", "6700", "6800",
                "5000", "5100", "5110", "5120", "5130", "5140",
            }
            if amt > Decimal("10000") and account_code not in known_expense_codes:
                return CapexResult(
                    is_capex=False,
                    amount=amt,
                    evidence="Large expense without asset keyword match (passed exclusion gate)",
                    recommendation=(
                        f"Expense of ${amt} exceeds $10,000 and is not a routine category. "
                        "Verify this is not a capital expenditure that should be depreciated."
                    ),
                )
            return CapexResult(is_capex=False, amount=amt)

        cls_info = ASSET_CLASSES[matched_class]

        # Apply de minimis safe harbor
        if amt <= self.threshold:
            return CapexResult(
                is_capex=False,
                asset_class=matched_class,
                amount=amt,
                de_minimis_eligible=True,
                evidence=(
                    f"Matches asset class '{matched_class}' but ${amt} is at or below "
                    f"de minimis safe harbor (${self.threshold}). May expense immediately."
                ),
                recommendation="Eligible for de minimis safe harbor expensing.",
            )

        return CapexResult(
            is_capex=True,
            asset_class=matched_class,
            asset_class_info=cls_info,
            amount=amt,
            evidence=(
                f"Matches asset class '{matched_class}' (keywords: {matched_keywords}). "
                f"Amount ${amt} exceeds de minimis threshold (${self.threshold})."
            ),
            recommendation=(
                f"Route to Fixed Assets ({cls_info['irs_class']}). "
                f"CPA to evaluate: Section 179 election, Bonus Depreciation (168(k)), "
                f"or standard MACRS over {cls_info['useful_life_years']} years. "
                f"Ref: {cls_info['irs_ref']}"
            ),
        )

    def process_batch(self, transactions) -> Dict:
        """Process all transactions for capex detection."""
        capex_items = []
        de_minimis_items = []
        total_capex = Decimal("0")

        for txn in transactions:
            if txn.direction != "DEBIT":
                continue

            result = self.classify(txn.description, txn.amount, txn.account_type,
                                   getattr(txn, 'account_code', ''))

            if result.is_capex:
                txn.is_capex = True
                txn.capex_asset_class = result.asset_class
                txn.depreciation_eligible = True
                txn.account_type = "ASSET"
                txn.account_code = "1500"
                txn.account_name = f"Fixed Assets - {result.asset_class.title()}"
                total_capex += txn.amount
                capex_items.append({
                    "date": txn.date,
                    "description": txn.description,
                    "amount": str(txn.amount),
                    "asset_class": result.asset_class,
                    "recommendation": result.recommendation,
                })

                if "CAPEX_DETECTED" not in txn.flags:
                    txn.flags.append("CAPEX_DETECTED")
                    txn.flag_notes.append(result.recommendation)

            elif result.de_minimis_eligible:
                de_minimis_items.append({
                    "date": txn.date,
                    "description": txn.description,
                    "amount": str(txn.amount),
                    "asset_class": result.asset_class,
                })

            elif result.recommendation:
                if "LARGE_EXPENSE_REVIEW" not in txn.flags:
                    txn.flags.append("LARGE_EXPENSE_REVIEW")
                    txn.flag_notes.append(result.recommendation)

        return {
            "capex_items": capex_items,
            "capex_count": len(capex_items),
            "total_capex": str(total_capex),
            "de_minimis_items": de_minimis_items,
            "de_minimis_count": len(de_minimis_items),
        }
