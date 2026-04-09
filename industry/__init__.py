from .base_profile import BaseProfile, score_against_benchmark
from .bakery import BAKERY_BENCHMARKS, BakeryProfile
from .mechanic import MECHANIC_BENCHMARKS, MechanicProfile

INDUSTRY_PROFILES = {
    "bakery": BakeryProfile,
    "mechanic": MechanicProfile,
    "general": BaseProfile,
}

__all__ = [
    "BaseProfile",
    "BakeryProfile",
    "MechanicProfile",
    "BAKERY_BENCHMARKS",
    "MECHANIC_BENCHMARKS",
    "INDUSTRY_PROFILES",
    "score_against_benchmark",
]
