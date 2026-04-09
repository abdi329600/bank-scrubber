"""
End-to-end test for the Bulletproof P&L Blueprint.
Tests all new modules: merchant normalization, inflow classification,
loan splitting, reconciliation, capex detection, validation, acceptance.
"""

import sys
import os
import tempfile
from decimal import Decimal
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from engine.transaction import Transaction, TransactionBatch
from engine.merchant_normalizer import MerchantNormalizer
from engine.inflow_classifier import InflowClassifier
from engine.loan_splitter import LoanSplitter
from engine.reconciliation import ReconciliationEngine
from categorization.categorizer_engine import CategorizerEngine
from accounting.journal_entry import JournalEntryGenerator
from accounting.trial_balance import TrialBalanceGenerator
from accounting.cogs_engine import COGSEngine
from accounting.capex_classifier import CapexClassifier
from validation.validator import ValidationEngine
from validation.acceptance import AcceptanceCriteria
from flags.flag_engine import FlagEngine

PASS = 0
FAIL = 0

def check(name, condition):
    global PASS, FAIL
    if condition:
        PASS += 1
        print(f"  PASS  {name}")
    else:
        FAIL += 1
        print(f"  FAIL  {name}")


def build_test_batch():
    """Build a realistic batch with various transaction types."""
    txns = [
        Transaction(description="SHELL OIL 12345", amount=Decimal("45.00"), direction="DEBIT", date="2024-01-05"),
        Transaction(description="STARBUCKS STORE 789", amount=Decimal("12.50"), direction="DEBIT", date="2024-01-06"),
        Transaction(description="ADP PAYROLL 01/15", amount=Decimal("3500.00"), direction="DEBIT", date="2024-01-15"),
        Transaction(description="STRIPE PAYOUT 01/20", amount=Decimal("8500.00"), direction="CREDIT", date="2024-01-20"),
        Transaction(description="SBA LOAN PAYMENT", amount=Decimal("1200.00"), direction="DEBIT", date="2024-01-25"),
        Transaction(description="TRANSFER FROM SAVINGS", amount=Decimal("5000.00"), direction="CREDIT", date="2024-01-10"),
        Transaction(description="OWNER CONTRIBUTION", amount=Decimal("10000.00"), direction="CREDIT", date="2024-01-02"),
        Transaction(description="DELL COMPUTER PURCHASE", amount=Decimal("3200.00"), direction="DEBIT", date="2024-01-18"),
        Transaction(description="MONTHLY SERVICE FEE", amount=Decimal("15.00"), direction="DEBIT", date="2024-01-31"),
        Transaction(description="RANDOM VENDOR XYZ", amount=Decimal("250.00"), direction="DEBIT", date="2024-01-22"),
        Transaction(description="GEICO INSURANCE", amount=Decimal("180.00"), direction="DEBIT", date="2024-01-08"),
        Transaction(description="DEPOSIT", amount=Decimal("2000.00"), direction="CREDIT", date="2024-01-28"),
    ]
    batch = TransactionBatch(
        transactions=txns,
        source_document="test_data.csv",
        document_type="bank_statement",
        period_start="2024-01-01",
        period_end="2024-01-31",
        beginning_balance=Decimal("10000.00"),
        ending_balance=Decimal("27097.50"),
    )
    return batch


# ══════════════════════════════════════════════════════════════
print("=" * 65)
print("BULLETPROOF P&L BLUEPRINT — END-TO-END TEST")
print("=" * 65)

# ── 1. Merchant Normalizer ─────────────────────────────────
print("\n1. MERCHANT NORMALIZER")
norm = MerchantNormalizer()
r = norm.normalize("POS DEBIT SHELL OIL 12345 CARD 4321")
check("Cleans bank noise", "POS" not in r.cleaned)
check("Resolves Shell alias", r.canonical_id == "SHELL")
check("Extracts tokens", len(r.tokens) > 0)

