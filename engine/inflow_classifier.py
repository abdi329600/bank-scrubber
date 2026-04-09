"""
inflow_classifier.py
====================
Classifies inflows BEFORE they hit the categorization engine.
Bank deposits != gross receipts. This module enforces the IRS principle
that deposits must be analyzed to identify sources.

Inflow taxonomy:
  REVENUE     — Customer receipts, processor payouts
  CONTRA_REV  — Returns, refunds, chargebacks reducing revenue
  FINANCING   — Loan proceeds, line of credit draws
  EQUITY      — Owner contributions, capital injections
  TRANSFER    — Between own accounts (not revenue)
  REFUND      — Tax refunds, insurance refunds, vendor credits
  UNKNOWN     — Requires human classification
"""

import re
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass


@dataclass
class InflowClassification:
    inflow_type: str       # REVENUE / CONTRA_REV / FINANCING / EQUITY / TRANSFER / REFUND / UNKNOWN
    confidence: float
    evidence: str
    requires_review: bool = False


# ── Pattern rules ordered by specificity (most specific first) ────
INFLOW_RULES: List[Dict] = [
    # ── TRANSFER (between own accounts) ──────────────────────────
    {
        "type": "TRANSFER",
        "patterns": [
            r"TRANSFER\s*(FROM|TO)\s*(SAVINGS|CHECKING|ACCOUNT)",
            r"ONLINE\s*TRANSFER", r"INTERNAL\s*TRANSFER",
            r"XFER\s*(FROM|TO)", r"MOBILE\s*TRANSFER",
            r"BETWEEN\s*ACCOUNTS",
        ],
        "confidence": 0.92,
        "evidence": "Description matches inter-account transfer pattern",
    },
    # ── FINANCING (loan proceeds) ────────────────────────────────
    {
        "type": "FINANCING",
        "patterns": [
            r"LOAN\s*PROCEED", r"LINE\s*OF\s*CREDIT",
            r"SBA\s*(LOAN|EIDL|PPP)", r"CREDIT\s*LINE\s*DRAW",
            r"MERCHANT\s*ADVANCE", r"EQUIPMENT\s*FINANCING",
            r"BUSINESS\s*LOAN",
        ],
        "confidence": 0.90,
        "evidence": "Description matches financing/loan pattern — NOT revenue",
    },
    # ── EQUITY (owner contributions) ─────────────────────────────
    {
        "type": "EQUITY",
        "patterns": [
            r"OWNER\s*(CONTRIBUTION|INVEST|DEPOSIT|CAPITAL)",
            r"MEMBER\s*CONTRIBUTION", r"CAPITAL\s*INJECTION",
            r"PERSONAL\s*DEPOSIT", r"SHAREHOLDER\s*LOAN",
        ],
        "confidence": 0.88,
        "evidence": "Description matches owner/equity contribution pattern — NOT revenue",
    },
    # ── REFUND (vendor/tax/insurance) ────────────────────────────
    {
        "type": "REFUND",
        "patterns": [
            r"REFUND", r"CREDIT\s*MEMO", r"REVERSAL",
            r"TAX\s*REFUND", r"INSURANCE\s*REFUND",
            r"VENDOR\s*CREDIT", r"RETURN\s*CREDIT",
            r"CHARGEBACK\s*CREDIT",
        ],
        "confidence": 0.85,
        "evidence": "Description matches refund/reversal pattern",
    },
    # ── CONTRA-REVENUE (customer returns reducing gross receipts) ─
    {
        "type": "CONTRA_REV",
        "patterns": [
            r"CUSTOMER\s*RETURN", r"SALES\s*RETURN",
            r"CHARGEBACK", r"DISPUTE\s*CREDIT",
        ],
        "confidence": 0.87,
        "evidence": "Customer return/chargeback — reduces gross revenue",
    },
    # ── REVENUE: Processor payouts (deterministic — these ARE revenue) ──
    {
        "type": "REVENUE",
        "patterns": [
            r"SQUARE\s*(DEPOSIT|PAYOUT)",
            r"SQ\s*\*?\s*(DEPOSIT|PAYOUT)",
            r"STRIPE\s*(PAYOUT|TRANSFER|DEPOSIT)",
            r"PAYPAL\s*(TRANSFER|DEPOSIT|INST)",
            r"CLOVER\s*(DEPOSIT|PAYOUT)",
            r"SHOPIFY\s*(PAYOUT|DEPOSIT)",
            r"TOAST\s*(DEPOSIT|PAYOUT)",
        ],
        "confidence": 0.95,
        "evidence": "Payment processor payout — deterministic revenue deposit",
    },
    # ── REVENUE: Customer payments (high confidence) ────────────
    {
        "type": "REVENUE",
        "patterns": [
            r"DEPOSIT\s*-?\s*(CUSTOMER|CLIENT|INVOICE|PAYMENT)",
            r"CUSTOMER\s*(PAYMENT|PMT|DEPOSIT)",
            r"CLIENT\s*(PAYMENT|PMT|DEPOSIT)",
            r"INVOICE\s*(PAYMENT|PMT)",
            r"ZELLE\s*(FROM|PAYMENT|RECEIVED|PMT)",
            r"VENMO\s*(PAYMENT|CASHOUT|FROM)",
            r"WIRE\s*(TRANSFER\s*)?IN",
            r"ACH\s*(DEPOSIT|CREDIT)\s*-?\s*\w",
            r"CHECK\s*DEPOSIT",
            r"POS\s*(SALE|BATCH|DEPOSIT)",
            r"DAILY\s*SALES",
            r"CASH\s*DEPOSIT",
            r"SERVICE\s*(PAYMENT|PMT|FEE)",
            r"CONSULTING\s*(FEE|PAYMENT|PMT)",
            r"PAYMENT\s*RECEIVED",
            r"RECEIVED\s*FROM",
            r"MOBILE\s*DEPOSIT",
            r"REMOTE\s*DEPOSIT",
        ],
        "confidence": 0.85,
        "evidence": "Customer receipt or deposit — likely business revenue",
    },
    # ── INSURANCE REIMBURSEMENT ────────────────────────────────
    {
        "type": "REFUND",
        "patterns": [
            r"INSURANCE\s*(REIMBURSE|REFUND|CLAIM|PAYMENT|PMT|PROCEEDS)",
            r"CLAIM\s*(PAYMENT|PROCEEDS|SETTLEMENT)",
            r"(GEICO|STATE\s*FARM|PROGRESSIVE|ALLSTATE|LIBERTY|NATIONWIDE|USAA)\s*(CLAIM|PMT|PAYMENT)",
        ],
        "confidence": 0.90,
        "evidence": "Insurance reimbursement/claim payment — not operating revenue",
    },
    # ── OWNER DRAW (outflow but equity, not expense) ───────────
    {
        "type": "EQUITY",
        "patterns": [
            r"OWNER\s*(DRAW|DISTRIBUTION|DIST|WITHDRAWAL)",
            r"MEMBER\s*DISTRIBUTION",
            r"SHAREHOLDER\s*DISTRIBUTION",
            r"PERSONAL\s*(TRANSFER|WITHDRAWAL)",
        ],
        "confidence": 0.92,
        "evidence": "Owner draw/distribution — equity reduction, NOT P&L expense",
    },
]


