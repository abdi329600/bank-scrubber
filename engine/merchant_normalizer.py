"""
merchant_normalizer.py
======================
Entity resolution layer: normalize raw bank descriptions into
canonical merchant identities BEFORE categorization.

Two distinct problems solved here:
1. Merchant identity — "AMZN Mktp", "Amazon.com", "AMAZON PRIME" → same merchant
2. Token extraction — pull meaningful tokens for downstream matching
"""

import re
import json
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, field


# ── Common prefixes/suffixes the banks inject ────────────────────
BANK_NOISE = [
    r"\bPOS\b", r"\bPOS DEBIT\b", r"\bDEBIT\b", r"\bCREDIT\b",
    r"\bPURCHASE\b", r"\bACH\b", r"\bWITHDRAWAL\b", r"\bCHECK\s*#?\d*",
    r"\bWIRE\b", r"\bONLINE\b", r"\bMOBILE\b", r"\bRECURRING\b",
    r"\bAUTOPAY\b", r"\bEFT\b", r"\bPAYMENT\b", r"\bTRANSFER\b",
    r"\bELECTRONIC\b", r"\bPRE-AUTH\b", r"\bPENDING\b",
    r"\b\d{2}/\d{2}\b",          # embedded dates MM/DD
    r"#\d+",                      # reference numbers
    r"\bCARD\s*\d{4}\b",         # card last-4
    r"\bXX+\d{4}\b",             # masked card
    r"\s{2,}",                    # multi-spaces
]

# ── Canonical merchant aliases ───────────────────────────────────
# Maps variant → canonical merchant ID
MERCHANT_ALIASES: Dict[str, str] = {
    # ── Retail / General ──────────────────────────────────────────
    "AMZN": "AMAZON", "AMZN MKTP": "AMAZON", "AMAZON.COM": "AMAZON",
    "AMAZON PRIME": "AMAZON_PRIME", "PRIME VIDEO": "AMAZON_PRIME",
    "WM SUPERCENTER": "WALMART", "WAL-MART": "WALMART", "WALMART.COM": "WALMART",
    "MCDONALD'S": "MCDONALDS", "MCDONALDS": "MCDONALDS",
    "CHICK FIL A": "CHICK_FIL_A", "CHICK-FIL-A": "CHICK_FIL_A",
    # ── Fuel ──────────────────────────────────────────────────────
    "SHELL OIL": "SHELL", "SHELL SERVICE": "SHELL",
    "EXXONMOBIL": "EXXON", "EXXON MOBIL": "EXXON",
    # ── Payment Processors (revenue deposits) ─────────────────────
    "SQ *": "SQUARE", "SQUARE": "SQUARE", "GOSQ.COM": "SQUARE",
    "SQUARE DEPOSIT": "SQUARE_DEPOSIT", "SQ *DEPOSIT": "SQUARE_DEPOSIT",
    "STRIPE": "STRIPE", "STRIPE PAYOUT": "STRIPE_PAYOUT",
    "STRIPE TRANSFER": "STRIPE_PAYOUT",
    "PP *": "PAYPAL", "PAYPAL": "PAYPAL",
    "PAYPAL TRANSFER": "PAYPAL_PAYOUT", "PAYPAL INST": "PAYPAL_PAYOUT",
    "CLOVER": "CLOVER", "CLOVER DEPOSIT": "CLOVER_DEPOSIT",
    "SHOPIFY": "SHOPIFY", "SHOPIFY PAYOUT": "SHOPIFY_PAYOUT",
    "TOAST": "TOAST", "TOAST DEPOSIT": "TOAST_DEPOSIT",
    # ── COGS Suppliers (food service) ─────────────────────────────
    "US FOODS": "US_FOODS", "USFOODS": "US_FOODS",
    "SYSCO": "SYSCO", "SYSCO FOOD": "SYSCO",
    "RESTAURANT DEPOT": "RESTAURANT_DEPOT", "REST DEPOT": "RESTAURANT_DEPOT",
    "GORDON FOOD": "GORDON_FOOD", "GFS": "GORDON_FOOD",
    "PERFORMANCE FOOD": "PERFORMANCE_FOOD",
    # ── COGS Suppliers (auto parts) ───────────────────────────────
    "AUTOZONE": "AUTOZONE", "AUTO ZONE": "AUTOZONE",
    "NAPA AUTO": "NAPA", "NAPA": "NAPA",
    "O'REILLY": "OREILLY_AUTO", "O'REILLY AUTO": "OREILLY_AUTO",
    "ADVANCE AUTO": "ADVANCE_AUTO",
    "PEP BOYS": "PEP_BOYS",
    # ── Office / Supplies ─────────────────────────────────────────
    "OFFICE DEPOT": "OFFICE_DEPOT", "OFFICEMAX": "OFFICE_DEPOT",
    "STAPLES": "STAPLES",
    # ── Advertising ───────────────────────────────────────────────
    "GOOGLE *": "GOOGLE", "GOOGLE ADS": "GOOGLE_ADS",
    "FB ADS": "FACEBOOK_ADS", "FACEBOOK ADS": "FACEBOOK_ADS", "META ADS": "FACEBOOK_ADS",
    # ── Software / SaaS ──────────────────────────────────────────
    "INTUIT": "QUICKBOOKS", "QUICKBOOKS": "QUICKBOOKS", "QB ONLINE": "QUICKBOOKS", "QB": "QUICKBOOKS",
    # ── Ride / Delivery ───────────────────────────────────────────
    "UBER TRIP": "UBER_RIDE", "UBER *TRIP": "UBER_RIDE",
    "UBER EATS": "UBER_EATS", "UBEREATS": "UBER_EATS",
    # ── Telecom ───────────────────────────────────────────────────
    "VZWRLSS": "VERIZON", "VERIZON": "VERIZON",
    "ATT*": "ATT", "AT&T": "ATT",
    "COMCAST": "COMCAST", "XFINITY": "COMCAST",
    "T-MOBILE": "TMOBILE", "TMOBILE": "TMOBILE",
    "SPECTRUM": "SPECTRUM",
    # ── Payroll ───────────────────────────────────────────────────
    "ADP PAYROLL": "ADP", "ADP": "ADP",
    "GUSTO": "GUSTO", "GUSTO PAYROLL": "GUSTO",
    "PAYCHEX": "PAYCHEX",
}

