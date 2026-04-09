"""
document_classifier.py
======================
Identifies document type from content analysis.
Bank statement vs receipt vs invoice vs credit card statement.
100% local — no network calls.
"""

import re
from enum import Enum
from dataclasses import dataclass
from typing import Dict, List, Tuple


class DocumentType(Enum):
    BANK_STATEMENT = "bank_statement"
    CREDIT_CARD_STATEMENT = "credit_card_statement"
    RECEIPT = "receipt"
    INVOICE = "invoice"
    UNKNOWN = "unknown"


DOCUMENT_SIGNATURES: Dict[DocumentType, Dict] = {
    DocumentType.BANK_STATEMENT: {
        "identifiers": [
            "account number", "routing", "statement period",
            "beginning balance", "ending balance", "checking",
            "savings account", "account summary", "deposits and credits",
            "withdrawals and debits", "daily balance",
        ],
        "key_fields": ["date", "description", "debit", "credit", "balance"],
        "weight": 1.0,
    },
    DocumentType.CREDIT_CARD_STATEMENT: {
        "identifiers": [
            "credit card", "minimum payment", "credit limit",
            "payment due date", "new balance", "previous balance",
            "annual percentage rate", "apr", "credit line",
            "reward points", "cash advance",
        ],
        "key_fields": ["date", "merchant", "amount", "category"],
        "weight": 1.0,
    },
    DocumentType.RECEIPT: {
        "identifiers": [
            "receipt", "subtotal", "tax", "total",
            "thank you", "change due", "payment method",
            "visa", "mastercard", "item", "qty",
        ],
        "key_fields": ["date", "vendor", "items", "amount", "tax_amount"],
        "weight": 0.8,
    },
    DocumentType.INVOICE: {
        "identifiers": [
            "invoice number", "invoice #", "bill to", "due date",
            "net 30", "net 60", "remit to", "purchase order",
            "terms", "ship to", "invoice date",
        ],
        "key_fields": ["invoice_date", "due_date", "vendor", "line_items", "total"],
        "weight": 1.0,
    },
}


@dataclass
class ClassificationResult:
    document_type: DocumentType
    confidence: float
    matched_identifiers: List[str]
    scores: Dict[str, float]


class DocumentClassifier:
    """
    Scores document text against known signatures.
    Returns the best-match document type + confidence.
    """

    def classify(self, text: str) -> ClassificationResult:
        text_lower = text.lower()
        scores: Dict[str, float] = {}
        best_type = DocumentType.UNKNOWN
        best_score = 0.0
        best_matches: List[str] = []

        for doc_type, sig in DOCUMENT_SIGNATURES.items():
            matched = []
            for identifier in sig["identifiers"]:
                if identifier.lower() in text_lower:
                    matched.append(identifier)

            if not sig["identifiers"]:
                score = 0.0
            else:
                score = (len(matched) / len(sig["identifiers"])) * sig["weight"]

            scores[doc_type.value] = round(score, 3)

            if score > best_score:
                best_score = score
                best_type = doc_type
                best_matches = matched

        # Minimum threshold — below this we call it unknown
        if best_score < 0.15:
            best_type = DocumentType.UNKNOWN
            best_matches = []

        return ClassificationResult(
            document_type=best_type,
            confidence=round(best_score, 3),
            matched_identifiers=best_matches,
            scores=scores,
        )

    def classify_with_fallback(self, text: str) -> ClassificationResult:
        """
        Classify with heuristic fallbacks for edge cases.
        """
        result = self.classify(text)

        if result.document_type == DocumentType.UNKNOWN:
            # Heuristic: lots of dated rows with amounts = likely bank statement
            date_pattern = re.compile(
                r"\d{1,2}[/-]\d{1,2}[/-]?\d{0,4}\s+.+\s+\$?[\d,]+\.\d{2}"
            )
            matches = date_pattern.findall(text)
            if len(matches) >= 5:
                result.document_type = DocumentType.BANK_STATEMENT
                result.confidence = 0.50
                result.matched_identifiers = ["heuristic: dated transaction rows"]

        return result
