"""
package_generator.py
====================
Assembles a complete CPA workpaper package from processed data.
"""

import json
from datetime import datetime
from decimal import Decimal
from pathlib import Path
from typing import List, Dict, Optional

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from engine.transaction import Transaction, TransactionBatch
from accounting.journal_entry import JournalEntry, JournalEntryGenerator
from accounting.trial_balance import TrialBalanceGenerator
from accounting.schedule_c import ScheduleCMapper
from flags.flag_engine import FlagEngine, FLAG_RULES


class CPAReportPackage:
    """
    Generates a complete, professional workpaper package
    that a CPA can immediately work from.
    """

    def __init__(self):
        self.je_gen = JournalEntryGenerator()
        self.tb_gen = TrialBalanceGenerator()
        self.sc_mapper = ScheduleCMapper()
        self.flag_engine = FlagEngine()

    def generate(
        self,
        batch: TransactionBatch,
        business_name: str = "",
        period: str = "",
        output_dir: str = "output",
    ) -> Dict:
        """Full pipeline: JE → TB → P&L → Schedule C → Flags → Package."""

        txns = batch.transactions

        # 1. Generate journal entries
        journal_entries = self.je_gen.generate_batch(txns)
        all_balanced = self.je_gen.validate_all_balanced(journal_entries)

        # 2. Generate trial balance
        trial_balance = self.tb_gen.generate(journal_entries)

        # 3. Build P&L from trial balance
        pnl = self._build_pnl(trial_balance)

        # 4. Schedule C mapping
        schedule_c = self.sc_mapper.map_transactions(txns)

        # 5. Run flag engine
        flag_report = self.flag_engine.flag_batch(batch)

        # 6. Category summary
        category_summary = self._category_summary(txns)

        # 7. Transaction register
        register = self._transaction_register(txns)

        # 8. Audit trail
        audit_trail = self._audit_trail(txns, journal_entries)

        # 9. Cover sheet
        cover = self._cover_sheet(
            business_name, period, batch, trial_balance, flag_report
        )

        # 10. Bank reconciliation
        reconciliation = self._reconciliation(batch)

        package = {
            "cover_sheet": cover,
            "bank_reconciliation": reconciliation,
            "transaction_register": register,
            "trial_balance": trial_balance,
            "profit_and_loss": pnl,
            "schedule_c_map": schedule_c,
            "flagged_items_report": flag_report,
            "category_summary": category_summary,
            "audit_trail": audit_trail,
            "journal_entries_balanced": all_balanced,
            "journal_entry_count": len(journal_entries),
            "generated_at": datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
            "ruleset_version": getattr(batch, 'ruleset_version', '2.4.0'),
            "software_version": "4.1.0",
        }

        # Save JSON package
        out = Path(output_dir)
        out.mkdir(parents=True, exist_ok=True)
        pkg_path = out / "cpa_package.json"
        with open(pkg_path, "w") as f:
            json.dump(package, f, indent=2, default=str)

        package["_saved_to"] = str(pkg_path)
        package["_journal_entries"] = journal_entries
        return package

    def _build_pnl(self, tb: Dict) -> Dict:
        """Extract P&L from trial balance accounts."""
        revenue = Decimal("0")
        cogs = Decimal("0")
        expenses = Decimal("0")
        rev_lines = []
        cogs_lines = []
        exp_lines = []

        for acct in tb.get("accounts", []):
            code = acct["code"]
            net = Decimal(str(acct.get("net_balance", 0)))
            name = acct["name"]
            atype = acct["type"]

            if atype == "REVENUE":
                amt = abs(net)
                revenue += amt
                rev_lines.append({"code": code, "name": name, "amount": str(amt)})
            elif atype == "COGS":
                amt = abs(net)
                cogs += amt
                cogs_lines.append({"code": code, "name": name, "amount": str(amt)})
            elif atype == "EXPENSE":
                amt = abs(net)
                expenses += amt
                exp_lines.append({"code": code, "name": name, "amount": str(amt)})

        gross_profit = revenue - cogs
        net_income = gross_profit - expenses
        gross_margin = (
            str(Decimal(str(gross_profit / revenue * 100)).quantize(Decimal("0.1"))) if revenue else "0.0"
        )

        # Separate interest expense from operating expenses
        interest_total = Decimal("0")
        opex_lines = []
        for l in exp_lines:
            if l["code"] == "6700":
                interest_total += Decimal(l["amount"])
            else:
                opex_lines.append(l)
        opex_total = expenses - interest_total

        return {
            "basis": "cash_basis_from_bank_activity",
            "revenue": {"total": str(revenue), "lines": rev_lines},
            "cogs": {"total": str(cogs), "lines": cogs_lines},
            "gross_profit": str(gross_profit),
            "gross_margin_pct": gross_margin,
            "operating_expenses": {"total": str(opex_total), "lines": opex_lines},
            "interest_expense": str(interest_total),
            "net_income": str(net_income),
            "assumptions": [
                "P&L derived from trial balance rollups (ledger-first).",
                "Cash basis from bank activity; no accrual adjustments.",
                "COGS is bank-proxy only; no inventory adjustments applied.",
            ],
            "warnings": [],
        }

    def _category_summary(self, txns: List[Transaction]) -> Dict:
        from collections import defaultdict
        cats: Dict[str, Dict] = defaultdict(lambda: {
            "count": 0, "total": Decimal("0"), "account": ""
        })
        for t in txns:
            key = t.account_name or "Uncategorized"
            cats[key]["count"] += 1
            cats[key]["total"] += t.amount
            cats[key]["account"] = t.account_code
        # Sort by total descending, serialize totals as strings
        sorted_cats = dict(
            sorted(cats.items(), key=lambda x: x[1]["total"], reverse=True)
        )
        for v in sorted_cats.values():
            v["total"] = str(v["total"])
        return sorted_cats

    def _transaction_register(self, txns: List[Transaction]) -> List[Dict]:
        return [
            {
                "date": t.date,
                "description": t.description,
                "amount": str(t.amount),
                "direction": t.direction,
                "account_code": t.account_code,
                "account_name": t.account_name,
                "confidence": t.confidence_score,
                "flagged": t.is_flagged,
                "flags": t.flags,
            }
            for t in txns
        ]

    def _audit_trail(
        self, txns: List[Transaction], entries: List[JournalEntry]
    ) -> List[Dict]:
        trail = []
        for txn, je in zip(txns, entries):
            trail.append({
                "transaction_id": txn.transaction_id,
                "date": txn.date,
                "description": txn.description,
                "amount": str(txn.amount),
                "categorization_layer": txn.categorization_layer,
                "account_code": txn.account_code,
                "account_name": txn.account_name,
                "confidence": txn.confidence_score,
                "journal_entry_id": je.entry_id,
                "je_balanced": je.is_balanced,
                "flags": txn.flags,
                "flag_notes": txn.flag_notes,
            })
        return trail

    def _cover_sheet(
        self, name: str, period: str, batch: TransactionBatch,
        tb: Dict, flags: Dict,
    ) -> Dict:
        return {
            "business_name": name or "Client",
            "period": period or f"{batch.period_start} to {batch.period_end}",
            "prepared_by": "Financial Document Processing System v4.1",
            "prepared_date": datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
            "source_document": batch.source_document,
            "source_hash": getattr(batch, 'source_hash', ''),
            "document_type": batch.document_type,
            "accounting_method": getattr(batch, 'accounting_method', 'cash'),
            "transaction_count": batch.count,
            "total_debits": str(batch.total_debits),
            "total_credits": str(batch.total_credits),
            "trial_balance_status": "BALANCED" if tb["is_balanced"] else "OUT OF BALANCE",
            "flagged_items": flags.get("flagged_transactions", 0),
            "critical_flags": flags.get("by_severity", {}).get("CRITICAL", 0),
            "ruleset_version": "2.4.0",
            "reviewer_id": "",
            "review_timestamp": "",
            "review_status": "PENDING",
        }

    def _reconciliation(self, batch: TransactionBatch) -> Dict:
        return {
            "beginning_balance": (
                str(batch.beginning_balance) if batch.beginning_balance else None
            ),
            "total_credits": str(batch.total_credits),
            "total_debits": str(batch.total_debits),
            "net_change": str(batch.net_change),
            "ending_balance": (
                str(batch.ending_balance) if batch.ending_balance else None
            ),
            "reconciles": batch.balance_reconciles(),
            "calculated_ending": (
                str(batch.beginning_balance + batch.net_change)
                if batch.beginning_balance is not None else None
            ),
        }
