import json
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from renttrust.evaluate import evaluate_file
from renttrust.price import compare_price, load_sample_listings
from renttrust.scorer import Listing, score_listing

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SAMPLE = os.path.join(ROOT, "data", "sample_listings.csv")
LABELED = os.path.join(ROOT, "data", "labeled_test_set.json")


class TestScorerIntegration(unittest.TestCase):
    def test_clean_demo_scores_green_with_checklist(self):
        with open(os.path.join(ROOT, "demo", "clean_listing.json")) as handle:
            listing = Listing.from_dict(json.load(handle))
        sample = load_sample_listings(SAMPLE)
        result = score_listing(listing, price=compare_price(listing.to_dict(), sample))
        self.assertEqual(result.tier, "GREEN")
        self.assertEqual(result.flags, [])
        self.assertEqual(len(result.checklist), 5)
        self.assertIn("property-tax", result.checklist[1])

    def test_red_flag_demo_scores_red(self):
        with open(os.path.join(ROOT, "demo", "red_flag_listing.json")) as handle:
            listing = Listing.from_dict(json.load(handle))
        sample = load_sample_listings(SAMPLE)
        result = score_listing(listing, price=compare_price(listing.to_dict(), sample))
        self.assertEqual(result.tier, "RED")
        ids = {flag.id for flag in result.flags}
        self.assertIn("deposit_before_viewing_or_lease", ids)
        self.assertIn("irreversible_payment", ids)
        self.assertIn("landlord_abroad_cannot_show", ids)
        self.assertIn("viewing_refused", ids)
        self.assertIn("price_below_median", ids)

    def test_output_never_accuses_a_named_person(self):
        # The disclaimer and flag wording must frame results as
        # flags warranting verification, never as an accusation.
        listing = Listing(rent=1750, beds=1, sqft=650,
                          neighborhood="Mission District",
                          payment_method="wire", viewing="none",
                          deposit_before_viewing=True)
        result = score_listing(listing, price={"flagged": True,
                                               "pct_below_median_rent": 39.0,
                                               "median_rent": 2875.0, "basis": None,
                                               "n": 4, "median_rent_per_sqft": None,
                                               "listing_rent": 1750,
                                               "listing_rent_per_sqft": 2.69,
                                               "pct_below_median_per_sqft": None})
        text = result.disclaimer + " ".join(f.detail for f in result.flags)
        self.assertNotIn("scammer", text.lower())
        self.assertNotIn("is a scam", text.lower())
        self.assertIn("warrant", result.disclaimer.lower())


class TestLabeledEvaluation(unittest.TestCase):
    def test_labeled_set_has_20_cases(self):
        with open(LABELED, encoding="utf-8") as handle:
            payload = json.load(handle)
        self.assertEqual(len(payload["cases"]), 20)
        labels = [c["label"] for c in payload["cases"]]
        self.assertEqual(labels.count("scam-pattern"), 10)
        self.assertEqual(labels.count("legitimate"), 10)

    def test_labeled_set_has_no_personal_data(self):
        with open(LABELED, encoding="utf-8") as handle:
            text = handle.read()
        for banned in ("ssn", "bank account", "driver"):
            self.assertNotIn(banned, text.lower())

    def test_evaluation_metrics(self):
        metrics = evaluate_file(LABELED, SAMPLE)
        # Every scam-pattern case is flagged; the only legitimate case
        # flagged is the deliberate borderline weak-flags case (L10).
        self.assertEqual(metrics["flag_recall_pct"], 100.0)
        self.assertEqual(metrics["false_positive_rate_pct"], 10.0)
        self.assertEqual(metrics["red_false_positive_rate_pct"], 0.0)
        self.assertEqual(metrics["expected_flag_recall_pct"], 100.0)
        # Every case scores its expected tier.
        self.assertTrue(all(c["tier_matches_expected"] for c in metrics["cases"]))


if __name__ == "__main__":
    unittest.main()
