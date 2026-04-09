"""
mechanic.py
===========
Auto repair shop benchmarks and scoring profile.
"""

from .base_profile import BaseProfile, score_against_benchmark


MECHANIC_BENCHMARKS = {
    "gross_margin_pct": {
        "low": 45,
        "healthy": 55,
        "excellent": 65,
        "note": "Labor is high margin, parts are lower",
    },
    "cogs_pct": {
        "low": 30,
        "healthy": 40,
        "high": 55,
        "note": "Parts cost — most shops mark up 40-50%",
    },
    "rent_pct_of_revenue": {
        "ideal": 6,
        "warning": 10,
        "critical": 14,
        "note": "Bay/shop rent should stay under 10%",
    },
    "net_margin_pct": {
        "struggling": 5,
        "average": 12,
        "healthy": 18,
        "excellent": 25,
    },
    "operating_margin_pct": {
        "low": 10,
        "healthy": 20,
        "excellent": 30,
        "note": "Well-run shops hit 20%+",
    },
    "parts_markup": {
        "minimum": 25,
        "standard": 40,
        "note": "Most shops mark up parts 40-50%",
    },
    "labor_rate_utilization": {
        "poor": 60,
        "average": 75,
        "excellent": 85,
        "note": "% of billed hours vs available hours",
    },
}


class MechanicProfile(BaseProfile):
    name = "Auto Repair Shop"
    benchmarks = MECHANIC_BENCHMARKS

    @classmethod
    def score(cls, pl_statement):
        return score_against_benchmark(pl_statement, cls.benchmarks, cls.name)
