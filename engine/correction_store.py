"""
correction_store.py
===================
Persistent learning layer: stores human corrections and replays them
as high-confidence matches on future transactions.

Every manual override becomes a "learned rule" that:
  1. Maps normalized description → correct account code/name/type
  2. Tracks how many times it was applied (confidence compounds)
  3. Persists per-client to JSON on disk
  4. Sits between exact_match (Layer 1) and pattern_match (Layer 2)
     as "learned_match" (Layer 1.5)

This is the core feedback loop that makes the system compound —
same mistake never happens twice.
"""

import json
import re
import hashlib
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional
from dataclasses import dataclass, field, asdict


@dataclass
class CorrectionRule:
    """A single learned correction from a human override."""
    rule_id: str                    # SHA-256 hash of canonical pattern
    canonical_pattern: str          # Normalized description fragment to match
    account_code: str               # Correct CoA account code
    account_name: str               # Correct account name
    account_type: str               # ASSET/LIABILITY/EQUITY/REVENUE/COGS/EXPENSE
    category: str = ""              # High-level bucket
    subcategory: str = ""           # Detailed bucket
    deductible: bool = True
    irs_ref: str = ""
    direction: str = ""             # DEBIT or CREDIT (optional constraint)
    # ── Learning metadata ──────────────────────────────────────────
    times_applied: int = 0          # How many times this rule has fired
    times_confirmed: int = 0        # How many times human confirmed it was right
    times_overridden: int = 0       # How many times human overrode it again
    created_at: str = ""
    last_applied: str = ""
    source: str = "human_override"  # "human_override" / "bulk_import" / "api"
    notes: str = ""

    @property
    def confidence(self) -> float:
        """Confidence increases with application count, decreases with overrides."""
        base = 0.90
        # Each confirmation adds 0.01 up to 0.99
        confirm_boost = min(0.09, self.times_confirmed * 0.01)
        # Each override reduces confidence
        override_penalty = min(0.30, self.times_overridden * 0.10)
        return max(0.50, min(0.99, base + confirm_boost - override_penalty))


@dataclass
class CorrectionMatch:
    """Result of a learned-match lookup."""
    matched: bool = False
    rule: Optional[CorrectionRule] = None
    confidence: float = 0.0
    evidence: str = ""


