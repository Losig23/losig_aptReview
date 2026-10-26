"""Price comparison against a manually collected sample CSV.

The sample is deliberately small and local: it is the set of listings
recorded in ``data/sample_listings.csv`` (no personal data, no landlord
contact details). Medians are computed from that file only. They are
not a live market index and they are not scraped data.

Comparable selection, in order:
  1. same neighbourhood + same number of beds, if at least 3 rows;
  2. same city + same number of beds, if at least 3 rows;
  3. same neighbourhood, any beds, if at least 3 rows;
  4. same city, any beds, if at least 3 rows;
  5. otherwise: no comparable -- no price flag is raised.

Step 2 comes before step 3 on purpose: a studio compared to a
neighbourhood median that mixes studios with two-bedrooms would be
flagged as "below median" for being small, not for being cheap.
Matching beds first keeps the comparison about price, not size.

A price flag is raised when the listing rent is at least 20% below the
comparable median rent, or its rent per sqft is at least 20% below the
comparable median rent per sqft (when sqft is known).
"""

import csv
import statistics
from collections import namedtuple

PRICE_THRESHOLD_PCT = 20.0
MIN_COMPARABLES = 3

PriceBasis = namedtuple(
    "PriceBasis", ["kind", "neighborhood", "city", "beds", "n"]
)


def _norm(text):
    return (text or "").strip().lower()


def load_sample_listings(path):
    """Load sample listings from a CSV file.

    Expected columns: id, city, neighborhood, beds, baths, sqft, rent.
    Rows with a missing or non-positive rent are skipped.
    """
    rows = []
    with open(path, newline="", encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            try:
                rent = float(row["rent"])
                beds = int(float(row["beds"]))
            except (KeyError, TypeError, ValueError):
                continue
            if rent <= 0:
                continue
            try:
                sqft = int(float(row["sqft"])) if row.get("sqft") else None
            except (TypeError, ValueError):
                sqft = None
            if sqft is not None and sqft <= 0:
                sqft = None
            try:
                baths = float(row["baths"]) if row.get("baths") else None
            except (TypeError, ValueError):
                baths = None
            rows.append(
                {
                    "id": row.get("id", ""),
                    "city": row.get("city", ""),
                    "neighborhood": row.get("neighborhood", ""),
                    "beds": beds,
                    "baths": baths,
                    "sqft": sqft,
                    "rent": rent,
                }
            )
    return rows


def median_price(rows):
    """Return (median rent, median rent/sqft) for a list of sample rows."""
    if not rows:
        return None, None
    median_rent = statistics.median([row["rent"] for row in rows])
    per_sqft = [
        row["rent"] / row["sqft"]
        for row in rows
        if row["sqft"] is not None and row["sqft"] > 0
    ]
    median_psf = statistics.median(per_sqft) if per_sqft else None
    return median_rent, median_psf


def _pct_below(listing_value, median_value):
    if listing_value is None or median_value in (None, 0):
        return None
    return (median_value - listing_value) / median_value * 100.0


def compare_price(listing, sample_rows):
    """Compare a listing to the best available comparable set.

    ``listing`` is a mapping (or object) with rent, beds, neighborhood
    and city attributes/keys, plus optional sqft. Returns a dict with
    the comparison numbers, the basis used, and whether the price flag
    fires. When no comparable set exists, ``median_rent`` is None and
    ``flagged`` is False -- absence of data is never treated as a flag.
    """
    if isinstance(listing, dict):
        rent = listing.get("rent")
        beds = listing.get("beds")
        sqft = listing.get("sqft")
        neighborhood = listing.get("neighborhood", "")
        city = listing.get("city", "")
    else:
        rent = getattr(listing, "rent", None)
        beds = getattr(listing, "beds", None)
        sqft = getattr(listing, "sqft", None)
        neighborhood = getattr(listing, "neighborhood", "")
        city = getattr(listing, "city", "")

    neighborhood_norm = _norm(neighborhood)
    city_norm = _norm(city)

    same_nbhd = [r for r in sample_rows if _norm(r["neighborhood"]) == neighborhood_norm]
    same_nbhd_beds = [r for r in same_nbhd if beds is not None and r["beds"] == beds]
    same_city = [r for r in sample_rows if _norm(r["city"]) == city_norm]
    same_city_beds = [r for r in same_city if beds is not None and r["beds"] == beds]

    if len(same_nbhd_beds) >= MIN_COMPARABLES:
        comparables, basis = same_nbhd_beds, PriceBasis(
            "neighborhood + beds", neighborhood, city, beds, len(same_nbhd_beds)
        )
    elif len(same_city_beds) >= MIN_COMPARABLES:
        comparables, basis = same_city_beds, PriceBasis(
            "city + beds", neighborhood, city, beds, len(same_city_beds)
        )
    elif len(same_nbhd) >= MIN_COMPARABLES:
        comparables, basis = same_nbhd, PriceBasis(
            "neighborhood (all beds)", neighborhood, city, None, len(same_nbhd)
        )
    elif len(same_city) >= MIN_COMPARABLES:
        comparables, basis = same_city, PriceBasis(
            "city (all neighborhoods)", neighborhood, city, None, len(same_city)
        )
    else:
        return {
            "basis": None,
            "n": 0,
            "median_rent": None,
            "median_rent_per_sqft": None,
            "listing_rent": rent,
            "listing_rent_per_sqft": None,
            "pct_below_median_rent": None,
            "pct_below_median_per_sqft": None,
            "flagged": False,
            "reason": "No comparable sample (fewer than %d listings) -- "
            "no price flag raised." % MIN_COMPARABLES,
        }

    median_rent, median_psf = median_price(comparables)
    listing_psf = (rent / sqft) if (rent and sqft) else None
    pct_rent = _pct_below(rent, median_rent)
    pct_psf = _pct_below(listing_psf, median_psf)
    flagged = bool(
        (pct_rent is not None and pct_rent >= PRICE_THRESHOLD_PCT)
        or (pct_psf is not None and pct_psf >= PRICE_THRESHOLD_PCT)
    )
    return {
        "basis": basis,
        "n": len(comparables),
        "median_rent": median_rent,
        "median_rent_per_sqft": median_psf,
        "listing_rent": rent,
        "listing_rent_per_sqft": listing_psf,
        "pct_below_median_rent": pct_rent,
        "pct_below_median_per_sqft": pct_psf,
        "flagged": flagged,
        "reason": None,
    }
