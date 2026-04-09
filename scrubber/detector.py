"""
detector.py
===========
Pure-Python regex engine — no external API calls, no network I/O.
All detection happens in local RAM only.
"""

import re
from dataclasses import dataclass, field
from typing import List, Tuple, Optional
from enum import Enum


class DataType(Enum):
    ACCOUNT_NUMBER = "Account Number"
    ROUTING_NUMBER = "Routing Number"
    SSN            = "Social Security Number"
    PHONE          = "Phone Number"
    EMAIL          = "Email Address"
    ADDRESS        = "Street Address"
    CREDIT_CARD    = "Credit Card Number"
    DATE_OF_BIRTH  = "Date of Birth"
    FULL_NAME      = "Full Name"
    IP_ADDRESS     = "IP Address"
    IBAN           = "IBAN"
    PASSPORT       = "Passport Number"
    DRIVERS_LIC    = "Drivers License"
    CUSTOM         = "Custom Term"


@dataclass
class Detection:
    data_type:  DataType
    value:      str
    start:      int
    end:        int
    confidence: float          # 0.0 – 1.0
    context:    str = field(default="")   # surrounding chars for audit


class SensitiveDataDetector:
    """
    Scans plain text and returns every sensitive span.
    No data ever leaves this function — pure in-memory regex.
    """

    PATTERNS: List[Tuple[DataType, str, float]] = [

        # SSN — must come BEFORE generic numbers
        (DataType.SSN,
         r"\b(?!000|666|9\d{2})\d{3}[-.\s]?(?!00)\d{2}[-.\s]?(?!0000)\d{4}\b",
         0.97),

        # Credit / debit card (Visa, MC, Amex, Discover, generic 13-19 digit)
        (DataType.CREDIT_CARD,
         r"\b(?:4[0-9]{12}(?:[0-9]{3})?"
         r"|(?:5[1-5][0-9]{2}|222[1-9]|22[3-9][0-9]"
         r"|2[3-6][0-9]{2}|27[01][0-9]|2720)[0-9]{12}"
         r"|3[47][0-9]{13}"
         r"|6(?:011|5[0-9]{2})[0-9]{12}"
         r"|(?:\d[ -]?){13,19})\b",
         0.92),

        # IBAN
        (DataType.IBAN,
         r"\b[A-Z]{2}\d{2}[A-Z0-9]{4}\d{7}(?:[A-Z0-9]?){0,16}\b",
         0.95),

        # US routing number (exactly 9 digits)
        (DataType.ROUTING_NUMBER,
         r"\b(?:routing(?:\s+(?:number|#|no\.?))?[\s:]*)?[0-9]{9}\b",
         0.78),

        # Bank account number (8-17 digits)
        (DataType.ACCOUNT_NUMBER,
         r"\b(?:account(?:\s+(?:number|#|no\.?))?[\s:]*)?[0-9]{8,17}\b",
         0.72),

        # Phone numbers (US + international variants)
        (DataType.PHONE,
         r"\b(?:\+?1[-.\s]?)?(?:\(?[2-9][0-9]{2}\)?[-.\s]?)"
         r"[2-9][0-9]{2}[-.\s]?[0-9]{4}\b",
         0.95),

        # Email
        (DataType.EMAIL,
         r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b",
         0.99),

        # Street address (number + street name + type)
        (DataType.ADDRESS,
         r"\b\d{1,5}\s+(?:[A-Z][a-z]+\s+){1,4}"
         r"(?:Street|St|Avenue|Ave|Boulevard|Blvd|Road|Rd|"
         r"Drive|Dr|Lane|Ln|Court|Ct|Place|Pl|Way|Circle|Cir)"
         r"(?:\.|\s|,|$)",
         0.87),

        # Date of birth
        (DataType.DATE_OF_BIRTH,
         r"\b(?:DOB|Date\s+of\s+Birth|Born|Birth\s+Date)"
         r"[\s:]+\d{1,2}[/-]\d{1,2}[/-]\d{2,4}\b",
         0.92),

        # IP address
        (DataType.IP_ADDRESS,
         r"\b(?:(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.){3}"
         r"(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\b",
         0.99),
    ]

    CONTEXT_WINDOW = 30  # chars either side captured for audit log

    def __init__(self, custom_terms: Optional[List[str]] = None):
        self._compiled = self._compile_patterns()
        self.custom_terms: List[str] = list(custom_terms or [])

    def _compile_patterns(self):
        out = []
        for dt, pat, conf in self.PATTERNS:
            try:
                out.append((dt, re.compile(pat, re.IGNORECASE), conf))
            except re.error as exc:
                print(f"[WARN] Pattern compile failed for {dt}: {exc}")
        return out

    # ── public API ──────────────────────────────────────────────

    def detect(self, text: str) -> List[Detection]:
        """Return all detections, sorted by start position."""
        detections: List[Detection] = []

        for dt, pattern, confidence in self._compiled:
            for m in pattern.finditer(text):
                s, e = m.start(), m.end()
                ctx = text[max(0, s - self.CONTEXT_WINDOW):e + self.CONTEXT_WINDOW]
                detections.append(
                    Detection(dt, m.group(), s, e, confidence, ctx)
                )

        # custom terms — exact match, case-insensitive
        for term in self.custom_terms:
            pat = re.compile(re.escape(term), re.IGNORECASE)
            for m in pat.finditer(text):
                s, e = m.start(), m.end()
                ctx = text[max(0, s - self.CONTEXT_WINDOW):e + self.CONTEXT_WINDOW]
                detections.append(
                    Detection(DataType.CUSTOM, m.group(), s, e, 1.0, ctx)
                )

        return sorted(detections, key=lambda d: d.start)

    def add_custom_term(self, term: str) -> None:
        if term and term not in self.custom_terms:
            self.custom_terms.append(term)

    def remove_custom_term(self, term: str) -> bool:
        if term in self.custom_terms:
            self.custom_terms.remove(term)
            return True
        return False

    def summary(self, detections: List[Detection]) -> dict:
        """Return counts grouped by DataType."""
        counts: dict = {}
        for d in detections:
            counts[d.data_type.value] = counts.get(d.data_type.value, 0) + 1
        return dict(sorted(counts.items()))