class CorrectionStore:
    """
    Per-client persistent correction memory.
    
    Storage: JSON file at config/corrections/{client_id}.json
    Lookup: normalized description substring match, longest-match-first.
    """

    def __init__(self, client_id: str = "default", store_dir: str = "config/corrections"):
        self.client_id = client_id
        self.store_dir = Path(store_dir)
        self.rules: Dict[str, CorrectionRule] = {}
        self._load()

    def _store_path(self) -> Path:
        return self.store_dir / f"{self.client_id}.json"

    def _load(self):
        """Load corrections from disk."""
        path = self._store_path()
        if path.exists():
            try:
                with open(path) as f:
                    data = json.load(f)
                for rule_id, rule_data in data.get("rules", {}).items():
                    self.rules[rule_id] = CorrectionRule(**rule_data)
            except (json.JSONDecodeError, IOError, TypeError):
                self.rules = {}

    def save(self):
        """Persist corrections to disk."""
        self.store_dir.mkdir(parents=True, exist_ok=True)
        data = {
            "client_id": self.client_id,
            "rule_count": len(self.rules),
            "last_updated": datetime.utcnow().isoformat() + "Z",
            "rules": {rid: asdict(rule) for rid, rule in self.rules.items()},
        }
        with open(self._store_path(), "w") as f:
            json.dump(data, f, indent=2)

    def _make_rule_id(self, pattern: str) -> str:
        """Deterministic ID from normalized pattern."""
        return hashlib.sha256(pattern.upper().strip().encode()).hexdigest()[:16]

    def add_correction(
        self,
        description: str,
        account_code: str,
        account_name: str,
        account_type: str,
        category: str = "",
        subcategory: str = "",
        deductible: bool = True,
        irs_ref: str = "",
        direction: str = "",
        notes: str = "",
        source: str = "human_override",
    ) -> CorrectionRule:
        """Record a human correction as a learned rule.
        
        The description is normalized to uppercase and stripped of noise
        to create a reusable matching pattern.
        """
        pattern = self._normalize_for_matching(description)
        rule_id = self._make_rule_id(pattern)

        if rule_id in self.rules:
            # Update existing rule
            existing = self.rules[rule_id]
            existing.account_code = account_code
            existing.account_name = account_name
            existing.account_type = account_type
            existing.category = category or existing.category
            existing.subcategory = subcategory or existing.subcategory
            existing.deductible = deductible
            existing.irs_ref = irs_ref or existing.irs_ref
            existing.notes = notes or existing.notes
            existing.times_confirmed += 1
            existing.last_applied = datetime.utcnow().isoformat() + "Z"
            self.save()
            return existing

        rule = CorrectionRule(
            rule_id=rule_id,
            canonical_pattern=pattern,
            account_code=account_code,
            account_name=account_name,
            account_type=account_type,
            category=category,
            subcategory=subcategory,
            deductible=deductible,
            irs_ref=irs_ref,
            direction=direction,
            created_at=datetime.utcnow().isoformat() + "Z",
            last_applied="",
            source=source,
            notes=notes,
        )
        self.rules[rule_id] = rule
        self.save()
        return rule

    def record_override(self, description: str):
        """Record that a learned rule was overridden by a human.
        
        This reduces confidence for the existing rule so the system
        learns it was wrong.
        """
        pattern = self._normalize_for_matching(description)
        rule_id = self._make_rule_id(pattern)
        if rule_id in self.rules:
            self.rules[rule_id].times_overridden += 1
            self.save()

    def match(self, description: str, direction: str = "") -> CorrectionMatch:
        """Look up a description against learned corrections.
        
        Uses longest-match-first strategy (more specific rules win).
        Optionally constrains by direction.
        """
        if not self.rules:
            return CorrectionMatch(matched=False)

        cleaned = self._normalize_for_matching(description)

        # Sort rules by pattern length descending (longest match first)
        sorted_rules = sorted(
            self.rules.values(),
            key=lambda r: len(r.canonical_pattern),
            reverse=True,
        )

        for rule in sorted_rules:
            if rule.canonical_pattern in cleaned:
                # Direction constraint check
                if rule.direction and direction and rule.direction != direction:
                    continue

                # Skip rules with too many overrides (low trust)
                if rule.confidence < 0.50:
                    continue

                # Update application count
                rule.times_applied += 1
                rule.last_applied = datetime.utcnow().isoformat() + "Z"

                return CorrectionMatch(
                    matched=True,
                    rule=rule,
                    confidence=rule.confidence,
                    evidence=(
                        f"Learned match: '{rule.canonical_pattern}' → "
                        f"{rule.account_code} {rule.account_name} "
                        f"(applied {rule.times_applied}x, "
                        f"confirmed {rule.times_confirmed}x, "
                        f"source: {rule.source})"
                    ),
                )

        return CorrectionMatch(matched=False)

    def _normalize_for_matching(self, description: str) -> str:
        """Normalize description for consistent matching.
        
        Strips bank noise, dates, reference numbers, card numbers.
        This ensures "SYSCO #1234 04/01" and "SYSCO #5678 05/15"
        match the same rule.
        """
        text = description.upper().strip()
        # Strip reference numbers, dates, card numbers
        text = re.sub(r"#\d+", "", text)
        text = re.sub(r"\b\d{2}/\d{2}(/\d{2,4})?\b", "", text)
        text = re.sub(r"\bCARD\s*\d{4}\b", "", text)
        text = re.sub(r"\bXX+\d{4}\b", "", text)
        text = re.sub(r"\b\d{6,}\b", "", text)  # Long reference numbers
        text = re.sub(r"\s+", " ", text).strip()
        return text

    def bulk_import(self, corrections: List[Dict]) -> int:
        """Import corrections from a list of dicts (e.g., from CSV or API).
        
        Each dict must have: description, account_code, account_name, account_type
        Optional: category, subcategory, deductible, direction, notes
        """
        count = 0
        for c in corrections:
            try:
                self.add_correction(
                    description=c["description"],
                    account_code=c["account_code"],
                    account_name=c["account_name"],
                    account_type=c["account_type"],
                    category=c.get("category", ""),
                    subcategory=c.get("subcategory", ""),
                    deductible=c.get("deductible", True),
                    direction=c.get("direction", ""),
                    notes=c.get("notes", ""),
                    source="bulk_import",
                )
                count += 1
            except (KeyError, TypeError):
                continue
        return count

    @property
    def stats(self) -> Dict:
        """Summary statistics for the correction store."""
        if not self.rules:
            return {"total_rules": 0, "total_applied": 0, "avg_confidence": 0}
        total_applied = sum(r.times_applied for r in self.rules.values())
        avg_conf = sum(r.confidence for r in self.rules.values()) / len(self.rules)
        return {
            "total_rules": len(self.rules),
            "total_applied": total_applied,
            "avg_confidence": round(avg_conf, 3),
            "high_confidence_rules": sum(1 for r in self.rules.values() if r.confidence >= 0.90),
            "low_trust_rules": sum(1 for r in self.rules.values() if r.confidence < 0.70),
        }
