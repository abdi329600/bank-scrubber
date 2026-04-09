"""
loan_splitter.py
================
Splits loan payments into principal (balance sheet) and interest (P&L expense).
A bank statement line "loan payment" mixes both. Only interest is deductible.
Principal repayment is liability reduction, NOT a P&L expense.

Split priority:
  1. Manual split (API-provided from CPA) — highest trust
  2. Description-extracted interest amount
  3. Amortization schedule lookup by date
  4. Estimated split based on loan type heuristics — lowest trust, flagged
  5. Unsplit fallback — full amount to liability, flagged
"""

import re
from decimal import Decimal, ROUND_HALF_UP
from typing import Dict, List, Optional
from dataclasses import dataclass, field


def _cents(v) -> Decimal:
    return Decimal(str(v)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


LOAN_KEYWORDS = [
    "LOAN", "SBA", "NOTE PAYMENT", "LINE OF CREDIT", "LOC PAYMENT",
    "EQUIPMENT FINANCING", "MERCHANT ADVANCE", "BUSINESS LOAN",
    "INSTALLMENT", "FINANCE CHARGE",
]

INTEREST_KEYWORDS = [
    "INTEREST", "INT CHARGE", "FINANCE CHARGE", "INT PMT",
]

FEE_KEYWORDS = [
    "FEE", "ORIGINATION", "PROCESSING FEE", "LATE FEE", "SERVICE CHARGE",
]

# Typical annual interest rates by loan type (for estimation only)
# These produce approximate splits — always flagged for CPA verification
LOAN_TYPE_RATES = {
    "SBA":        Decimal("0.065"),   # ~6.5% SBA 7(a)
    "EQUIPMENT":  Decimal("0.080"),   # ~8% equipment financing
    "LOC":        Decimal("0.100"),   # ~10% line of credit
    "MERCHANT":   Decimal("0.150"),   # ~15% merchant cash advance (factor rate)
    "GENERIC":    Decimal("0.080"),   # ~8% fallback assumption
}


@dataclass
class LoanSplitResult:
    is_loan: bool = False
    total: Decimal = field(default_factory=lambda: Decimal("0"))
    principal: Optional[Decimal] = None
    interest: Optional[Decimal] = None
    fees: Optional[Decimal] = None
    loan_type: str = ""              # "SBA" / "EQUIPMENT" / "LOC" / "MERCHANT" / "GENERIC"
    split_source: str = ""           # "manual" / "description" / "amortization" / "estimated" / "unsplit"
    needs_manual_split: bool = False
    is_estimated: bool = False       # True if using heuristic rate assumption
    evidence: str = ""


@dataclass
class AmortizationEntry:
    """One row from a loan amortization schedule."""
    date: str
    payment: Decimal
    principal: Decimal
    interest: Decimal
    balance: Decimal


class LoanSplitter:
    """
    Detects loan payments and splits principal vs interest.
    
    Split priority:
      1. Manual splits (provided via API from CPA/user)
      2. Description extraction ("INTEREST $XX.XX")
      3. Amortization schedule lookup
      4. Estimated split using typical rates (flagged)
      5. Unsplit fallback (full amount to liability)
    """

    def __init__(self):
        self.amortization_schedules: Dict[str, List[AmortizationEntry]] = {}
        self.manual_splits: Dict[str, Dict] = {}  # key=description_hash → {principal, interest, fees}

    def add_amortization_schedule(self, loan_id: str, entries: List[AmortizationEntry]):
        """Load an amortization schedule for date-based lookups."""
        self.amortization_schedules[loan_id] = sorted(entries, key=lambda e: e.date)

    def add_manual_split(self, description_pattern: str, principal_pct: Decimal,
                          interest_pct: Decimal, fees_pct: Decimal = Decimal("0")):
        """Register a manual split ratio for a loan description pattern.
        
        Percentages should sum to 1.0 (e.g. 0.70 principal, 0.25 interest, 0.05 fees).
        """
        key = description_pattern.upper().strip()
        self.manual_splits[key] = {
            "principal_pct": principal_pct,
            "interest_pct": interest_pct,
            "fees_pct": fees_pct,
        }

    def _detect_loan_type(self, desc_upper: str) -> str:
        """Determine loan type from description for rate estimation."""
        if "SBA" in desc_upper or "PPP" in desc_upper or "EIDL" in desc_upper:
            return "SBA"
        if "EQUIPMENT" in desc_upper or "EQUIP" in desc_upper:
            return "EQUIPMENT"
        if "LINE OF CREDIT" in desc_upper or "LOC" in desc_upper or "REVOLVING" in desc_upper:
            return "LOC"
        if "MERCHANT" in desc_upper or "ADVANCE" in desc_upper:
            return "MERCHANT"
        return "GENERIC"

    def _extract_fees_from_description(self, desc_upper: str) -> Optional[Decimal]:
        """Try to find fee amount in description."""
        pattern = r"(?:FEE|LATE\s*FEE|SERVICE\s*CHARGE|ORIGINATION)\s*[\$:]?\s*(\d+\.?\d*)"
        match = re.search(pattern, desc_upper)
        if match:
            try:
                return Decimal(match.group(1))
            except Exception:
                return None
        return None

    def analyze(self, description: str, amount: Decimal, date: str = "") -> LoanSplitResult:
        """Analyze a transaction to determine if it's a loan payment and split it."""
        desc_upper = description.upper()
        amt = _cents(amount)

        # Step 1: Is this a loan payment?
        is_loan = any(kw in desc_upper for kw in LOAN_KEYWORDS)
        if not is_loan:
            return LoanSplitResult(is_loan=False, total=amt)

        loan_type = self._detect_loan_type(desc_upper)
        result = LoanSplitResult(is_loan=True, total=amt, loan_type=loan_type)

        # Extract fees if present
        fees = self._extract_fees_from_description(desc_upper)
        if fees:
            result.fees = _cents(fees)

        # Step 2: Check for manual split override (highest priority)
        for pattern, split in self.manual_splits.items():
            if pattern in desc_upper:
                net_amt = amt - (result.fees or Decimal("0"))
                result.principal = _cents(net_amt * split["principal_pct"])
                result.interest = _cents(net_amt * split["interest_pct"])
                if split.get("fees_pct") and not result.fees:
                    result.fees = _cents(net_amt * split["fees_pct"])
                result.split_source = "manual"
                result.evidence = f"Manual split applied: {split['principal_pct']*100:.0f}% principal, {split['interest_pct']*100:.0f}% interest"
                return result

        # Step 3: Try to extract interest from description
        interest_from_desc = self._extract_interest_from_description(desc_upper)
        if interest_from_desc is not None:
            interest = _cents(interest_from_desc)
            net_for_pi = amt - (result.fees or Decimal("0"))
            principal = _cents(net_for_pi - interest)
            result.interest = interest
            result.principal = principal
            result.split_source = "description"
            result.evidence = f"Interest extracted from description: ${interest}"
            return result

        # Step 4: Try amortization schedule lookup
        for loan_id, schedule in self.amortization_schedules.items():
            entry = self._find_amortization_entry(schedule, date, amt)
            if entry:
                result.principal = _cents(entry.principal)
                result.interest = _cents(entry.interest)
                result.split_source = "amortization"
                result.evidence = f"Matched amortization schedule '{loan_id}' for {date}"
                return result

        # Step 5: Estimated split using typical rates (better than nothing)
        rate = LOAN_TYPE_RATES.get(loan_type, LOAN_TYPE_RATES["GENERIC"])
        # Monthly interest estimate: (annual rate / 12) * payment amount
        # For typical amortizing loans, interest portion ≈ rate * remaining_balance / 12
        # Without knowing balance, estimate interest as (annual_rate / 12) * (payment * 12 * 0.6)
        # Simplified: interest_pct ≈ annual_rate * 0.5 for mid-life assumption
        interest_pct = _cents(rate * Decimal("0.5"))
        if interest_pct > Decimal("0.45"):
            interest_pct = Decimal("0.45")  # Cap at 45% to avoid absurd splits
        if interest_pct < Decimal("0.05"):
            interest_pct = Decimal("0.05")  # Floor at 5%

        net_for_pi = amt - (result.fees or Decimal("0"))
        estimated_interest = _cents(net_for_pi * interest_pct)
        estimated_principal = _cents(net_for_pi - estimated_interest)

        result.principal = estimated_principal
        result.interest = estimated_interest
        result.split_source = "estimated"
        result.is_estimated = True
        result.needs_manual_split = True
        result.evidence = (
            f"Estimated split using {loan_type} typical rate ({rate*100:.1f}% annual). "
            f"~{interest_pct*100:.0f}% interest (${estimated_interest}), "
            f"~{(Decimal('1')-interest_pct)*100:.0f}% principal (${estimated_principal}). "
            f"ESTIMATED — provide lender statement for accurate split."
        )
        return result

    def _extract_interest_from_description(self, desc_upper: str) -> Optional[Decimal]:
        """Try to find interest amount in the description text."""
        # Pattern: "INTEREST $XX.XX" or "INT $XX.XX" or "INTEREST: XX.XX"
        pattern = r"(?:INTEREST|INT\s*CHARGE|INT\s*PMT|FINANCE\s*CHARGE)\s*[\$:]?\s*(\d+\.?\d*)"
        match = re.search(pattern, desc_upper)
        if match:
            try:
                return Decimal(match.group(1))
            except Exception:
                return None
        return None

    def _find_amortization_entry(
        self, schedule: List[AmortizationEntry], date: str, amount: Decimal
    ) -> Optional[AmortizationEntry]:
        """Find matching amortization entry by date and amount."""
        tolerance = Decimal("0.50")
        for entry in schedule:
            if entry.date == date and abs(entry.payment - amount) <= tolerance:
                return entry
        # Try amount-only match if date doesn't match exactly
        for entry in schedule:
            if abs(entry.payment - amount) <= tolerance:
                return entry
        return None

    def process_batch(self, transactions) -> Dict:
        """Process all transactions, splitting loans. Returns summary."""
        loan_count = 0
        confirmed_split = 0      # manual / description / amortization
        estimated_split = 0      # heuristic rate assumption
        unsplit_count = 0
        total_interest = Decimal("0")
        total_principal = Decimal("0")
        total_fees = Decimal("0")
        by_type: Dict[str, int] = {}
        by_source: Dict[str, int] = {}

        for txn in transactions:
            if txn.direction != "DEBIT":
                continue

            result = self.analyze(txn.description, txn.amount, txn.date)
            if not result.is_loan:
                continue

            loan_count += 1
            txn.loan_split_source = result.split_source
            txn.loan_type = result.loan_type
            txn.loan_estimated = result.is_estimated

            # Track by type and source
            by_type[result.loan_type] = by_type.get(result.loan_type, 0) + 1
            by_source[result.split_source] = by_source.get(result.split_source, 0) + 1

            if result.fees:
                txn.loan_fees = result.fees
                total_fees += result.fees

            if result.principal is not None and result.interest is not None:
                txn.loan_principal = result.principal
                txn.loan_interest = result.interest
                total_principal += result.principal
                total_interest += result.interest
                if result.is_estimated:
                    estimated_split += 1
                else:
                    confirmed_split += 1
            else:
                txn.loan_principal = result.total
                txn.loan_interest = Decimal("0")
                unsplit_count += 1

            if result.needs_manual_split:
                flag_tag = "LOAN_ESTIMATED_SPLIT" if result.is_estimated else "LOAN_NEEDS_SPLIT"
                if flag_tag not in txn.flags:
                    txn.flags.append(flag_tag)
                    txn.flag_notes.append(result.evidence)

            # Route loan to liability, NOT expense
            txn.account_type = "LIABILITY"
            txn.account_code = "2300"
            txn.account_name = "Loan Payable"

        return {
            "loan_payments_found": loan_count,
            "confirmed_split": confirmed_split,
            "estimated_split": estimated_split,
            "needs_manual_split": unsplit_count,
            "total_principal": str(total_principal),
            "total_interest_expense": str(total_interest),
            "total_fees": str(total_fees),
            "by_loan_type": by_type,
            "by_split_source": by_source,
        }
