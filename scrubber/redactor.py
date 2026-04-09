"""
redactor.py
===========
Replaces detected spans in plain text.
No network calls. No file writes. Pure string manipulation in RAM.
"""

from datetime import datetime
from typing import List, Dict
from .detector import Detection, DataType


REPLACEMENT_MAP: Dict[DataType, str] = {
    DataType.ACCOUNT_NUMBER: "██ ACCOUNT-XXXX{last4} ██",
    DataType.ROUTING_NUMBER: "██ ROUTING-REDACTED ██",
    DataType.SSN:            "██ SSN-REDACTED ██",
    DataType.PHONE:          "██ PHONE-REDACTED ██",
    DataType.EMAIL:          "██ EMAIL-REDACTED ██",
    DataType.ADDRESS:        "██ ADDRESS-REDACTED ██",
    DataType.CREDIT_CARD:    "██ CARD-XXXX{last4} ██",
    DataType.DATE_OF_BIRTH:  "██ DOB-REDACTED ██",
    DataType.FULL_NAME:      "██ NAME-REDACTED ██",
    DataType.IP_ADDRESS:     "██ IP-REDACTED ██",
    DataType.IBAN:           "██ IBAN-REDACTED ██",
    DataType.PASSPORT:       "██ PASSPORT-REDACTED ██",
    DataType.DRIVERS_LIC:    "██ DRVLIC-REDACTED ██",
    DataType.CUSTOM:         "██ REDACTED ██",
}


class TextRedactor:

    def __init__(self, keep_last_four: bool = True):
        """
        Args:
            keep_last_four: When True, account/card numbers show
                            the last 4 digits (e.g. ██ ACCOUNT-XXXX1234 ██).
        """
        self.keep_last_four = keep_last_four

    def _replacement(self, detection: Detection) -> str:
        template = REPLACEMENT_MAP.get(detection.data_type, "██ REDACTED ██")

        if self.keep_last_four and "{last4}" in template:
            digits = "".join(c for c in detection.value if c.isdigit())
            last4 = digits[-4:] if len(digits) >= 4 else digits.rjust(4, "X")
            return template.format(last4=last4)

        return template.replace("{last4}", "XXXX")

    @staticmethod
    def _resolve_overlaps(detections: List[Detection]) -> List[Detection]:
        """Drop lower-confidence detections that overlap a retained one."""
        sorted_dets = sorted(detections, key=lambda d: (d.start, -d.confidence))
        kept: List[Detection] = []
        last_end = -1

        for det in sorted_dets:
            if det.start >= last_end:
                kept.append(det)
                last_end = det.end

        return kept

    def redact(self, text: str, detections: List[Detection]) -> str:
        """
        Right-to-left substitution so earlier offsets stay valid.
        Returns a new string — original is never mutated.
        """
        if not detections:
            return text

        clean = self._resolve_overlaps(detections)
        chars = list(text)

        for det in reversed(clean):
            chars[det.start:det.end] = list(self._replacement(det))

        return "".join(chars)

    def generate_report(
        self,
        original: str,
        redacted: str,
        detections: List[Detection],
        filename: str = "",
    ) -> str:
        """Human-readable redaction report."""
        lines = [
            "=" * 62,
            "       BANK STATEMENT SCRUBBER — REDACTION REPORT",
            "=" * 62,
            f"  File            : {filename or 'N/A'}",
            f"  Processed at    : {datetime.now().strftime('%Y-%m-%d  %H:%M:%S')}",
            f"  Original chars  : {len(original):,}",
            f"  Redacted chars  : {len(redacted):,}",
            f"  Items redacted  : {len(detections)}",
            "",
            "  DATA NEVER TRANSMITTED — all processing was local.",
            "",
            "-" * 62,
            "  Breakdown by type:",
        ]

        counts: dict = {}
        for d in detections:
            counts[d.data_type.value] = counts.get(d.data_type.value, 0) + 1

        for label, count in sorted(counts.items()):
            lines.append(f"    • {label:<35} {count:>3} item(s)")

        lines += [
            "",
            "-" * 62,
            "  CONFIDENCE SCORES LEGEND:",
            "    99-95%  →  Near-certain match (email, SSN, IP)",
            "    94-85%  →  High confidence  (card, phone, address)",
            "    84-70%  →  Moderate — verify output manually",
            "",
            "-" * 62,
            "  Detections (value masked in this report):",
        ]

        shown: dict = {}
        for d in detections:
            key = d.data_type.value
            if shown.get(key, 0) < 3:  # max 3 examples per type
                masked = "*" * max(0, len(d.value) - 4) + d.value[-4:]
                lines.append(
                    f"    [{key:<28}]  "
                    f"~{masked!r:<18}  "
                    f"conf={d.confidence:.0%}"
                )
                shown[key] = shown.get(key, 0) + 1

        lines += [
            "",
            "=" * 62,
            "  REVIEW CHECKLIST:",
            "  ☐  Confirm all account numbers are masked",
            "  ☐  Confirm client name does not appear in output",
            "  ☐  Confirm no address lines remain",
            "  ☐  Spot-check transaction descriptions manually",
            "  ☐  Delete this report file after review",
            "=" * 62,
        ]

        return "\n".join(lines)
