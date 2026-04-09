"""
base_profile.py
===============
Base industry profile with generic benchmarks.
Subclass this for specific industries.
"""

from decimal import Decimal
from typing import Dict, List

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


GENERAL_BENCHMARKS = {
    "gross_margin_pct": {
        "low": 30,
        "healthy": 45,
        "excellent": 60,
        "note": "Varies widely by industry",
    },
    "operating_margin_pct": {
        "low": 5,
        "healthy": 15,
        "excellent": 25,
        "note": "Above 15% is generally strong",
    },
    "net_margin_pct": {
        "struggling": 3,
        "average": 8,
        "healthy": 15,
        "excellent": 20,
    },
    "rent_pct_of_revenue": {
        "ideal": 8,
        "warning": 12,
        "critical": 15,
        "note": "Above 15% is a location cost problem",
    },
    "cogs_pct": {
        "low": 25,
        "healthy": 40,
        "high": 60,
        "note": "Service businesses are lower, product businesses higher",
    },
}


def score_against_benchmark(pl_statement, benchmarks: Dict, industry: str = "general") -> Dict:
    """
    Compare a PLStatement against industry benchmarks.
    Returns a scorecard with green/yellow/red flags.
    """
    scorecard: Dict = {"industry": industry, "metrics": {}}

    # Gross Margin
    gm = float(pl_statement.gross_margin_pct)
    gm_bench = benchmarks.get("gross_margin_pct", {})
    if gm_bench:
        if gm >= gm_bench.get("excellent", 999):
            scorecard["metrics"]["gross_margin"] = {
                "status": "EXCELLENT", "value": gm,
                "benchmark": gm_bench["excellent"], "flag": "green",
            }
        elif gm >= gm_bench.get("healthy", 999):
            scorecard["metrics"]["gross_margin"] = {
                "status": "HEALTHY", "value": gm,
                "benchmark": gm_bench["healthy"], "flag": "green",
            }
        elif gm >= gm_bench.get("low", 0):
            gap = gm_bench.get("healthy", 0) - gm
            scorecard["metrics"]["gross_margin"] = {
                "status": "BELOW AVERAGE", "value": gm,
                "benchmark": gm_bench["healthy"], "flag": "yellow",
                "action": f"Gross margin is {gap:.1f}% below target. Review {industry} COGS.",
            }
        else:
            scorecard["metrics"]["gross_margin"] = {
                "status": "CRITICAL", "value": gm,
                "benchmark": gm_bench.get("low", 0), "flag": "red",
                "action": "Immediate cost review needed",
            }

    # Net Margin
    nm = float(pl_statement.net_margin_pct)
    nm_bench = benchmarks.get("net_margin_pct", {})
    if nm_bench:
        if nm >= nm_bench.get("excellent", 999):
            scorecard["metrics"]["net_margin"] = {
                "status": "EXCELLENT", "value": nm, "flag": "green",
            }
        elif nm >= nm_bench.get("healthy", 999):
            scorecard["metrics"]["net_margin"] = {
                "status": "HEALTHY", "value": nm, "flag": "green",
            }
        elif nm >= nm_bench.get("average", nm_bench.get("struggling", 0)):
            scorecard["metrics"]["net_margin"] = {
                "status": "AVERAGE", "value": nm, "flag": "yellow",
                "action": "Look for OPEX savings to improve bottom line",
            }
        else:
            scorecard["metrics"]["net_margin"] = {
                "status": "STRUGGLING", "value": nm, "flag": "red",
                "action": "Business profitability needs immediate attention",
            }

    # Rent ratio
    rent_pct = float(pl_statement.rent_pct)
    rent_bench = benchmarks.get("rent_pct_of_revenue", {})
    if rent_bench and rent_pct > 0:
        if rent_pct <= rent_bench.get("ideal", 8):
            scorecard["metrics"]["rent"] = {
                "status": "IDEAL", "value": rent_pct, "flag": "green",
            }
        elif rent_pct <= rent_bench.get("warning", 12):
            scorecard["metrics"]["rent"] = {
                "status": "ACCEPTABLE", "value": rent_pct, "flag": "yellow",
                "action": "Rent approaching warning threshold",
            }
        else:
            scorecard["metrics"]["rent"] = {
                "status": "TOO HIGH", "value": rent_pct, "flag": "red",
                "action": f"Rent is {rent_pct:.1f}% of revenue — negotiate or relocate",
            }

    # COGS ratio
    cogs = float(pl_statement.cogs_pct)
    cogs_bench = benchmarks.get("cogs_pct", {})
    if cogs_bench and cogs > 0:
        if cogs <= cogs_bench.get("low", 25):
            scorecard["metrics"]["cogs"] = {
                "status": "LOW", "value": cogs, "flag": "green",
                "action": "Verify all direct costs are captured in COGS",
            }
        elif cogs <= cogs_bench.get("healthy", 40):
            scorecard["metrics"]["cogs"] = {
                "status": "HEALTHY", "value": cogs, "flag": "green",
            }
        elif cogs <= cogs_bench.get("high", 60):
            scorecard["metrics"]["cogs"] = {
                "status": "ELEVATED", "value": cogs, "flag": "yellow",
                "action": "Review supplier pricing and waste",
            }
        else:
            scorecard["metrics"]["cogs"] = {
                "status": "CRITICAL", "value": cogs, "flag": "red",
                "action": "Direct costs consuming too much revenue",
            }

    # Overall health
    flags = [m.get("flag") for m in scorecard["metrics"].values()]
    if "red" in flags:
        scorecard["overall"] = "NEEDS ATTENTION"
    elif "yellow" in flags:
        scorecard["overall"] = "ROOM FOR IMPROVEMENT"
    else:
        scorecard["overall"] = "HEALTHY"

    return scorecard


class BaseProfile:
    """Generic industry profile."""
    name = "General Business"
    benchmarks = GENERAL_BENCHMARKS

    @classmethod
    def score(cls, pl_statement) -> Dict:
        return score_against_benchmark(pl_statement, cls.benchmarks, cls.name)

    @classmethod
    def recommendations(cls, scorecard: Dict) -> List[str]:
        """Generate top action items from the scorecard."""
        recs = []
        for metric, data in scorecard.get("metrics", {}).items():
            if data.get("flag") in ("red", "yellow") and data.get("action"):
                recs.append(data["action"])
        return recs[:5]  # top 5
