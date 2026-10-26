"""RentTrust: a transparent rental-listing trust scorer.

The scorer never delivers a verdict about a person or a listing. It
returns a tier (GREEN / CHECK / RED) plus the specific flags that
warrant verification, and it always shows a verification checklist.
"""

from .scorer import Flag, Listing, PriceComparison, ScoreResult, score_listing
from .price import PriceBasis, load_sample_listings, median_price

__all__ = [
    "Flag",
    "Listing",
    "PriceBasis",
    "PriceComparison",
    "ScoreResult",
    "load_sample_listings",
    "median_price",
    "score_listing",
]

__version__ = "0.1.0"
