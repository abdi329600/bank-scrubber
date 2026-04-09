"""
categorizer.py
==============
Reads transactions and buckets them using the rules in
config/categories.json. Anything it can't match is flagged
for your manual review.

100% local — no network calls.
"""

import json
from pathlib import Path
from decimal import Decimal
from dataclasses import dataclass, field
from typing import Optional, List, Dict


@dataclass
class Transaction:
    date: str
    description: str
    amount: Decimal
    transaction_type: str          # 'credit' or 'debit'
    category: Optional[str] = None
    subcategory: Optional[str] = None
    confidence: str = "unprocessed"  # 'auto', 'manual', 'flagged', 'unprocessed'


class TransactionCategorizer:
    """
    Walks each transaction through the keyword rule sets.
    Rules are loaded from categories.json so you can tune
    them per client without touching code.
    """

    def __init__(self, categories_path: str = "config/categories.json"):
        self.categories_path = categories_path
        self.rules = self._load_rules(categories_path)

    def _load_rules(self, path: str) -> Dict:
        try:
            return json.loads(Path(path).read_text(encoding="utf-8"))
        except (FileNotFoundError, json.JSONDecodeError):
            print(f"[WARN] Could not load {path} — using empty rules")
            return {}

    def reload_rules(self) -> None:
        """Hot-reload after editing categories.json."""
        self.rules = self._load_rules(self.categories_path)

    # ── Single transaction ──────────────────────────────────────

    def categorize(self, transaction: Transaction) -> Transaction:
        """Match a single transaction against keyword rules."""
        desc = transaction.description.lower()

        # Skip transfers — they're not revenue or expense
        transfers = self.rules.get("transfers", {})
        for _sub, keywords in transfers.items():
            for kw in keywords:
                if kw.lower() in desc:
                    transaction.category = "transfer"
                    transaction.subcategory = "internal"
                    transaction.confidence = "auto"
                    return transaction

        # Walk through rule sets
        for category, subcategories in self.rules.items():
            if category == "transfers":
                continue
            for subcategory, keywords in subcategories.items():
                for keyword in keywords:
                    if keyword.lower() in desc:
                        transaction.category = category
                        transaction.subcategory = subcategory
                        transaction.confidence = "auto"
                        return transaction

        # Fallback — credits → uncategorized revenue, debits → uncategorized expense
        if transaction.transaction_type == "credit":
            transaction.category = "revenue"
            transaction.subcategory = "uncategorized_income"
        else:
            transaction.category = "opex"
            transaction.subcategory = "other_opex"

        transaction.confidence = "flagged"
        return transaction

    # ── Batch ───────────────────────────────────────────────────

    def categorize_batch(self, transactions: List[Transaction]) -> Dict:
        """
        Process all transactions. Returns:
        - categorized list
        - flagged-for-review list
        - counts
        """
        categorized = [self.categorize(t) for t in transactions]

        flagged = [t for t in categorized if t.confidence == "flagged"]
        transfers = [t for t in categorized if t.category == "transfer"]

        return {
            "transactions": categorized,
            "flagged_for_review": flagged,
            "transfers_skipped": transfers,
            "auto_categorized": len(categorized) - len(flagged) - len(transfers),
            "needs_review": len(flagged),
            "total": len(categorized),
        }

    # ── Summary ─────────────────────────────────────────────────

    @staticmethod
    def breakdown(transactions: List[Transaction]) -> Dict:
        """Group transactions by category/subcategory with totals."""
        groups: Dict[str, Dict[str, Decimal]] = {}

        for t in transactions:
            cat = t.category or "uncategorized"
            sub = t.subcategory or "unknown"
            if cat not in groups:
                groups[cat] = {}
            groups[cat][sub] = groups[cat].get(sub, Decimal("0")) + abs(t.amount)

        return {
            cat: {sub: float(amt) for sub, amt in subs.items()}
            for cat, subs in groups.items()
        }
