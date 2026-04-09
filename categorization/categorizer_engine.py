"""
categorizer_engine.py — 4-layer categorization orchestrator.
Layer 1:   Exact match (highest priority, deterministic)
Layer 1.5: Learned match (corrections from human overrides)
Layer 2:   Pattern match (regex/keyword)
Layer 3:   Fallback to uncategorized + flag for CPA review

Two modes:
  - "full"       : auto-accept all layers, flag low confidence
  - "categorize" : precision-first — only auto-accept above HIGH threshold,
                    everything else goes to review queue

Every decision returns an explainability payload:
  decision_layer, confidence, evidence, matched_rule_id, required_review
"""
from decimal import Decimal
from typing import List, Dict, Optional
from .exact_match import ExactMatchLayer
from .pattern_match import PatternMatchLayer
from .chart_of_accounts import get_account
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from engine.transaction import Transaction
from engine.merchant_normalizer import MerchantNormalizer
from engine.inflow_classifier import InflowClassifier
from engine.correction_store import CorrectionStore

# Precision-first threshold: only auto-accept above this in quick mode
PRECISION_THRESHOLD = 0.90
# Standard threshold: flag below this in full mode
STANDARD_THRESHOLD = 0.70


class CategorizerEngine:
    """
    Four-layer categorization with merchant normalization,
    inflow classification, explainability, and precision-first mode.
    """

    def __init__(self, mode: str = "full", client_id: str = "default"):
        self.layer1 = ExactMatchLayer()
        self.correction_store = CorrectionStore(client_id=client_id)
        self.layer2 = PatternMatchLayer()
        self.normalizer = MerchantNormalizer()
        self.inflow_classifier = InflowClassifier()
        self.mode = mode  # "full" or "categorize"
        self.client_id = client_id
        self.threshold = PRECISION_THRESHOLD if mode == "categorize" else STANDARD_THRESHOLD

    def categorize(self, txn: Transaction) -> Transaction:
        """Categorize a single transaction through all layers."""

        # ── Step 0: Merchant normalization ──────────────────────
        norm = self.normalizer.normalize(txn.description)
        txn.merchant_clean = norm.cleaned
        txn.canonical_merchant_id = norm.canonical_id
        txn.merchant_tokens = norm.tokens

        # ── PRE-CLASSIFICATION GATE ────────────────────────────
        # If inflow/outflow classifier already routed this to a non-P&L
        # bucket, lock it in and skip pattern matching. This prevents
        # the categorizer from overwriting TRANSFER/EQUITY/FINANCING.
        if self._pre_classified(txn):
            return txn

        # ── Loan splitter gate ───────────────────────────────
        # If loan_splitter already classified this as LIABILITY, preserve.
        if txn.account_type == "LIABILITY" and txn.loan_split_source:
            txn.categorization_layer = "loan_splitter"
            txn.categorization_evidence = [
                f"Loan payment routed by LoanSplitter (source: {txn.loan_split_source})",
                f"Principal: {txn.loan_principal}, Interest: {txn.loan_interest}",
            ]
            txn.confidence_score = 0.95
            return txn

        desc = txn.description

        # ── Layer 1: Exact Match ────────────────────────────────
        result = self.layer1.match(desc, direction=txn.direction)
        if result:
            txn.account_code = result.account
            txn.account_name = result.account_name
            txn.account_type = result.account_type
            txn.confidence_score = result.confidence
            txn.categorization_layer = "exact_match"
            txn.matched_rule_id = result.rule_id
            txn.categorization_evidence = [
                f"Exact match rule '{result.rule_id}'",
                f"Merchant: {norm.canonical_id}",
                f"Confidence: {result.confidence}",
            ]
            txn.deductible = result.deductible
            txn.irs_ref = result.irs_ref
            if result.flag_note:
                txn.flags.append("EXACT_MATCH_NOTE")
                txn.flag_notes.append(result.flag_note)
            self._enrich_from_coa(txn)
            self._apply_deductibility(txn)
            self._apply_precision_gate(txn)
            return txn

        # ── Layer 1.5: Learned Match (corrections) ──────────────
        learned = self.correction_store.match(desc, direction=txn.direction)
        if learned.matched and learned.rule:
            rule = learned.rule
            txn.account_code = rule.account_code
            txn.account_name = rule.account_name
            txn.account_type = rule.account_type
            txn.category = rule.category
            txn.subcategory = rule.subcategory
            txn.confidence_score = learned.confidence
            txn.categorization_layer = "learned_match"
            txn.matched_rule_id = rule.rule_id
            txn.categorization_evidence = [
                learned.evidence,
                f"Merchant: {norm.canonical_id}",
            ]
            txn.deductible = rule.deductible
            txn.irs_ref = rule.irs_ref
            self._enrich_from_coa(txn)
            self._apply_deductibility(txn)
            self._apply_precision_gate(txn)
            return txn

        # ── Layer 2: Pattern Match ──────────────────────────────
        pattern = self.layer2.match(desc, amount=float(txn.amount))
        if pattern:
            txn.account_code = pattern.account
            txn.account_name = pattern.account_name
            txn.account_type = pattern.account_type
            txn.confidence_score = pattern.confidence
            txn.categorization_layer = "pattern_match"
            txn.matched_rule_id = pattern.rule_id
            txn.matched_tokens = [t for t in norm.tokens if t.upper() in desc.upper()]
            txn.categorization_evidence = [
                f"Pattern match rule '{pattern.rule_id}'",
                f"Matched tokens: {txn.matched_tokens}",
                f"Merchant: {norm.canonical_id}",
                f"Confidence: {pattern.confidence}",
            ]
            txn.deductible = pattern.deductible
            txn.deduction_limit = pattern.deduction_limit
            txn.irs_ref = pattern.irs_ref
            if pattern.flag_note:
                txn.flags.append("PATTERN_NOTE")
                txn.flag_notes.append(pattern.flag_note)
            self._enrich_from_coa(txn)
            self._apply_deductibility(txn)
            self._apply_precision_gate(txn)
            return txn

        # ── Layer 3: Intelligent fallback (break misc into subtypes) ──
        self._classify_fallback(txn, norm)
        return txn

    def _classify_fallback(self, txn: Transaction, norm) -> None:
        """Break the misc parking lot into specific subtypes.
        
        Instead of dumping everything into 4900/6900, analyze the
        description for secondary signals to pick a better bucket.
        """
        desc_upper = txn.description.upper()
        txn.categorization_layer = "uncategorized"
        txn.required_review = True

        if txn.direction == "CREDIT":
            # ── Credit fallback: try to identify what kind of inflow ──
            if any(kw in desc_upper for kw in [
                "INSURANCE", "CLAIM", "GEICO", "STATE FARM", "PROGRESSIVE",
                "ALLSTATE", "LIBERTY", "NATIONWIDE", "USAA",
            ]):
                txn.account_code = "4500"
                txn.account_name = "Insurance Reimbursement"
                txn.account_type = "REVENUE"
                txn.confidence_score = 0.65
                txn.categorization_evidence = [
                    "Fallback: insurance keyword detected on CREDIT side",
                    "Routed to 4500 Insurance Reimbursement (contra-expense)",
                    f"Merchant: {norm.canonical_id}",
                ]
            elif any(kw in desc_upper for kw in [
                "REFUND", "CREDIT MEMO", "RETURN", "REVERSAL",
            ]):
                txn.account_code = "4510"
                txn.account_name = "Vendor Refunds & Credits"
                txn.account_type = "REVENUE"
                txn.confidence_score = 0.60
                txn.categorization_evidence = [
                    "Fallback: refund/credit keyword detected",
                    "Routed to 4510 Vendor Refunds (contra-expense)",
                    f"Merchant: {norm.canonical_id}",
                ]
            elif any(kw in desc_upper for kw in [
                "REIMBURSE", "REIMBURSEMENT",
            ]):
                txn.account_code = "4520"
                txn.account_name = "Other Reimbursements"
                txn.account_type = "REVENUE"
                txn.confidence_score = 0.55
                txn.categorization_evidence = [
                    "Fallback: reimbursement keyword detected",
                    "Routed to 4520 Other Reimbursements",
                    f"Merchant: {norm.canonical_id}",
                ]
            elif any(kw in desc_upper for kw in [
                "DEPOSIT", "PAYMENT", "PMT", "RECEIVED", "SALE", "REVENUE",
                "CUSTOMER", "CLIENT", "INVOICE", "CHECK", "ZELLE", "VENMO",
            ]):
                # Looks like revenue but wasn't caught by exact/pattern
                txn.account_code = "4000"
                txn.account_name = "Sales Revenue"
                txn.account_type = "REVENUE"
                txn.confidence_score = 0.45
                txn.categorization_evidence = [
                    "Fallback: revenue-like keywords on CREDIT side",
                    "Low confidence — needs CPA review",
                    f"Merchant: {norm.canonical_id}",
                ]
            else:
                txn.account_code = "4900"
                txn.account_name = "Other Income / Miscellaneous"
                txn.account_type = "REVENUE"
                txn.confidence_score = 0.0
                txn.categorization_evidence = [
                    "No matching pattern — routed to Other Income",
                    f"Merchant: {norm.canonical_id}",
                    f"Tokens: {norm.tokens}",
                ]
        else:
            # ── Debit fallback: try to identify expense type ──
            if any(kw in desc_upper for kw in [
                "INSURANCE", "PREMIUM", "GEICO", "STATE FARM",
                "PROGRESSIVE", "ALLSTATE", "LIBERTY", "NATIONWIDE",
            ]):
                txn.account_code = "6200"
                txn.account_name = "Insurance - General Business"
                txn.account_type = "EXPENSE"
                txn.confidence_score = 0.65
                txn.categorization_evidence = [
                    "Fallback: insurance keyword detected on DEBIT side",
                    "Routed to 6200 Insurance Expense",
                    f"Merchant: {norm.canonical_id}",
                ]
            elif any(kw in desc_upper for kw in [
                "RENT", "LEASE", "PROPERTY",
            ]):
                txn.account_code = "6100"
                txn.account_name = "Rent & Lease Expense"
                txn.account_type = "EXPENSE"
                txn.confidence_score = 0.60
                txn.categorization_evidence = [
                    "Fallback: rent/lease keyword detected",
                    f"Merchant: {norm.canonical_id}",
                ]
            elif any(kw in desc_upper for kw in [
                "ELECTRIC", "WATER", "GAS BILL", "UTILITY", "POWER",
                "COMCAST", "SPECTRUM", "AT&T", "VERIZON", "T-MOBILE",
            ]):
                txn.account_code = "6110"
                txn.account_name = "Utilities"
                txn.account_type = "EXPENSE"
                txn.confidence_score = 0.65
                txn.categorization_evidence = [
                    "Fallback: utility keyword detected",
                    f"Merchant: {norm.canonical_id}",
                ]
            elif any(kw in desc_upper for kw in [
                "PAYROLL", "SALARY", "WAGES", "ADP", "GUSTO", "PAYCHEX",
            ]):
                txn.account_code = "6000"
                txn.account_name = "Salaries & Wages"
                txn.account_type = "EXPENSE"
                txn.confidence_score = 0.60
                txn.categorization_evidence = [
                    "Fallback: payroll keyword detected",
                    f"Merchant: {norm.canonical_id}",
                ]
            else:
                txn.account_code = "6900"
                txn.account_name = "Miscellaneous Expense"
                txn.account_type = "EXPENSE"
                txn.confidence_score = 0.0
                txn.categorization_evidence = [
                    "No matching pattern — routed to Miscellaneous Expense",
                    f"Merchant: {norm.canonical_id}",
                    f"Tokens: {norm.tokens}",
                ]

        txn.flags.append("LOW_CONFIDENCE_CATEGORY")
        txn.flag_notes.append(
            f"Fallback classification to {txn.account_code} {txn.account_name}. "
            "CPA review required."
        )

    def _pre_classified(self, txn: Transaction) -> bool:
        """Check if inflow/outflow classifier already locked this transaction
        into a non-P&L route. If so, assign account codes and return True."""
        itype = getattr(txn, 'inflow_type', '')

        if itype == "TRANSFER":
            if txn.direction == "CREDIT":
                txn.account_code = "1000"
                txn.account_name = "Transfer In - Operating"
            else:
                txn.account_code = "1020"
                txn.account_name = "Transfer Out - Savings"
            txn.account_type = "ASSET"
            txn.confidence_score = 0.92
            txn.categorization_layer = "pre_classifier"
            txn.categorization_evidence = [
                f"Pre-classified as internal transfer ({txn.inflow_evidence})",
                "Balance sheet item — excluded from P&L",
            ]
            return True

        if itype == "FINANCING":
            if txn.direction == "CREDIT":
                txn.account_code = "2300"
                txn.account_name = "Loan Proceeds"
                txn.account_type = "LIABILITY"
            else:
                txn.account_code = "2300"
                txn.account_name = "Loan Payable"
                txn.account_type = "LIABILITY"
            txn.confidence_score = 0.90
            txn.categorization_layer = "pre_classifier"
            txn.categorization_evidence = [
                f"Pre-classified as financing ({txn.inflow_evidence})",
                "Balance sheet item — excluded from P&L",
            ]
            return True

        if itype == "EQUITY":
            if txn.direction == "CREDIT":
                txn.account_code = "3200"
                txn.account_name = "Owner's Contributions"
            else:
                txn.account_code = "3100"
                txn.account_name = "Owner's Draw"
            txn.account_type = "EQUITY"
            txn.confidence_score = 0.92
            txn.categorization_layer = "pre_classifier"
            txn.categorization_evidence = [
                f"Pre-classified as equity ({txn.inflow_evidence})",
                "Balance sheet item — excluded from P&L",
            ]
            txn.deductible = False
            return True

        if itype == "TAX_LIABILITY":
            txn.account_code = "2120"
            txn.account_name = "Sales Tax Payable"
            txn.account_type = "LIABILITY"
            txn.confidence_score = 0.90
            txn.categorization_layer = "pre_classifier"
            txn.categorization_evidence = [
                f"Pre-classified as tax liability ({txn.inflow_evidence})",
                "Balance sheet item — liability reduction, not expense",
            ]
            return True

        # REFUND inflows → contra-expense accounts, NOT generic 4900
        if itype == "REFUND" and txn.direction == "CREDIT":
            desc_upper = txn.description.upper()
            if any(kw in desc_upper for kw in [
                "INSURANCE", "CLAIM", "GEICO", "STATE FARM", "PROGRESSIVE",
                "ALLSTATE", "LIBERTY", "NATIONWIDE", "USAA",
            ]):
                txn.account_code = "4500"
                txn.account_name = "Insurance Reimbursement"
            else:
                txn.account_code = "4510"
                txn.account_name = "Vendor Refunds & Credits"
            txn.account_type = "REVENUE"
            txn.confidence_score = 0.88
            txn.categorization_layer = "pre_classifier"
            txn.categorization_evidence = [
                f"Pre-classified as refund/reimbursement ({txn.inflow_evidence})",
                "Contra-expense — nets against related expense, not operating revenue",
            ]
            return True

        # REVENUE inflows with high confidence from processor payouts
        if itype == "REVENUE" and txn.direction == "CREDIT":
            # Don't lock in — let exact/pattern match refine the account
            # But boost confidence since we know it's revenue
            return False

        return False

    def categorize_batch(self, txns: List[Transaction]) -> Dict:
        """Categorize a list of transactions. Return stats."""
        # Classify inflows BEFORE categorization
        self.inflow_classifier.classify_batch(txns)

        exact = 0
        learned = 0
        pattern = 0
        pre_classified = 0
        loan_split = 0
        uncategorized = 0
        review_queue = []
        flagged = []

        for txn in txns:
            self.categorize(txn)
            layer = txn.categorization_layer
            if layer == "exact_match":
                exact += 1
            elif layer == "learned_match":
                learned += 1
            elif layer == "pattern_match":
                pattern += 1
            elif layer == "pre_classifier":
                pre_classified += 1
            elif layer == "loan_splitter":
                loan_split += 1
            else:
                uncategorized += 1
            if txn.is_flagged:
                flagged.append(txn)
            if txn.needs_review:
                review_queue.append(txn)

        # Save correction store after batch (updated apply counts)
        self.correction_store.save()

        total = len(txns)
        auto = exact + learned + pattern + pre_classified + loan_split
        return {
            "total": total,
            "pre_classified": pre_classified,
            "loan_split": loan_split,
            "exact_match": exact,
            "learned_match": learned,
            "pattern_match": pattern,
            "uncategorized": uncategorized,
            "auto_categorized": auto,
            "flagged": len(flagged),
            "flagged_transactions": flagged,
            "review_queue": len(review_queue),
            "review_queue_items": review_queue,
            "avg_confidence": (
                round(sum(t.confidence_score for t in txns) / total, 3)
                if total else 0.0
            ),
            "mode": self.mode,
            "threshold": self.threshold,
            "correction_store": self.correction_store.stats,
        }

    def _enrich_from_coa(self, txn: Transaction):
        """Pull Schedule C line from the Chart of Accounts."""
        acct = get_account(txn.account_code)
        if acct:
            txn.schedule_c_line = acct.schedule_c_line
            if not txn.account_name:
                txn.account_name = acct.name

    def _apply_deductibility(self, txn: Transaction):
        """Set deductible_pct based on account type (e.g. meals = 50%)."""
        if txn.account_code == "6150":  # Meals
            txn.deductible_pct = Decimal("0.50")
            txn.deduction_limit = 0.50
            if "MEALS_50PCT" not in txn.categorization_evidence:
                txn.categorization_evidence.append(
                    "Meals: 50% deductible per IRC Section 274"
                )

    def _boost_multi_signal(self, txn: Transaction):
        """Boost confidence when multiple signals agree.
        
        Signals: vendor normalization, direction, inflow type.
        If vendor + direction + inflow agree, confidence should be high
        even if individual keyword match was moderate.
        """
        boost = 0.0
        signals = []

        # Signal 1: Known vendor (alias matched or client dict matched)
        norm_result = self.normalizer.normalize(txn.description)
        if norm_result.alias_matched or norm_result.client_dict_matched:
            boost += 0.05
            signals.append(f"known_vendor:{norm_result.canonical_id}")

        # Signal 2: Inflow type agrees with account type
        itype = getattr(txn, 'inflow_type', '')
        if itype == "REVENUE" and txn.account_type == "REVENUE":
            boost += 0.05
            signals.append("inflow_confirms_revenue")
        elif itype == "OUTFLOW" and txn.account_type in ("EXPENSE", "COGS"):
            boost += 0.03
            signals.append("outflow_confirms_expense")

        # Signal 3: Direction matches expected for account type
        if txn.direction == "CREDIT" and txn.account_type == "REVENUE":
            boost += 0.03
            signals.append("direction_confirms_credit_revenue")
        elif txn.direction == "DEBIT" and txn.account_type in ("EXPENSE", "COGS"):
            boost += 0.03
            signals.append("direction_confirms_debit_expense")

        if boost > 0:
            old_conf = txn.confidence_score
            txn.confidence_score = min(0.99, txn.confidence_score + boost)
            if signals:
                txn.categorization_evidence.append(
                    f"Multi-signal boost +{boost:.2f}: {', '.join(signals)}"
                )

    def _apply_precision_gate(self, txn: Transaction):
        """In precision-first mode, flag items below threshold for review."""
        # Apply multi-signal boost before checking threshold
        self._boost_multi_signal(txn)

        if txn.confidence_score < self.threshold:
            txn.required_review = True
            if "BELOW_THRESHOLD" not in txn.flags:
                txn.flags.append("BELOW_THRESHOLD")
                txn.flag_notes.append(
                    f"Confidence {txn.confidence_score:.0%} is below "
                    f"{self.threshold:.0%} threshold for mode '{self.mode}'. "
                    f"Queued for human review."
                )
