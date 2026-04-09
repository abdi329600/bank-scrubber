"""
pattern_match.py — Layer 2: Keyword pattern matching with IRS refs.
"""
from dataclasses import dataclass
from typing import Optional, List, Dict


@dataclass
class PatternResult:
    rule_id: str
    account: str
    account_name: str
    account_type: str
    confidence: float
    layer: str = "pattern_match"
    deductible: bool = True
    deduction_limit: Optional[float] = None
    irs_ref: str = ""
    flag_note: str = ""


PATTERN_RULES: List[Dict] = [
    {
        "rule_id": "FUEL",
        "patterns": [
            "GAS", "FUEL", "SHELL", "EXXON", "CHEVRON", "BP OIL",
            "SUNOCO", "MARATHON", "VALERO", "CITGO", "SPEEDWAY",
            "PILOT", "LOVES TRAVEL",
        ],
        "account": "6120",
        "name": "Auto & Fuel Expense",
        "type": "EXPENSE",
        "deductible": True,
        "irs_ref": "Schedule C Line 9",
    },
    {
        "rule_id": "MEALS",
        "patterns": [
            "RESTAURANT", "DOORDASH", "UBER EATS", "GRUBHUB",
            "MCDONALD", "STARBUCKS", "CHIPOTLE", "CHICK-FIL-A",
            "DARDEN", "GRILL", "KITCHEN", "CAFE", "PIZZA",
            "SUSHI", "STEAKHOUSE",
        ],
        "account": "6150",
        "name": "Meals & Entertainment",
        "type": "EXPENSE",
        "deductible": True,
        "deduction_limit": 0.50,
        "irs_ref": "IRC Section 274",
        "flag": "Only 50% deductible — CPA verify business purpose",
    },
    {
        "rule_id": "AUTO_REPAIR",
        "patterns": [
            "AUTO REPAIR", "MIDAS", "JIFFY LUBE", "FIRESTONE",
            "PEP BOYS", "AUTOZONE", "O'REILLY", "NAPA AUTO",
            "ADVANCE AUTO", "TRANSMISSION", "MECHANIC",
            "BODY SHOP", "DETAILING", "CAR WASH",
        ],
        "account": "6125",
        "name": "Vehicle Repairs & Maintenance",
        "type": "EXPENSE",
        "deductible": True,
        "irs_ref": "Schedule C Line 9",
    },
    {
        "rule_id": "OFFICE",
        "patterns": [
            "STAPLES", "OFFICE DEPOT", "OFFICEMAX",
        ],
        "account": "6350",
        "name": "Office Supplies",
        "type": "EXPENSE",
        "deductible": True,
        "irs_ref": "Schedule C Line 22",
    },
    {
        "rule_id": "SUBSCRIPTION",
        "patterns": [
            "ANNUAL", "MONTHLY", "SUBSCRIPTION", "RENEWAL",
            "RECURRING", "MEMBERSHIP",
        ],
        "account": "6400",
        "name": "Software & Subscriptions",
        "type": "EXPENSE",
        "deductible": True,
        "confidence_mod": -0.10,
        "irs_ref": "Schedule C Line 27",
        "flag": "Verify this is a business subscription, not personal",
    },
    {
        "rule_id": "RENT",
        "patterns": [
            "RENT", "LEASE PAYMENT", "PROPERTY MANAGEMENT",
            "STORAGE", "EXTRA SPACE", "PUBLIC STORAGE",
            "LIFE STORAGE",
        ],
        "account": "6100",
        "name": "Rent & Lease Expense",
        "type": "EXPENSE",
        "deductible": True,
        "irs_ref": "Schedule C Line 20b",
    },
    {
        "rule_id": "UTILITIES",
        "patterns": [
            "ELECTRIC", "UTILITY", "WATER BILL", "GAS BILL",
            "COMCAST", "AT&T", "VERIZON", "T-MOBILE",
            "SPECTRUM", "DUKE ENERGY",
        ],
        "account": "6110",
        "name": "Utilities",
        "type": "EXPENSE",
        "deductible": True,
        "irs_ref": "Schedule C Line 25",
    },
    {
        "rule_id": "ADVERTISING",
        "patterns": [
            "FACEBOOK ADS", "GOOGLE ADS", "META ADS",
            "INSTAGRAM", "MAILCHIMP", "CONSTANT CONTACT",
            "VISTAPRINT", "CANVA", "MARKETING", "ADVERTISING",
        ],
        "account": "6450",
        "name": "Advertising & Marketing",
        "type": "EXPENSE",
        "deductible": True,
        "irs_ref": "Schedule C Line 8",
    },
    {
        "rule_id": "PROFESSIONAL",
        "patterns": [
            "LAW OFFICE", "ATTORNEY", "LEGAL", "ACCOUNTANT",
            "CPA", "BOOKKEEPING", "CONSULTING", "NOTARY",
        ],
        "account": "6500",
        "name": "Professional Fees",
        "type": "EXPENSE",
        "deductible": True,
        "irs_ref": "Schedule C Line 17",
    },
    {
        "rule_id": "REVENUE",
        "patterns": [
            "ACH DEPOSIT", "WIRE TRANSFER IN", "ZELLE",
            "PAYPAL TRANSFER", "SQUARE DEPOSIT",
            "STRIPE PAYOUT", "VENMO",
        ],
        "account": "4000",
        "name": "Sales Revenue",
        "type": "REVENUE",
        "direction": "CREDIT",
        "flag": "Verify this is business revenue not a personal transfer",
    },
    {
        "rule_id": "LOAN",
        "patterns": [
            "LOAN PAYMENT", "SBA LOAN", "LINE OF CREDIT",
            "NOTE PAYMENT", "EQUIPMENT FINANCING",
            "MERCHANT ADVANCE",
        ],
        "account": "2300",
        "name": "Loan Payment",
        "type": "LIABILITY",
        "deductible": False,
        "flag": "Split principal vs interest — only interest deductible",
    },
    {
        "rule_id": "INSURANCE",
        "patterns": [
            "INSURANCE", "LIABILITY", "WORKERS COMP",
            "GENERAL LIABILITY",
        ],
        "account": "6200",
        "name": "Insurance - General",
        "type": "EXPENSE",
        "deductible": True,
        "irs_ref": "Schedule C Line 15",
    },
    {
        "rule_id": "TRAVEL",
        "patterns": [
            "AIRLINE", "DELTA", "UNITED", "SOUTHWEST",
            "AMERICAN AIR", "HOTEL", "MARRIOTT", "HILTON",
            "AIRBNB", "UBER", "LYFT",
        ],
        "account": "6140",
        "name": "Travel Expense",
        "type": "EXPENSE",
        "deductible": True,
        "irs_ref": "Schedule C Line 24a",
    },
    {
        "rule_id": "SHIPPING",
        "patterns": [
            "USPS", "UPS", "FEDEX", "DHL", "POSTAGE", "SHIPPING",
        ],
        "account": "6360",
        "name": "Postage & Shipping",
        "type": "EXPENSE",
        "deductible": True,
        "irs_ref": "Schedule C Line 18",
    },
    {
        "rule_id": "LICENSES",
        "patterns": [
            "LICENSE", "PERMIT", "REGISTRATION",
            "DMV", "SECRETARY OF STATE",
        ],
        "account": "6510",
        "name": "Licenses & Permits",
        "type": "EXPENSE",
        "deductible": True,
        "irs_ref": "Schedule C Line 23",
    },
]


