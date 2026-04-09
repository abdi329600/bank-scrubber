"""
chart_of_accounts.py
====================
Master Chart of Accounts reference.
Designed for: Small Business / Self-Employed + Vehicle Resale Operations.
"""

from dataclasses import dataclass
from typing import Dict, Optional


@dataclass
class AccountEntry:
    code: str
    name: str
    account_type: str     # ASSET, LIABILITY, EQUITY, REVENUE, COGS, EXPENSE
    normal_balance: str   # DEBIT or CREDIT
    schedule_c_line: str = ""
    deductible: bool = False
    notes: str = ""


CHART_OF_ACCOUNTS: Dict[str, AccountEntry] = {
    # ═══ ASSETS (1000s) ═══
    "1000": AccountEntry("1000", "Checking Account - Operating",    "ASSET", "DEBIT"),
    "1010": AccountEntry("1010", "Checking Account - Secondary",    "ASSET", "DEBIT"),
    "1020": AccountEntry("1020", "Savings Account",                 "ASSET", "DEBIT"),
    "1030": AccountEntry("1030", "Petty Cash",                      "ASSET", "DEBIT"),
    "1100": AccountEntry("1100", "Accounts Receivable",             "ASSET", "DEBIT"),
    "1200": AccountEntry("1200", "Inventory - Vehicles Held for Sale", "ASSET", "DEBIT",
                         notes="Car flip specific"),
    "1201": AccountEntry("1201", "Inventory - Parts & Materials",   "ASSET", "DEBIT",
                         notes="Car flip specific"),
    "1300": AccountEntry("1300", "Prepaid Insurance",               "ASSET", "DEBIT"),
    "1310": AccountEntry("1310", "Prepaid Expenses - Other",        "ASSET", "DEBIT"),
    "1500": AccountEntry("1500", "Vehicles & Equipment",            "ASSET", "DEBIT"),
    "1510": AccountEntry("1510", "Accum Depreciation - Vehicles",   "ASSET", "CREDIT",
                         notes="Contra asset"),
    "1520": AccountEntry("1520", "Office Equipment",                "ASSET", "DEBIT"),
    "1530": AccountEntry("1530", "Accum Depreciation - Equipment",  "ASSET", "CREDIT",
                         notes="Contra asset"),
    "1600": AccountEntry("1600", "Security Deposits",               "ASSET", "DEBIT"),

    # ═══ LIABILITIES (2000s) ═══
    "2000": AccountEntry("2000", "Accounts Payable",                "LIABILITY", "CREDIT"),
    "2100": AccountEntry("2100", "Federal Income Tax Payable",      "LIABILITY", "CREDIT"),
    "2110": AccountEntry("2110", "State Income Tax Payable",        "LIABILITY", "CREDIT"),
    "2120": AccountEntry("2120", "Sales Tax Payable",               "LIABILITY", "CREDIT"),
    "2130": AccountEntry("2130", "Payroll Tax Payable",             "LIABILITY", "CREDIT"),
    "2200": AccountEntry("2200", "Credit Card Payable",             "LIABILITY", "CREDIT"),
    "2300": AccountEntry("2300", "Short-Term Loans Payable",        "LIABILITY", "CREDIT"),
    "2400": AccountEntry("2400", "Long-Term Loans Payable",         "LIABILITY", "CREDIT"),
    "2500": AccountEntry("2500", "Deferred Revenue",                "LIABILITY", "CREDIT"),

    # ═══ EQUITY (3000s) ═══
    "3000": AccountEntry("3000", "Owner's Equity / Retained Earnings", "EQUITY", "CREDIT"),
    "3100": AccountEntry("3100", "Owner's Draw / Distributions",    "EQUITY", "DEBIT",
                         notes="NOT an expense — reduces equity"),
    "3200": AccountEntry("3200", "Owner's Contributions",           "EQUITY", "CREDIT"),
    "3900": AccountEntry("3900", "Current Year Net Income",         "EQUITY", "CREDIT"),

    # ═══ REVENUE (4000s) ═══
    "4000": AccountEntry("4000", "Sales Revenue - General",         "REVENUE", "CREDIT",
                         schedule_c_line="Line 1"),
    "4100": AccountEntry("4100", "Vehicle Sales Revenue",           "REVENUE", "CREDIT",
                         schedule_c_line="Line 1", notes="Car flip specific"),
    "4200": AccountEntry("4200", "Service Revenue",                 "REVENUE", "CREDIT",
                         schedule_c_line="Line 1"),
    "4300": AccountEntry("4300", "Consulting Revenue",              "REVENUE", "CREDIT",
                         schedule_c_line="Line 1"),
    "4500": AccountEntry("4500", "Insurance Reimbursements",          "REVENUE", "CREDIT",
                         schedule_c_line="Line 6",
                         notes="Contra to insurance expense — not operating revenue"),
    "4510": AccountEntry("4510", "Vendor Refunds & Credits",           "REVENUE", "CREDIT",
                         schedule_c_line="Line 6",
                         notes="Contra-expense: refunds from vendors"),
    "4520": AccountEntry("4520", "Other Reimbursements",               "REVENUE", "CREDIT",
                         schedule_c_line="Line 6",
                         notes="Non-operating reimbursements"),
    "4900": AccountEntry("4900", "Other Income / Miscellaneous",    "REVENUE", "CREDIT",
                         schedule_c_line="Line 6"),

    # ═══ COST OF GOODS SOLD (5000s) ═══
    "5000": AccountEntry("5000", "COGS - General",                  "COGS", "DEBIT",
                         schedule_c_line="Line 4", deductible=True),
    "5100": AccountEntry("5100", "Vehicle Purchase Cost",           "COGS", "DEBIT",
                         schedule_c_line="Line 4", deductible=True,
                         notes="Auction price paid"),
    "5110": AccountEntry("5110", "Vehicle Acquisition Fees",        "COGS", "DEBIT",
                         schedule_c_line="Line 4", deductible=True,
                         notes="Buyer's fee, transport"),
    "5120": AccountEntry("5120", "Vehicle Repair Costs - COGS",     "COGS", "DEBIT",
                         schedule_c_line="Line 4", deductible=True,
                         notes="Repairs before resale"),
    "5130": AccountEntry("5130", "Vehicle Detailing & Prep - COGS", "COGS", "DEBIT",
                         schedule_c_line="Line 4", deductible=True),
    "5140": AccountEntry("5140", "Title & Registration Fees - COGS","COGS", "DEBIT",
                         schedule_c_line="Line 4", deductible=True),

    # ═══ OPERATING EXPENSES (6000s) ═══
    "6000": AccountEntry("6000", "Salaries & Wages",                "EXPENSE", "DEBIT",
                         schedule_c_line="Line 26", deductible=True),
    "6010": AccountEntry("6010", "Payroll Processing Fees",         "EXPENSE", "DEBIT",
                         schedule_c_line="Line 27", deductible=True),
    "6020": AccountEntry("6020", "Contract Labor / 1099 Workers",   "EXPENSE", "DEBIT",
                         schedule_c_line="Line 11", deductible=True),
    "6100": AccountEntry("6100", "Rent & Lease Expense",            "EXPENSE", "DEBIT",
                         schedule_c_line="Line 20b", deductible=True),
    "6110": AccountEntry("6110", "Utilities",                       "EXPENSE", "DEBIT",
                         schedule_c_line="Line 25", deductible=True),
    "6120": AccountEntry("6120", "Auto & Fuel Expense",             "EXPENSE", "DEBIT",
                         schedule_c_line="Line 9", deductible=True),
    "6125": AccountEntry("6125", "Vehicle Repairs - Operating",     "EXPENSE", "DEBIT",
                         schedule_c_line="Line 9", deductible=True),
    "6130": AccountEntry("6130", "Vehicle Insurance",               "EXPENSE", "DEBIT",
                         schedule_c_line="Line 15", deductible=True),
    "6140": AccountEntry("6140", "Travel Expense",                  "EXPENSE", "DEBIT",
                         schedule_c_line="Line 24a", deductible=True),
    "6150": AccountEntry("6150", "Meals & Entertainment",           "EXPENSE", "DEBIT",
                         schedule_c_line="Line 24b", deductible=True,
                         notes="Only 50% deductible per IRS"),
    "6200": AccountEntry("6200", "Insurance - General Business",    "EXPENSE", "DEBIT",
                         schedule_c_line="Line 15", deductible=True),
    "6210": AccountEntry("6210", "Health Insurance",                "EXPENSE", "DEBIT",
                         schedule_c_line="Line 14", deductible=True),
    "6300": AccountEntry("6300", "Bank Service Charges & Fees",     "EXPENSE", "DEBIT",
                         schedule_c_line="Line 27", deductible=True),
    "6310": AccountEntry("6310", "Credit Card Processing Fees",     "EXPENSE", "DEBIT",
                         schedule_c_line="Line 10", deductible=True),
    "6350": AccountEntry("6350", "Office Supplies",                 "EXPENSE", "DEBIT",
                         schedule_c_line="Line 22", deductible=True),
    "6360": AccountEntry("6360", "Postage & Shipping",              "EXPENSE", "DEBIT",
                         schedule_c_line="Line 18", deductible=True),
    "6400": AccountEntry("6400", "Software & Subscriptions",        "EXPENSE", "DEBIT",
                         schedule_c_line="Line 27", deductible=True),
    "6410": AccountEntry("6410", "Computer & Technology",           "EXPENSE", "DEBIT",
                         schedule_c_line="Line 27", deductible=True),
    "6450": AccountEntry("6450", "Advertising & Marketing",         "EXPENSE", "DEBIT",
                         schedule_c_line="Line 8", deductible=True),
    "6500": AccountEntry("6500", "Professional Fees (Legal, CPA)",  "EXPENSE", "DEBIT",
                         schedule_c_line="Line 17", deductible=True),
    "6510": AccountEntry("6510", "Licenses & Permits",              "EXPENSE", "DEBIT",
                         schedule_c_line="Line 23", deductible=True),
    "6600": AccountEntry("6600", "Depreciation Expense",            "EXPENSE", "DEBIT",
                         schedule_c_line="Line 13", deductible=True),
    "6700": AccountEntry("6700", "Interest Expense",                "EXPENSE", "DEBIT",
                         schedule_c_line="Line 16", deductible=True),
    "6800": AccountEntry("6800", "Bad Debt Expense",                "EXPENSE", "DEBIT",
                         schedule_c_line="Line 27", deductible=True),
    "6900": AccountEntry("6900", "Miscellaneous Expense",           "EXPENSE", "DEBIT",
                         schedule_c_line="Line 27", deductible=True,
                         notes="Flag-heavy account — review all entries"),
    "9000": AccountEntry("9000", "Suspense / Unclassified",          "EXPENSE", "DEBIT",
                         notes="Temporary holding — must be reclassified before close"),
}


def get_account(code: str) -> Optional[AccountEntry]:
    return CHART_OF_ACCOUNTS.get(code)
