"""
Benchmark-style categorization accuracy test on a labeled fixture dataset.

Goal: keep account-code accuracy at or above 90% on representative transactions.
"""

import json
from decimal import Decimal
from pathlib import Path

from engine.transaction import Transaction
from categorization.categorizer_engine import CategorizerEngine


FIXTURE_PATH = Path(__file__).parent / "fixtures" / "categorization_benchmark.json"
MIN_ACCURACY = 0.90


def _load_fixture():
    return json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))


def test_categorization_accuracy_benchmark():
    rows = _load_fixture()
    txns = [
        Transaction(
            description=row["description"],
            direction=row["direction"],
            amount=Decimal(row["amount"]),
            date="2026-04-01",
        )
        for row in rows
    ]

    engine = CategorizerEngine(mode="full", client_id="accuracy_benchmark")
    engine.categorize_batch(txns)

    correct = 0
    mismatches = []
    for row, txn in zip(rows, txns):
        expected = row["expected_account_code"]
        actual = txn.account_code
        if actual == expected:
            correct += 1
        else:
            mismatches.append(
                f"{txn.description}: expected {expected}, got {actual} (layer={txn.categorization_layer})"
            )

    accuracy = correct / len(rows)

    assert accuracy >= MIN_ACCURACY, (
        f"Categorization accuracy {accuracy:.1%} below target {MIN_ACCURACY:.0%}. "
        f"Mismatches ({len(mismatches)}): {mismatches}"
    )
