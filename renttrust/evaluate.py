"""Evaluate the scorer on the anonymized labeled test set.

Metrics reported (both, always -- a scorer that flags everything is
useless, so recall alone is not enough):
  * flag recall on scam-pattern cases: share flagged CHECK or RED.
  * RED recall on scam-pattern cases: share flagged RED.
  * expected-flag recall: share of the flags each scam-pattern case
    was constructed to exhibit that the scorer actually detects.
  * false-positive rate on legitimate cases: share flagged CHECK or
    RED, and separately the share flagged RED.

The labeled cases are reconstructed from FTC-style scam patterns,
not real victims' listings, and the legitimate cases are ordinary
listings. With only ~20 cases these numbers describe this test set
only; they are not an estimate of real-world accuracy.
"""

import json
import os

from .price import compare_price, load_sample_listings
from .scorer import Listing, score_listing

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEFAULT_SAMPLE_CSV = os.path.join(REPO_ROOT, "data", "sample_listings.csv")


def _pct(numerator, denominator):
    return (numerator / denominator * 100.0) if denominator else 0.0


def evaluate_cases(cases, sample_rows):
    scam = [c for c in cases if c.get("label") == "scam-pattern"]
    legit = [c for c in cases if c.get("label") == "legitimate"]
    rows = []
    expected_total = 0
    expected_detected = 0

    for case in cases:
        listing = Listing.from_dict(case.get("listing", {}))
        price = compare_price(listing.to_dict(), sample_rows)
        result = score_listing(listing, price=price)
        detected = {flag.id for flag in result.flags}
        expected = case.get("expected_flags", [])
        if case.get("label") == "scam-pattern":
            expected_total += len(expected)
            expected_detected += len([f for f in expected if f in detected])
        rows.append(
            {
                "id": case.get("id"),
                "label": case.get("label"),
                "tier": result.tier,
                "expected_tier": case.get("expected_tier"),
                "flags": sorted(detected),
                "expected_flags": expected,
                "tier_matches_expected": result.tier == case.get("expected_tier"),
            }
        )

    scam_flagged = sum(1 for r in rows if r["label"] == "scam-pattern" and r["tier"] in ("CHECK", "RED"))
    scam_red = sum(1 for r in rows if r["label"] == "scam-pattern" and r["tier"] == "RED")
    legit_flagged = sum(1 for r in rows if r["label"] == "legitimate" and r["tier"] in ("CHECK", "RED"))
    legit_red = sum(1 for r in rows if r["label"] == "legitimate" and r["tier"] == "RED")

    return {
        "n_total": len(cases),
        "n_scam_pattern": len(scam),
        "n_legitimate": len(legit),
        "scam_flagged": scam_flagged,
        "scam_red": scam_red,
        "flag_recall_pct": _pct(scam_flagged, len(scam)),
        "red_recall_pct": _pct(scam_red, len(scam)),
        "expected_flags_detected": expected_detected,
        "expected_flags_total": expected_total,
        "expected_flag_recall_pct": _pct(expected_detected, expected_total),
        "legit_flagged": legit_flagged,
        "legit_red": legit_red,
        "false_positive_rate_pct": _pct(legit_flagged, len(legit)),
        "red_false_positive_rate_pct": _pct(legit_red, len(legit)),
        "cases": rows,
    }


def evaluate_file(labeled_path, sample_csv=None):
    with open(labeled_path, encoding="utf-8") as handle:
        payload = json.load(handle)
    cases = payload["cases"] if isinstance(payload, dict) else payload
    sample_path = sample_csv or DEFAULT_SAMPLE_CSV
    sample_rows = load_sample_listings(sample_path)
    return evaluate_cases(cases, sample_rows)
