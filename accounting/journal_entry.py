"""
journal_entry.py
================
Double-entry journal entry generator.
Every transaction produces balanced entries: Total Debits == Total Credits.
"""

import uuid
from dataclasses import dataclass, field
from decimal import Decimal, ROUND_HALF_UP
from typing import List, Dict, Optional

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from engine.transaction import Transaction


def _cents(v) -> Decimal:
    return Decimal(str(v)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


@dataclass
class JournalLine:
    account: str
    account_name: str
    debit: Decimal = field(default_factory=lambda: Decimal("0"))
    credit: Decimal = field(default_factory=lambda: Decimal("0"))
    memo: str = ""
    flag: str = ""

    def to_dict(self) -> Dict:
        return {
            "account": self.account,
            "account_name": self.account_name,
            "debit": str(self.debit),
            "credit": str(self.credit),
            "memo": self.memo,
            "flag": self.flag,
        }


@dataclass
class JournalEntry:
    entry_id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    date: str = ""
    lines: List[JournalLine] = field(default_factory=list)
    source_transaction_id: str = ""
    description: str = ""
    confidence: float = 0.0

    @property
    def total_debits(self) -> Decimal:
        return _cents(sum(l.debit for l in self.lines))

    @property
    def total_credits(self) -> Decimal:
        return _cents(sum(l.credit for l in self.lines))

    @property
    def is_balanced(self) -> bool:
        return self.total_debits == self.total_credits

    def to_dict(self) -> Dict:
        return {
            "entry_id": self.entry_id,
            "date": self.date,
            "description": self.description,
            "lines": [l.to_dict() for l in self.lines],
            "total_debits": str(self.total_debits),
            "total_credits": str(self.total_credits),
            "balanced": self.is_balanced,
            "confidence": self.confidence,
        }


class JournalEntryGenerator:
    """
    Takes categorized transactions and generates proper
    double-entry journal entries.
    """

    def __init__(self, cash_account: str = "1000"):
        self.cash_account = cash_account

    def generate(self, txn: Transaction) -> JournalEntry:
        je = JournalEntry(
            date=txn.date,
            source_transaction_id=txn.transaction_id,
            description=txn.description,
            confidence=txn.confidence_score,
        )

        acct = txn.account_code or "6900"
        acct_name = txn.account_name or "Miscellaneous"
        amt = _cents(txn.amount)
        acct_type = txn.account_type

        # ── EXPENSE paid from bank ──────────────────────────────
        if acct_type == "EXPENSE" and txn.direction == "DEBIT":
            je.lines = [
                JournalLine(acct, acct_name, debit=amt, memo=txn.description),
                JournalLine(self.cash_account, "Checking Account",
                            credit=amt, memo=txn.description),
            ]

        # ── REVENUE received into bank ──────────────────────────
        elif acct_type == "REVENUE" and txn.direction == "CREDIT":
            je.lines = [
                JournalLine(self.cash_account, "Checking Account",
                            debit=amt, memo=txn.description),
                JournalLine(acct, acct_name, credit=amt, memo=txn.description),
            ]

        # ── COGS paid from bank ─────────────────────────────────
        elif acct_type == "COGS" and txn.direction == "DEBIT":
            je.lines = [
                JournalLine(acct, acct_name, debit=amt, memo=txn.description),
                JournalLine(self.cash_account, "Checking Account",
                            credit=amt, memo=txn.description),
            ]

        # ── LIABILITY payment (loan) — split-aware ────────────
        elif acct_type == "LIABILITY" and txn.direction == "DEBIT":
            if txn.loan_interest is not None and txn.loan_principal is not None:
                # Split: principal reduces liability, interest is expense
                principal = _cents(txn.loan_principal)
                interest = _cents(txn.loan_interest)
                fees = _cents(txn.loan_fees) if txn.loan_fees else Decimal("0")
                est_tag = " (ESTIMATED)" if getattr(txn, 'loan_estimated', False) else ""

                je.lines = [
                    JournalLine(acct, acct_name, debit=principal,
                                memo=f"Loan principal{est_tag} - {txn.description}"),
                    JournalLine("6700", "Interest Expense", debit=interest,
                                memo=f"Loan interest{est_tag} - {txn.description}"),
                ]
                if fees > 0:
                    je.lines.append(
                        JournalLine("6300", "Bank Service Charges", debit=fees,
                                    memo=f"Loan fee - {txn.description}")
                    )
                je.lines.append(
                    JournalLine(self.cash_account, "Checking Account",
                                credit=amt, memo=txn.description)
                )
            else:
                # Unsplit: route full amount to liability reduction + flag
                je.lines = [
                    JournalLine(acct, acct_name, debit=amt,
                                memo=txn.description,
                                flag="Unsplit loan payment — principal/interest unknown. "
                                     "Full amount to liability. Interest portion NOT on P&L."),
                    JournalLine(self.cash_account, "Checking Account",
                                credit=amt, memo=txn.description),
                ]

        # ── OWNER'S DRAW (Equity reduction, NOT expense) ────────
        elif acct == "3100":
            je.lines = [
                JournalLine("3100", "Owner's Draw", debit=amt,
                            memo="Owner distribution",
                            flag="NOT TAX DEDUCTIBLE — reduces equity"),
                JournalLine(self.cash_account, "Checking Account",
                            credit=amt, memo="Owner distribution"),
            ]

        # ── OWNER'S CONTRIBUTION ────────────────────────────────
        elif acct == "3200":
            je.lines = [
                JournalLine(self.cash_account, "Checking Account",
                            debit=amt, memo="Owner contribution"),
                JournalLine("3200", "Owner's Contributions",
                            credit=amt, memo="Owner contribution"),
            ]

        # ── ASSET purchase (inventory) ──────────────────────────
        elif acct_type == "ASSET" and txn.direction == "DEBIT":
            je.lines = [
                JournalLine(acct, acct_name, debit=amt, memo=txn.description),
                JournalLine(self.cash_account, "Checking Account",
                            credit=amt, memo=txn.description),
            ]

        # ── Fallback: debit goes to expense, credit from cash ───
        else:
            if txn.direction == "DEBIT":
                je.lines = [
                    JournalLine(acct, acct_name, debit=amt, memo=txn.description),
                    JournalLine(self.cash_account, "Checking Account",
                                credit=amt, memo=txn.description),
                ]
            else:
                je.lines = [
                    JournalLine(self.cash_account, "Checking Account",
                                debit=amt, memo=txn.description),
                    JournalLine(acct, acct_name, credit=amt, memo=txn.description),
                ]

        # Set debit/credit accounts on the transaction
        txn.debit_account = je.lines[0].account if je.lines else ""
        txn.credit_account = je.lines[1].account if len(je.lines) > 1 else ""

        return je

    def generate_batch(self, txns: List[Transaction]) -> List[JournalEntry]:
        entries = []
        for txn in txns:
            je = self.generate(txn)
            if not je.is_balanced:
                txn.flags.append("UNBALANCED_ENTRY")
                txn.flag_notes.append(
                    f"JE {je.entry_id} debits={je.total_debits} "
                    f"credits={je.total_credits}"
                )
            entries.append(je)
        return entries

    def validate_all_balanced(self, entries: List[JournalEntry]) -> bool:
        return all(e.is_balanced for e in entries)