# ── Ambiguous vendor heuristics (amount-based) ──────────────────
# These vendors sell everything. Use amount to make a reasonable guess.
# Map vendor aliases to their heuristic tier key
_AMBIGUOUS_ALIASES = {
    "AMAZON": "AMAZON", "AMZN": "AMAZON", "AMZN MKTP": "AMAZON", "AMAZON.COM": "AMAZON",
    "WALMART": "WALMART", "WAL-MART": "WALMART", "WM SUPERCENTER": "WALMART",
    "TARGET": "TARGET",
    "BEST BUY": "BEST BUY",
}

AMBIGUOUS_VENDOR_HEURISTICS = {
    "AMAZON": [
        # (max_amount, account, name, type, confidence, flag)
        (20,    "6350", "Office Supplies",           "EXPENSE", 0.72, "Amazon < $20 — likely supplies"),
        (100,   "6350", "Office Supplies",           "EXPENSE", 0.68, "Amazon $20-$100 — likely supplies, verify receipt"),
        (500,   "6410", "Computer & Technology",     "EXPENSE", 0.60, "Amazon $100-$500 — possibly tech, verify receipt"),
        (99999, "6900", "Miscellaneous Expense",     "EXPENSE", 0.40, "Amazon > $500 — could be equipment, verify receipt"),
    ],
    "WALMART": [
        (30,    "6350", "Office Supplies",           "EXPENSE", 0.70, "Walmart < $30 — likely supplies"),
        (200,   "6350", "Office Supplies",           "EXPENSE", 0.60, "Walmart $30-$200 — likely supplies, verify receipt"),
        (99999, "6900", "Miscellaneous Expense",     "EXPENSE", 0.40, "Walmart > $200 — verify receipt for category"),
    ],
    "TARGET": [
        (50,    "6350", "Office Supplies",           "EXPENSE", 0.65, "Target < $50 — likely supplies"),
        (99999, "6900", "Miscellaneous Expense",     "EXPENSE", 0.40, "Target > $50 — verify receipt"),
    ],
    "BEST BUY": [
        (200,   "6410", "Computer & Technology",     "EXPENSE", 0.75, "Best Buy < $200 — likely tech/accessories"),
        (2500,  "6410", "Computer & Technology",     "EXPENSE", 0.70, "Best Buy $200-$2500 — computer/equipment"),
        (99999, "6410", "Computer & Technology",     "EXPENSE", 0.55, "Best Buy > $2500 — possible capex, verify"),
    ],
}