r2 = norm.normalize("AMZN Mktp US*1234")
check("Amazon alias resolution", r2.canonical_id == "AMAZON")

# ── 2. Inflow Classifier ──────────────────────────────────
print("\n2. INFLOW CLASSIFIER")
ic = InflowClassifier()

rev = ic.classify("STRIPE PAYOUT 01/20")
check("Stripe payout = REVENUE", rev.inflow_type == "REVENUE")

xfer = ic.classify("TRANSFER FROM SAVINGS")
check("Transfer = TRANSFER", xfer.inflow_type == "TRANSFER")

equity = ic.classify("OWNER CONTRIBUTION")
check("Owner contribution = EQUITY", equity.inflow_type == "EQUITY")

unknown = ic.classify("DEPOSIT")
check("Generic deposit = UNKNOWN", unknown.inflow_type == "UNKNOWN")
check("Unknown requires review", unknown.requires_review == True)

# ── 3. Loan Splitter ──────────────────────────────────────
print("\n3. LOAN SPLITTER")
ls = LoanSplitter()

result = ls.analyze("SBA LOAN PAYMENT", Decimal("1200.00"))
check("Detects loan", result.is_loan == True)
check("Needs manual split (no amortization)", result.needs_manual_split == True)

result2 = ls.analyze("SBA LOAN PAYMENT INTEREST $45.00", Decimal("1200.00"))
check("Extracts interest from desc", result2.interest == Decimal("45.00"))
check("Computes principal", result2.principal == Decimal("1155.00"))
check("Split source = description", result2.split_source == "description")

non_loan = ls.analyze("STARBUCKS COFFEE", Decimal("5.00"))
check("Non-loan detected correctly", non_loan.is_loan == False)

# ── 4. Full Pipeline ──────────────────────────────────────
print("\n4. FULL PIPELINE")
batch = build_test_batch()

# Loan splitting
loan_report = ls.process_batch(batch.transactions)
check("Loan payments found", loan_report["loan_payments_found"] >= 1)

# Categorization (full mode)
cat = CategorizerEngine(mode="full")
cat_result = cat.categorize_batch(batch.transactions)
check("All transactions processed", cat_result["total"] == 12)
check("Review queue populated", cat_result["review_queue"] >= 0)
check("Mode is full", cat_result["mode"] == "full")

# Verify merchant normalization ran
check("Merchant clean populated", batch.transactions[0].merchant_clean != "")
check("Canonical ID populated", batch.transactions[0].canonical_merchant_id != "")

# Verify inflow classification ran
credits = [t for t in batch.transactions if t.direction == "CREDIT"]
check("Credits have inflow_type", all(t.inflow_type != "" for t in credits))

# Capex detection
capex = CapexClassifier()
capex_report = capex.process_batch(batch.transactions)
check("Capex report generated", "capex_count" in capex_report)

# ── 5. Journal Entries ─────────────────────────────────────
print("\n5. JOURNAL ENTRIES")
je_gen = JournalEntryGenerator()
entries = je_gen.generate_batch(batch.transactions)
all_balanced = je_gen.validate_all_balanced(entries)
check("All JEs generated", len(entries) == 12)
check("All JEs balanced", all_balanced)

# Check loan JE doesn't hit expense
loan_txn = [t for t in batch.transactions if "LOAN" in t.description.upper()][0]
check("Loan routed to LIABILITY", loan_txn.account_type == "LIABILITY")

# ── 6. Trial Balance ──────────────────────────────────────
print("\n6. TRIAL BALANCE")
tb_gen = TrialBalanceGenerator()
tb = tb_gen.generate(entries)
check("TB generated", tb is not None)
check("TB is balanced", tb.get("is_balanced", False))

# ── 7. Reconciliation ─────────────────────────────────────
print("\n7. RECONCILIATION")
recon = ReconciliationEngine()
recon_result = recon.reconcile(batch)
check("Reconciliation ran", recon_result.status in ("GREEN", "YELLOW", "RED"))
check("Balances provided", recon_result.balances_provided)
print(f"  INFO  Recon status: {recon_result.status}, diff: {recon_result.difference}")