# ── Per-client dictionary path ───────────────────────────────────
CLIENT_DICT_PATH = Path("config/merchant_dictionary.json")


@dataclass
class NormalizationResult:
    original: str
    cleaned: str
    canonical_id: str
    tokens: List[str]
    alias_matched: bool = False
    client_dict_matched: bool = False


class MerchantNormalizer:
    """
    Normalize transaction descriptions into canonical merchant identities.
    Order: clean → alias lookup → client dictionary → token extraction.
    """

    def __init__(self, client_dict_path: Optional[str] = None):
        self.aliases = dict(MERCHANT_ALIASES)
        self.client_dict: Dict[str, Dict] = {}
        self._load_client_dict(client_dict_path or str(CLIENT_DICT_PATH))

    def _load_client_dict(self, path: str):
        p = Path(path)
        if p.exists():
            try:
                with open(p) as f:
                    self.client_dict = json.load(f)
            except (json.JSONDecodeError, IOError):
                self.client_dict = {}

    def save_client_dict(self, path: Optional[str] = None):
        p = Path(path or str(CLIENT_DICT_PATH))
        p.parent.mkdir(parents=True, exist_ok=True)
        with open(p, "w") as f:
            json.dump(self.client_dict, f, indent=2)

    def add_client_mapping(self, raw_pattern: str, canonical_id: str,
                           default_account: str = "", notes: str = ""):
        """Add or update a per-client merchant mapping."""
        self.client_dict[raw_pattern.upper()] = {
            "canonical_id": canonical_id,
            "default_account": default_account,
            "notes": notes,
        }

    def normalize(self, description: str) -> NormalizationResult:
        """Full normalization pipeline for a single description."""
        original = description
        cleaned = self._clean(description)
        tokens = self._tokenize(cleaned)

        # 1. Client dictionary lookup (highest priority — per-client overrides)
        for pattern, mapping in self.client_dict.items():
            if pattern in cleaned:
                return NormalizationResult(
                    original=original,
                    cleaned=cleaned,
                    canonical_id=mapping["canonical_id"],
                    tokens=tokens,
                    client_dict_matched=True,
                )

        # 2. Global alias lookup
        canonical_id = self._alias_lookup(cleaned)
        if canonical_id:
            return NormalizationResult(
                original=original,
                cleaned=cleaned,
                canonical_id=canonical_id,
                tokens=tokens,
                alias_matched=True,
            )

        # 3. Fallback: use first 2-3 meaningful tokens as provisional ID
        provisional = "_".join(tokens[:3]).upper() if tokens else cleaned[:20].upper()
        return NormalizationResult(
            original=original,
            cleaned=cleaned,
            canonical_id=provisional,
            tokens=tokens,
        )

    def _clean(self, desc: str) -> str:
        """Remove bank noise, normalize whitespace/punctuation."""
        text = desc.upper().strip()
        for pattern in BANK_NOISE:
            text = re.sub(pattern, " ", text)
        text = re.sub(r"[^\w\s&'-]", " ", text)
        text = re.sub(r"\s+", " ", text).strip()
        return text

    def _tokenize(self, cleaned: str) -> List[str]:
        """Extract meaningful merchant tokens."""
        stop_words = {"THE", "OF", "AND", "FOR", "TO", "IN", "AT", "ON", "BY", "A", "AN"}
        tokens = cleaned.split()
        return [t for t in tokens if t not in stop_words and len(t) > 1]

    def _alias_lookup(self, cleaned: str) -> Optional[str]:
        """Check global aliases, longest match first."""
        sorted_aliases = sorted(self.aliases.keys(), key=len, reverse=True)
        for alias in sorted_aliases:
            if alias in cleaned:
                return self.aliases[alias]
        return None

    def normalize_batch(self, descriptions: List[str]) -> List[NormalizationResult]:
        return [self.normalize(d) for d in descriptions]
