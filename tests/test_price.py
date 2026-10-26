import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from renttrust.price import compare_price, load_sample_listings, median_price

DATA = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                    "data", "sample_listings.csv")


def listing(**kwargs):
    base = {"rent": 2900, "beds": 1, "sqft": 680,
            "neighborhood": "Mission District", "city": "San Francisco"}
    base.update(kwargs)
    return base


class TestPriceComparison(unittest.TestCase):
    def setUp(self):
        self.sample = load_sample_listings(DATA)

    def test_sample_has_20_to_50_rows_and_no_contact_columns(self):
        self.assertGreaterEqual(len(self.sample), 20)
        self.assertLessEqual(len(self.sample), 50)
        with open(DATA, encoding="utf-8") as handle:
            header = handle.readline()
        for banned in ("email", "phone", "landlord", "ssn", "bank"):
            self.assertNotIn(banned, header.lower())

    def test_median_price(self):
        median_rent, median_psf = median_price(self.sample[:4])
        # Mission 1-beds in the sample: 2800, 2950, 3100, 2650
        self.assertEqual(median_rent, 2875.0)
        self.assertIsNotNone(median_psf)

    def test_below_median_by_20_percent_flags(self):
        # Mission 1-bed median is 2875; 20% below is 2300.
        result = compare_price(listing(rent=2000), self.sample)
        self.assertTrue(result["flagged"])
        self.assertEqual(result["median_rent"], 2875.0)
        self.assertGreaterEqual(result["pct_below_median_rent"], 20.0)

    def test_exactly_20_percent_below_flags(self):
        result = compare_price(listing(rent=2300), self.sample)
        self.assertTrue(result["flagged"])

    def test_just_above_threshold_does_not_flag(self):
        result = compare_price(listing(rent=2350), self.sample)
        # 2350 is 18.3% below 2875, and its $/sqft is near the median.
        self.assertFalse(result["flagged"])

    def test_at_or_above_median_does_not_flag(self):
        result = compare_price(listing(rent=2900), self.sample)
        self.assertFalse(result["flagged"])

    def test_rent_per_sqft_below_threshold_flags(self):
        # Rent is only ~10% below median, but $/sqft is far below
        # because the unit is unusually large for its rent.
        result = compare_price(listing(rent=2600, sqft=1200), self.sample)
        self.assertTrue(result["flagged"])

    def test_same_beds_preferred_over_neighborhood_mix(self):
        # A Hayes Valley studio must not be compared to a median that
        # mixes studios with two-bedrooms in that neighbourhood.
        result = compare_price(
            listing(rent=2250, beds=0, sqft=470,
                    neighborhood="Hayes Valley"), self.sample)
        self.assertEqual(result["basis"].kind, "city + beds")
        self.assertFalse(result["flagged"])

    def test_no_comparable_means_no_price_flag(self):
        result = compare_price(
            listing(rent=500, neighborhood="Nowhere", city="Nowhere"), self.sample)
        self.assertFalse(result["flagged"])
        self.assertIsNone(result["median_rent"])

    def test_missing_sqft_uses_rent_only(self):
        result = compare_price(listing(rent=2000, sqft=None), self.sample)
        self.assertTrue(result["flagged"])
        self.assertIsNone(result["pct_below_median_per_sqft"])


if __name__ == "__main__":
    unittest.main()
