"""
bakery.py
=========
Bakery-specific benchmarks and scoring profile.
"""

from .base_profile import BaseProfile, score_against_benchmark


BAKERY_BENCHMARKS = {
    "gross_margin_pct": {
        "low": 50,
        "healthy": 60,
        "excellent": 70,
        "note": "Bakeries with waste control hit 65%+",
    },
    "cogs_pct": {
        "low": 25,
        "healthy": 35,
        "high": 45,
        "note": "Food cost should be 28-35% of revenue",
    },
    "rent_pct_of_revenue": {
        "ideal": 8,
        "warning": 12,
        "critical": 15,
        "note": "If rent is over 15% you have a location problem",
    },
    "net_margin_pct": {
        "struggling": 5,
        "average": 10,
        "healthy": 15,
        "excellent": 20,
    },
    "operating_margin_pct": {
        "low": 8,
        "healthy": 18,
        "excellent": 28,
        "note": "Strong bakeries operate at 18-25%",
    },
    "labor_pct": {
        "low": 20,
        "healthy": 30,
        "high": 40,
        "note": "Total labor (COGS + staff) should be 25-35%",
    },
}


class BakeryProfile(BaseProfile):
    name = "Bakery"
    benchmarks = BAKERY_BENCHMARKS

    @classmethod
    def score(cls, pl_statement):
        return score_against_benchmark(pl_statement, cls.benchmarks, cls.name)