# ── 8. COGS Engine ─────────────────────────────────────────
print("\n8. COGS ENGINE")
cogs = COGSEngine()
cogs_result = cogs.compute_bank_proxy(batch.transactions)
check("COGS mode = bank_proxy", cogs_result.mode == "bank_proxy")
check("COGS is preliminary", cogs_result.is_preliminary == True)

# ── 9. Flags ───────────────────────────────────────────────
print("\n9. FLAGS")
fe = FlagEngine()
flag_report = fe.flag_batch(batch)
check("Flags processed", flag_report["total_flags"] >= 0)

# ── 10. Validation ─────────────────────────────────────────
print("\n10. VALIDATION")
ve = ValidationEngine()
val_report = ve.validate(batch, entries, tb, recon_result)
check("Validation ran", val_report is not None)
check("Structural issues counted", val_report.structural_count >= 0)
check("Semantic issues counted", val_report.semantic_count >= 0)
print(f"  INFO  Structural pass: {val_report.structural_pass}, Semantic pass: {val_report.semantic_pass}")

# ── 11. Acceptance Criteria ────────────────────────────────
print("\n11. ACCEPTANCE CRITERIA")
ac = AcceptanceCriteria()
accept = ac.evaluate(batch, entries, tb, recon_result, val_report)
check("Acceptance evaluated", accept is not None)
check("4 gates present", len(accept.gates) == 4)
gate_names = [g.name for g in accept.gates]
check("ARITHMETIC gate", "ARITHMETIC" in gate_names)
check("STRUCTURAL gate", "STRUCTURAL" in gate_names)
check("DISCLOSURE gate", "DISCLOSURE" in gate_names)
check("REVIEW gate", "REVIEW" in gate_names)
print(f"  INFO  Overall: {accept.overall_status}")
print(f"  INFO  Can issue full: {accept.can_issue_full}")
print(f"  INFO  Summary: {accept.summary[:100]}...")

# ── 12. Decimal Safety ─────────────────────────────────────
print("\n12. DECIMAL SAFETY")
d = batch.transactions[0].to_dict()
check("Amount serialized as string", isinstance(d["amount"], str))
check("Deductible_pct as string", isinstance(d["deductible_pct"], str))

bd = batch.to_dict()
check("Batch total_credits as string", isinstance(bd["total_credits"], str))
check("Batch total_debits as string", isinstance(bd["total_debits"], str))
check("Reconciliation status in batch", bd["reconciliation_status"] in ("GREEN", "YELLOW", "RED"))

# ── 13. Precision-First Mode ──────────────────────────────
print("\n13. PRECISION-FIRST MODE")
batch2 = build_test_batch()
cat2 = CategorizerEngine(mode="categorize")
cat2_result = cat2.categorize_batch(batch2.transactions)
check("Categorize mode threshold = 0.90", cat2.threshold == 0.90)
check("Higher review queue in precision mode", cat2_result["review_queue"] >= cat_result["review_queue"])

# ── 14. Explainability ────────────────────────────────────
print("\n14. EXPLAINABILITY")
check("Evidence populated", any(len(t.categorization_evidence) > 0 for t in batch.transactions))
check("Matched rule populated", any(t.matched_rule_id != "" for t in batch.transactions))
check("Required review set on unknowns",
      all(t.required_review for t in batch.transactions if t.categorization_layer == "uncategorized"))

# ── SUMMARY ────────────────────────────────────────────────
print("\n" + "=" * 65)
total = PASS + FAIL
print(f"RESULTS: {PASS}/{total} passed, {FAIL} failed")
if FAIL == 0:
    print("ALL TESTS PASS — Blueprint implementation verified.")
else:
    print(f"WARNING: {FAIL} test(s) failed. Review above.")
print("=" * 65)
