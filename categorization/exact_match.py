"""
exact_match.py
==============
Layer 1: Deterministic exact-match lookup.
These are NEVER wrong — known merchant → known account.
Highest priority in the categorization stack.
"""

from typing import Optional, Dict
from dataclasses import dataclass


@dataclass
class MatchResult:
    rule_id: str
    account: str
    account_name: str
    account_type: str
    confidence: float
    layer: str = "exact_match"
    deductible: bool = True
    irs_ref: str = ""
    flag_note: str = ""


# ═══════════════════════════════════════════════════════════════
#  EXACT MATCH RULES — Deterministic mapping
#  Key = uppercase merchant substring
# ═══════════════════════════════════════════════════════════════

EXACT_MATCH_RULES: Dict[str, Dict] = {
    # ── TAX PAYMENTS ────────────────────────────────────────────
    "IRS EFTPS":              {"account": "2100", "name": "Federal Income Tax Payable",  "type": "LIABILITY"},
    "EFTPS TAX":              {"account": "2100", "name": "Federal Income Tax Payable",  "type": "LIABILITY"},
    "STATE TAX PAYMENT":      {"account": "2110", "name": "State Income Tax Payable",    "type": "LIABILITY"},
    "FRANCHISE TAX":          {"account": "2110", "name": "State Income Tax Payable",    "type": "LIABILITY"},

    # ── PAYROLL PROCESSORS ──────────────────────────────────────
    "ADP PAYROLL":            {"account": "6010", "name": "Payroll Expense",             "type": "EXPENSE"},
    "GUSTO PAYROLL":          {"account": "6010", "name": "Payroll Expense",             "type": "EXPENSE"},
    "GUSTO FEE":              {"account": "6010", "name": "Payroll Processing Fees",     "type": "EXPENSE"},
    "PAYCHEX":                {"account": "6010", "name": "Payroll Expense",             "type": "EXPENSE"},
    "SQUARE PAYROLL":         {"account": "6010", "name": "Payroll Expense",             "type": "EXPENSE"},

    # ── BANKING FEES ────────────────────────────────────────────
    "MONTHLY SERVICE FEE":    {"account": "6300", "name": "Bank Service Charges",        "type": "EXPENSE"},
    "MONTHLY MAINTENANCE":    {"account": "6300", "name": "Bank Service Charges",        "type": "EXPENSE"},
    "OVERDRAFT FEE":          {"account": "6300", "name": "Bank Service Charges",        "type": "EXPENSE"},
    "WIRE TRANSFER FEE":      {"account": "6300", "name": "Bank Service Charges",        "type": "EXPENSE"},
    "NSF FEE":                {"account": "6300", "name": "Bank Service Charges",        "type": "EXPENSE"},
    "ATM FEE":                {"account": "6300", "name": "Bank Service Charges",        "type": "EXPENSE"},
    "FOREIGN TRANSACTION":    {"account": "6300", "name": "Bank Service Charges",        "type": "EXPENSE"},

    # ── INSURANCE (direction-aware: DEBIT=expense, CREDIT=reimbursement) ──
    "PROGRESSIVE INSURANCE":  {"account": "6200", "name": "Insurance Expense",           "type": "EXPENSE", "direction": "DEBIT"},
    "GEICO":                  {"account": "6200", "name": "Insurance Expense",           "type": "EXPENSE", "direction": "DEBIT"},
    "STATE FARM":             {"account": "6200", "name": "Insurance Expense",           "type": "EXPENSE", "direction": "DEBIT"},
    "ALLSTATE":               {"account": "6200", "name": "Insurance Expense",           "type": "EXPENSE", "direction": "DEBIT"},
    "LIBERTY MUTUAL":         {"account": "6200", "name": "Insurance Expense",           "type": "EXPENSE", "direction": "DEBIT"},
    "NATIONWIDE":             {"account": "6200", "name": "Insurance Expense",           "type": "EXPENSE", "direction": "DEBIT"},
    "USAA INSURANCE":         {"account": "6200", "name": "Insurance Expense",           "type": "EXPENSE", "direction": "DEBIT"},

    # ── SOFTWARE / SaaS ────────────────────────────────────────
    "QUICKBOOKS":             {"account": "6400", "name": "Software & Subscriptions",    "type": "EXPENSE"},
    "INTUIT":                 {"account": "6400", "name": "Software & Subscriptions",    "type": "EXPENSE"},
    "ADOBE":                  {"account": "6400", "name": "Software & Subscriptions",    "type": "EXPENSE"},
    "MICROSOFT 365":          {"account": "6400", "name": "Software & Subscriptions",    "type": "EXPENSE"},
    "MICROSOFT OFFICE":       {"account": "6400", "name": "Software & Subscriptions",    "type": "EXPENSE"},
    "GOOGLE WORKSPACE":       {"account": "6400", "name": "Software & Subscriptions",    "type": "EXPENSE"},
    "ZOOM.US":                {"account": "6400", "name": "Software & Subscriptions",    "type": "EXPENSE"},
    "SLACK":                  {"account": "6400", "name": "Software & Subscriptions",    "type": "EXPENSE"},
    "DROPBOX":                {"account": "6400", "name": "Software & Subscriptions",    "type": "EXPENSE"},
    "XERO":                   {"account": "6400", "name": "Software & Subscriptions",    "type": "EXPENSE"},
    "FRESHBOOKS":             {"account": "6400", "name": "Software & Subscriptions",    "type": "EXPENSE"},
    "HUBSPOT":                {"account": "6400", "name": "Software & Subscriptions",    "type": "EXPENSE"},

    # ── AUTO AUCTION (Car Flip) ─────────────────────────────────
    "MANHEIM":                {"account": "5100", "name": "Vehicle Purchases - COGS",    "type": "COGS"},
    "COPART":                 {"account": "5100", "name": "Vehicle Purchases - COGS",    "type": "COGS"},
    "IAAI":                   {"account": "5100", "name": "Vehicle Purchases - COGS",    "type": "COGS"},
    "ADESA":                  {"account": "5100", "name": "Vehicle Purchases - COGS",    "type": "COGS"},

    # ── CREDIT CARD PROCESSING ──────────────────────────────────
    "SQUARE INC":             {"account": "6310", "name": "CC Processing Fees",          "type": "EXPENSE"},
    "STRIPE FEE":             {"account": "6310", "name": "CC Processing Fees",          "type": "EXPENSE"},
    "PAYPAL FEE":             {"account": "6310", "name": "CC Processing Fees",          "type": "EXPENSE"},
    "CLOVER FEE":             {"account": "6310", "name": "CC Processing Fees",          "type": "EXPENSE"},

    # ── REVENUE DEPOSITS (processor payouts) ────────────────
    "SQUARE DEPOSIT":         {"account": "4000", "name": "Sales Revenue",               "type": "REVENUE", "direction": "CREDIT"},
    "SQ *DEPOSIT":            {"account": "4000", "name": "Sales Revenue",               "type": "REVENUE", "direction": "CREDIT"},
    "STRIPE PAYOUT":          {"account": "4000", "name": "Sales Revenue",               "type": "REVENUE", "direction": "CREDIT"},
    "STRIPE TRANSFER":        {"account": "4000", "name": "Sales Revenue",               "type": "REVENUE", "direction": "CREDIT"},
    "SHOPIFY PAYOUT":         {"account": "4000", "name": "Sales Revenue",               "type": "REVENUE", "direction": "CREDIT"},
    "PAYPAL TRANSFER":        {"account": "4000", "name": "Sales Revenue",               "type": "REVENUE", "direction": "CREDIT"},
    "CLOVER DEPOSIT":         {"account": "4000", "name": "Sales Revenue",               "type": "REVENUE", "direction": "CREDIT"},
    "TOAST DEPOSIT":          {"account": "4000", "name": "Sales Revenue",               "type": "REVENUE", "direction": "CREDIT"},

    # ── REVENUE — Direct Customer Receipts (deterministic) ─────
    "POS SALE":               {"account": "4000", "name": "Sales Revenue",               "type": "REVENUE", "direction": "CREDIT"},
    "POS BATCH":              {"account": "4000", "name": "Sales Revenue",               "type": "REVENUE", "direction": "CREDIT"},
    "DAILY SALES":            {"account": "4000", "name": "Sales Revenue",               "type": "REVENUE", "direction": "CREDIT"},
    "CASH DEPOSIT":           {"account": "4000", "name": "Sales Revenue",               "type": "REVENUE",
                               "flag": "Cash deposit — verify this is business revenue", "direction": "CREDIT"},
    "CUSTOMER PAYMENT":       {"account": "4000", "name": "Sales Revenue",               "type": "REVENUE", "direction": "CREDIT"},
    "CUSTOMER PMT":           {"account": "4000", "name": "Sales Revenue",               "type": "REVENUE", "direction": "CREDIT"},
    "CLIENT PAYMENT":         {"account": "4000", "name": "Sales Revenue",               "type": "REVENUE", "direction": "CREDIT"},
    "INVOICE PAYMENT":        {"account": "4000", "name": "Sales Revenue",               "type": "REVENUE", "direction": "CREDIT"},
    "INVOICE PMT":            {"account": "4000", "name": "Sales Revenue",               "type": "REVENUE", "direction": "CREDIT"},
    "SERVICE PAYMENT":        {"account": "4200", "name": "Service Revenue",             "type": "REVENUE", "direction": "CREDIT"},
    "CONSULTING FEE":         {"account": "4300", "name": "Consulting Revenue",          "type": "REVENUE", "direction": "CREDIT"},
    "ZELLE FROM":             {"account": "4000", "name": "Sales Revenue",               "type": "REVENUE", "direction": "CREDIT"},
    "ZELLE PAYMENT":          {"account": "4000", "name": "Sales Revenue",               "type": "REVENUE", "direction": "CREDIT"},
    "VENMO PAYMENT":          {"account": "4000", "name": "Sales Revenue",               "type": "REVENUE", "direction": "CREDIT"},
    "VENMO CASHOUT":          {"account": "4000", "name": "Sales Revenue",               "type": "REVENUE", "direction": "CREDIT"},
    "CHECK DEPOSIT":          {"account": "4000", "name": "Sales Revenue",               "type": "REVENUE",
                               "flag": "Check deposit — verify this is business revenue, not personal", "direction": "CREDIT"},
    "WIRE TRANSFER IN":       {"account": "4000", "name": "Sales Revenue",               "type": "REVENUE", "direction": "CREDIT"},
    "ACH DEPOSIT":            {"account": "4000", "name": "Sales Revenue",               "type": "REVENUE", "direction": "CREDIT"},
    "ACH CREDIT":             {"account": "4000", "name": "Sales Revenue",               "type": "REVENUE", "direction": "CREDIT"},

    # ── CONTRA-EXPENSE — Insurance Reimbursements (NOT revenue) ───
    "INSURANCE CLAIM":        {"account": "4500", "name": "Insurance Reimbursement",     "type": "REVENUE",
                               "flag": "Contra to insurance expense — nets against 6200, not operating revenue", "direction": "CREDIT"},
    "INSURANCE REIMBURSE":    {"account": "4500", "name": "Insurance Reimbursement",     "type": "REVENUE", "direction": "CREDIT"},
    "INSURANCE REFUND":       {"account": "4500", "name": "Insurance Reimbursement",     "type": "REVENUE", "direction": "CREDIT"},
    "INSURANCE PROCEEDS":     {"account": "4500", "name": "Insurance Reimbursement",     "type": "REVENUE", "direction": "CREDIT"},
    "CLAIM PAYMENT":          {"account": "4500", "name": "Insurance Reimbursement",     "type": "REVENUE", "direction": "CREDIT"},
    "CLAIM SETTLEMENT":       {"account": "4500", "name": "Insurance Reimbursement",     "type": "REVENUE", "direction": "CREDIT"},

    # ── CONTRA-EXPENSE — Vendor Refunds (NOT revenue) ──────────
    "VENDOR REFUND":          {"account": "4510", "name": "Vendor Refund",               "type": "REVENUE", "direction": "CREDIT"},
    "VENDOR CREDIT":          {"account": "4510", "name": "Vendor Credit",              "type": "REVENUE", "direction": "CREDIT"},
    "CREDIT MEMO":            {"account": "4510", "name": "Vendor Credit",              "type": "REVENUE", "direction": "CREDIT"},
    "RETURN CREDIT":          {"account": "4510", "name": "Vendor Refund",               "type": "REVENUE", "direction": "CREDIT"},
    "REFUND FROM":            {"account": "4510", "name": "Vendor Refund",               "type": "REVENUE", "direction": "CREDIT"},

    # ── COGS — Food / Supplies Vendors ──────────────────────
    "US FOODS":               {"account": "5000", "name": "COGS - Supplies",             "type": "COGS",
                               "irs_ref": "Schedule C Line 4"},
    "SYSCO":                  {"account": "5000", "name": "COGS - Supplies",             "type": "COGS",
                               "irs_ref": "Schedule C Line 4"},
    "RESTAURANT DEPOT":       {"account": "5000", "name": "COGS - Supplies",             "type": "COGS",
                               "irs_ref": "Schedule C Line 4"},
    "PERFORMANCE FOOD":       {"account": "5000", "name": "COGS - Supplies",             "type": "COGS",
                               "irs_ref": "Schedule C Line 4"},
    "GORDON FOOD":            {"account": "5000", "name": "COGS - Supplies",             "type": "COGS",
                               "irs_ref": "Schedule C Line 4"},

    # ── COGS — Auto Parts (for repair/resale businesses) ──────
    "AUTOZONE":               {"account": "5120", "name": "Parts & Materials - COGS",    "type": "COGS",
                               "irs_ref": "Schedule C Line 4"},
    "NAPA AUTO":              {"account": "5120", "name": "Parts & Materials - COGS",    "type": "COGS",
                               "irs_ref": "Schedule C Line 4"},
    "O'REILLY AUTO":          {"account": "5120", "name": "Parts & Materials - COGS",    "type": "COGS",
                               "irs_ref": "Schedule C Line 4"},
    "ADVANCE AUTO":           {"account": "5120", "name": "Parts & Materials - COGS",    "type": "COGS",
                               "irs_ref": "Schedule C Line 4"},
    "PEP BOYS":               {"account": "5120", "name": "Parts & Materials - COGS",    "type": "COGS",
                               "irs_ref": "Schedule C Line 4"},

    # ── COGS — Direct Labor / Shop Payroll ──────────────────
    "PAYROLL RUN":            {"account": "5000", "name": "Direct Labor - COGS",          "type": "COGS",
                               "irs_ref": "Schedule C Line 4",
                               "flag": "Verify this is production/shop payroll not admin payroll"},
    "SHOP PAYROLL":           {"account": "5000", "name": "Direct Labor - COGS",          "type": "COGS",
                               "irs_ref": "Schedule C Line 4"},
    "DIRECT LABOR":           {"account": "5000", "name": "Direct Labor - COGS",          "type": "COGS",
                               "irs_ref": "Schedule C Line 4"},

    # ── STORAGE & FACILITIES ──────────────────────────────────
    "PUBLIC STORAGE":         {"account": "6100", "name": "Rent & Lease Expense",          "type": "EXPENSE"},
    "EXTRA SPACE":            {"account": "6100", "name": "Rent & Lease Expense",          "type": "EXPENSE"},
    "LIFE STORAGE":           {"account": "6100", "name": "Rent & Lease Expense",          "type": "EXPENSE"},
    "CUBESMART":              {"account": "6100", "name": "Rent & Lease Expense",          "type": "EXPENSE"},
    "UHAUL":                  {"account": "6100", "name": "Rent & Lease Expense",          "type": "EXPENSE"},
    "U-HAUL":                 {"account": "6100", "name": "Rent & Lease Expense",          "type": "EXPENSE"},
    "STORAGE UNIT":           {"account": "6100", "name": "Rent & Lease Expense",          "type": "EXPENSE"},

    # ── CLEANING & MAINTENANCE ─────────────────────────────
    "CLEANING SERVICE":       {"account": "6800", "name": "Other Operating Expense",       "type": "EXPENSE"},
    "JANITORIAL":             {"account": "6800", "name": "Other Operating Expense",       "type": "EXPENSE"},
    "PEST CONTROL":           {"account": "6800", "name": "Other Operating Expense",       "type": "EXPENSE"},
    "TERMINIX":               {"account": "6800", "name": "Other Operating Expense",       "type": "EXPENSE"},
    "ORKIN":                  {"account": "6800", "name": "Other Operating Expense",       "type": "EXPENSE"},
    "WASTE MANAGEMENT":       {"account": "6800", "name": "Other Operating Expense",       "type": "EXPENSE"},
    "REPUBLIC SERVICES":      {"account": "6800", "name": "Other Operating Expense",       "type": "EXPENSE"},

    # ── TELECOM & INTERNET ──────────────────────────────────
    "XFINITY":                {"account": "6110", "name": "Utilities",                     "type": "EXPENSE"},
    "COX COMM":               {"account": "6110", "name": "Utilities",                     "type": "EXPENSE"},
    "CENTURYLINK":            {"account": "6110", "name": "Utilities",                     "type": "EXPENSE"},
    "FRONTIER COMM":          {"account": "6110", "name": "Utilities",                     "type": "EXPENSE"},

    # ── SHIPPING & POSTAGE ──────────────────────────────────
    "USPS":                   {"account": "6360", "name": "Shipping & Postage",            "type": "EXPENSE"},
    "FEDEX":                  {"account": "6360", "name": "Shipping & Postage",            "type": "EXPENSE"},
    "UPS STORE":              {"account": "6360", "name": "Shipping & Postage",            "type": "EXPENSE"},
    "UPS.COM":                {"account": "6360", "name": "Shipping & Postage",            "type": "EXPENSE"},
    "DHL EXPRESS":            {"account": "6360", "name": "Shipping & Postage",            "type": "EXPENSE"},
    "STAMPS.COM":             {"account": "6360", "name": "Shipping & Postage",            "type": "EXPENSE"},
    "PIRATE SHIP":            {"account": "6360", "name": "Shipping & Postage",            "type": "EXPENSE"},

    # ── ACCOUNTING & TAX SERVICES ───────────────────────────
    "H&R BLOCK":              {"account": "6500", "name": "Professional Services",         "type": "EXPENSE"},
    "TURBOTAX":               {"account": "6500", "name": "Professional Services",         "type": "EXPENSE"},
    "CPA":                    {"account": "6500", "name": "Professional Services",         "type": "EXPENSE"},
    "BOOKKEEPER":             {"account": "6500", "name": "Professional Services",         "type": "EXPENSE"},
    "TAX PREPARATION":        {"account": "6500", "name": "Professional Services",         "type": "EXPENSE"},

    # ── FUEL ────────────────────────────────────────────────
    "SHELL OIL":              {"account": "6120", "name": "Vehicle - Fuel",                "type": "EXPENSE"},
    "CHEVRON":                {"account": "6120", "name": "Vehicle - Fuel",                "type": "EXPENSE"},
    "BP PRODUCTS":            {"account": "6120", "name": "Vehicle - Fuel",                "type": "EXPENSE"},
    "EXXONMOBIL":             {"account": "6120", "name": "Vehicle - Fuel",                "type": "EXPENSE"},
    "MARATHON PETRO":         {"account": "6120", "name": "Vehicle - Fuel",                "type": "EXPENSE"},
    "CIRCLE K":               {"account": "6120", "name": "Vehicle - Fuel",                "type": "EXPENSE"},
    "7-ELEVEN":               {"account": "6120", "name": "Vehicle - Fuel",                "type": "EXPENSE"},
    "PILOT TRAVEL":           {"account": "6120", "name": "Vehicle - Fuel",                "type": "EXPENSE"},
    "LOVES TRAVEL":           {"account": "6120", "name": "Vehicle - Fuel",                "type": "EXPENSE"},
    "WAWA":                   {"account": "6120", "name": "Vehicle - Fuel",                "type": "EXPENSE"},
    "RACETRAC":               {"account": "6120", "name": "Vehicle - Fuel",                "type": "EXPENSE"},
    "SPEEDWAY":               {"account": "6120", "name": "Vehicle - Fuel",                "type": "EXPENSE"},
    "COSTCO GAS":             {"account": "6120", "name": "Vehicle - Fuel",                "type": "EXPENSE"},
    "SAMS CLUB FUEL":         {"account": "6120", "name": "Vehicle - Fuel",                "type": "EXPENSE"},

    # ── ADVERTISING ─────────────────────────────────────────
    "FACEBOOK ADS":           {"account": "6450", "name": "Advertising & Marketing",       "type": "EXPENSE"},
    "META PLATFORMS":         {"account": "6450", "name": "Advertising & Marketing",       "type": "EXPENSE"},
    "GOOGLE ADS":             {"account": "6450", "name": "Advertising & Marketing",       "type": "EXPENSE"},
    "YELP ADVERTISING":       {"account": "6450", "name": "Advertising & Marketing",       "type": "EXPENSE"},
    "INDEED":                 {"account": "6450", "name": "Advertising & Marketing",       "type": "EXPENSE"},
    "VISTAPRINT":             {"account": "6450", "name": "Advertising & Marketing",       "type": "EXPENSE"},
    "CONSTANT CONTACT":       {"account": "6450", "name": "Advertising & Marketing",       "type": "EXPENSE"},
    "MAILCHIMP":              {"account": "6450", "name": "Advertising & Marketing",       "type": "EXPENSE"},

    # ── EMPLOYEE PAYROLL PROCESSORS ─────────────────────────
    "ADP PAYROLL":            {"account": "6000", "name": "Salaries & Wages",              "type": "EXPENSE"},
    "GUSTO":                  {"account": "6000", "name": "Salaries & Wages",              "type": "EXPENSE"},
    "PAYCHEX":                {"account": "6000", "name": "Salaries & Wages",              "type": "EXPENSE"},
    "SQUARE PAYROLL":         {"account": "6000", "name": "Salaries & Wages",              "type": "EXPENSE"},
    "HEARTLAND PAYROLL":      {"account": "6000", "name": "Salaries & Wages",              "type": "EXPENSE"},

    # ── CONTRACTOR / LABOR ──────────────────────────────────
    "UPWORK":                 {"account": "6020", "name": "Contract Labor",                "type": "EXPENSE"},
    "FIVERR":                 {"account": "6020", "name": "Contract Labor",                "type": "EXPENSE"},
    "FREELANCER":             {"account": "6020", "name": "Contract Labor",                "type": "EXPENSE"},

    # ── TRANSFERS (balance sheet, not P&L) ──────────────────
    "TRANSFER TO SAVINGS":    {"account": "1020", "name": "Transfer - Savings",           "type": "ASSET"},
    "TRANSFER FROM SAVINGS":  {"account": "1000", "name": "Transfer - Operating",         "type": "ASSET"},
    "ONLINE TRANSFER":        {"account": "1000", "name": "Internal Transfer",            "type": "ASSET",
                               "flag": "Verify this is an internal transfer, not a payment"},

    # ── SALES TAX (liability, not expense) ──────────────────
    "SALES TAX PAYMENT":      {"account": "2120", "name": "Sales Tax Payable",            "type": "LIABILITY"},
    "SALES TAX PMT":          {"account": "2120", "name": "Sales Tax Payable",            "type": "LIABILITY"},

    # ── OWNER TRANSACTIONS ──────────────────────────────
    "OWNER DRAW":             {"account": "3100", "name": "Owner's Draw",                "type": "EQUITY",
                               "deductible": False,
                               "flag": "NOT TAX DEDUCTIBLE — reduces equity not income"},
    "OWNER DISTRIBUTION":     {"account": "3100", "name": "Owner's Draw",                "type": "EQUITY",
                               "deductible": False,
                               "flag": "NOT TAX DEDUCTIBLE — reduces equity not income"},
    "OWNER CONTRIBUTION":     {"account": "3200", "name": "Owner's Contributions",       "type": "EQUITY"},
    "MEMBER DISTRIBUTION":    {"account": "3100", "name": "Owner's Draw",                "type": "EQUITY",
                               "deductible": False,
                               "flag": "NOT TAX DEDUCTIBLE — reduces equity not income"},

    # ── LOAN PAYMENTS (liability reduction) ─────────────────
    "LOAN PAYMENT":           {"account": "2300", "name": "Loan Payable",                "type": "LIABILITY",
                               "deductible": False,
                               "flag": "Split principal vs interest — only interest deductible"},
    "SBA LOAN":               {"account": "2300", "name": "SBA Loan Payable",             "type": "LIABILITY",
                               "deductible": False,
                               "flag": "Split principal vs interest — only interest deductible"},
    "LOAN PROCEED":           {"account": "2300", "name": "Loan Proceeds",               "type": "LIABILITY"},
}


class ExactMatchLayer:
    """Layer 1: Look up merchant against exact-match rules."""

    def __init__(self, extra_rules: Optional[Dict] = None):
        self.rules = dict(EXACT_MATCH_RULES)
        if extra_rules:
            self.rules.update(extra_rules)

    def match(self, description: str, direction: str = "") -> Optional[MatchResult]:
        desc_upper = description.upper().strip()
        # Longest-match-first prevents short generic rules (e.g. "CPA")
        # from stealing more specific merchant matches.
        sorted_rules = sorted(
            self.rules.items(),
            key=lambda item: len(item[0]),
            reverse=True,
        )
        for keyword, rule in sorted_rules:
            if keyword in desc_upper:
                # Check direction constraint if present
                rule_dir = rule.get("direction", "")
                if rule_dir and direction and rule_dir != direction:
                    continue
                return MatchResult(
                    rule_id=keyword,
                    account=rule["account"],
                    account_name=rule["name"],
                    account_type=rule["type"],
                    confidence=0.99,
                    layer="exact_match",
                    deductible=rule.get("deductible", True),
                    irs_ref=rule.get("irs_ref", ""),
                    flag_note=rule.get("flag", ""),
                )
        return None