class PatternMatchLayer:
    """Layer 2: Walk description against keyword pattern rules."""

    def __init__(self, extra_rules: Optional[List[Dict]] = None):
        self.rules = list(PATTERN_RULES)
        if extra_rules:
            self.rules.extend(extra_rules)

    def match(self, description: str, amount: float = 0) -> Optional[PatternResult]:
        desc_upper = description.upper().strip()
        best: Optional[PatternResult] = None
        best_score = 0.0

        for rule in self.rules:
            hits = sum(1 for p in rule["patterns"] if p in desc_upper)
            if hits == 0:
                continue
            base_conf = 0.85
            conf = min(0.95, base_conf + (hits - 1) * 0.03)
            conf += rule.get("confidence_mod", 0)
            conf = max(0.50, min(0.98, conf))

            if conf > best_score:
                best_score = conf
                best = PatternResult(
                    rule_id=rule["rule_id"],
                    account=rule["account"],
                    account_name=rule["name"],
                    account_type=rule["type"],
                    confidence=round(conf, 3),
                    deductible=rule.get("deductible", True),
                    deduction_limit=rule.get("deduction_limit"),
                    irs_ref=rule.get("irs_ref", ""),
                    flag_note=rule.get("flag", ""),
                )

        # If no standard rule matched, try ambiguous vendor heuristics
        if best is None and amount > 0:
            heuristic = self._match_ambiguous_vendor(desc_upper, amount)
            if heuristic:
                return heuristic

        return best

    def _match_ambiguous_vendor(self, desc_upper: str, amount: float) -> Optional[PatternResult]:
        """Amount-based heuristic for ambiguous vendors (Amazon, Walmart, etc.).
        
        Uses alias map to resolve variants like AMZN MKTP → AMAZON.
        Longest alias checked first to avoid false positives.
        """
        # Find which vendor this description matches (longest alias first)
        sorted_aliases = sorted(_AMBIGUOUS_ALIASES.keys(), key=len, reverse=True)
        matched_vendor = None
        for alias in sorted_aliases:
            if alias in desc_upper:
                matched_vendor = _AMBIGUOUS_ALIASES[alias]
                break

        if not matched_vendor or matched_vendor not in AMBIGUOUS_VENDOR_HEURISTICS:
            return None

        tiers = AMBIGUOUS_VENDOR_HEURISTICS[matched_vendor]
        for max_amt, account, name, acct_type, conf, flag in tiers:
            if amount <= max_amt:
                return PatternResult(
                    rule_id=f"HEURISTIC_{matched_vendor}",
                    account=account,
                    account_name=name,
                    account_type=acct_type,
                    confidence=round(conf, 3),
                    layer="pattern_match",
                    deductible=True,
                    flag_note=flag,
                )
        return None