class InflowClassifier:
    """
    Classifies credit (inflow) transactions before categorization.
    Only revenue-class inflows should populate gross revenue.
    """

    def __init__(self):
        self.rules = list(INFLOW_RULES)
        # Pre-compile regex patterns
        self._compiled = []
        for rule in self.rules:
            compiled_patterns = [re.compile(p, re.IGNORECASE) for p in rule["patterns"]]
            self._compiled.append((rule, compiled_patterns))

    def classify(self, description: str, amount=None) -> InflowClassification:
        """Classify a single inflow transaction."""
        desc = description.strip()

        for rule, patterns in self._compiled:
            for pat in patterns:
                if pat.search(desc):
                    return InflowClassification(
                        inflow_type=rule["type"],
                        confidence=rule["confidence"],
                        evidence=rule["evidence"],
                        requires_review=(rule["confidence"] < 0.85),
                    )

        # ── Heuristic fallback ───────────────────────────────────
        desc_upper = desc.upper()

        # Generic deposits with no clear source
        if "DEPOSIT" in desc_upper:
            return InflowClassification(
                inflow_type="UNKNOWN",
                confidence=0.40,
                evidence="Generic deposit — source unclear, could be revenue or transfer",
                requires_review=True,
            )

        # Large round deposits — possibly loan or equity
        from decimal import Decimal
        if amount and Decimal(str(amount)) >= Decimal("10000") and Decimal(str(amount)) % Decimal("1000") == 0:
            return InflowClassification(
                inflow_type="UNKNOWN",
                confidence=0.30,
                evidence="Large round deposit — may be loan proceeds, owner contribution, or revenue",
                requires_review=True,
            )

        return InflowClassification(
            inflow_type="UNKNOWN",
            confidence=0.20,
            evidence="No matching inflow pattern — human review required before posting as revenue",
            requires_review=True,
        )

    def classify_batch(self, transactions) -> None:
        """Classify all transactions for pre-categorization routing.
        
        Credits get inflow bucketing (revenue/transfer/equity/financing/refund).
        Debits get checked for transfers and owner equity activity.
        """
        for txn in transactions:
            if txn.direction == "CREDIT":
                result = self.classify(txn.description, txn.amount)
                txn.inflow_type = result.inflow_type
                txn.inflow_evidence = result.evidence
                if result.requires_review:
                    txn.required_review = True
                    if "INFLOW_UNCLASSIFIED" not in txn.flags:
                        txn.flags.append("INFLOW_UNCLASSIFIED")
                        txn.flag_notes.append(result.evidence)
            else:
                # Check debits for transfers / owner draws / non-P&L items
                outflow_result = self._classify_outflow(txn.description)
                txn.inflow_type = outflow_result.inflow_type
                txn.inflow_evidence = outflow_result.evidence

    def _classify_outflow(self, description: str) -> InflowClassification:
        """Pre-classify debit transactions for transfer/equity routing."""
        desc = description.upper().strip()

        # Internal transfers (should NOT hit P&L)
        import re
        transfer_patterns = [
            r"TRANSFER\s*(TO|FROM)\s*(SAVINGS|CHECKING|ACCOUNT)",
            r"ONLINE\s*TRANSFER", r"INTERNAL\s*TRANSFER",
            r"XFER\s*(TO|FROM)", r"MOBILE\s*TRANSFER",
            r"BETWEEN\s*ACCOUNTS",
        ]
        for pat in transfer_patterns:
            if re.search(pat, desc, re.IGNORECASE):
                return InflowClassification(
                    inflow_type="TRANSFER",
                    confidence=0.92,
                    evidence="Inter-account transfer — balance sheet only, not P&L",
                )

        # Owner draws / distributions (equity, not expense)
        owner_patterns = [
            r"OWNER\s*(DRAW|DISTRIBUTION|DIST|WITHDRAWAL)",
            r"MEMBER\s*DISTRIBUTION",
            r"SHAREHOLDER\s*DISTRIBUTION",
            r"PERSONAL\s*(TRANSFER|WITHDRAWAL)",
        ]
        for pat in owner_patterns:
            if re.search(pat, desc, re.IGNORECASE):
                return InflowClassification(
                    inflow_type="EQUITY",
                    confidence=0.92,
                    evidence="Owner draw/distribution — equity reduction, NOT P&L expense",
                )

        # Sales tax payments (liability, not expense)
        tax_patterns = [
            r"SALES\s*TAX\s*(PAYMENT|PMT)",
            r"STATE\s*TAX.*SALES",
        ]
        for pat in tax_patterns:
            if re.search(pat, desc, re.IGNORECASE):
                return InflowClassification(
                    inflow_type="TAX_LIABILITY",
                    confidence=0.90,
                    evidence="Sales tax payment — liability reduction, not operating expense",
                )

        return InflowClassification(
            inflow_type="OUTFLOW",
            confidence=1.0,
            evidence="Standard business outflow",
        )
