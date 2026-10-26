import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from renttrust.scorer import Listing, detect_flags, tier_for_flags


def clean(**kwargs):
    base = {
        "rent": 2900, "beds": 1, "sqft": 680,
        "neighborhood": "Mission District", "city": "San Francisco",
        "payment_method": "check", "viewing": "in-person",
        "contact_email": "leasing@example-property.com",
    }
    base.update(kwargs)
    return Listing(**base)


def flag_ids(listing, price=None):
    return {flag.id: flag for flag in detect_flags(listing, price=price)}


class TestStrongFlags(unittest.TestCase):
    def test_deposit_before_viewing(self):
        flags = flag_ids(clean(deposit_before_viewing=True))
        self.assertIn("deposit_before_viewing_or_lease", flags)
        self.assertEqual(flags["deposit_before_viewing_or_lease"].weight, "strong")

    def test_deposit_before_lease(self):
        flags = flag_ids(clean(deposit_before_lease=True))
        self.assertIn("deposit_before_viewing_or_lease", flags)

    def test_irreversible_payments(self):
        for method in ("wire", "wire transfer", "gift-card", "crypto", "bitcoin"):
            flags = flag_ids(clean(payment_method=method))
            self.assertIn("irreversible_payment", flags, method)
            self.assertEqual(flags["irreversible_payment"].weight, "strong")

    def test_reversible_payments_do_not_flag(self):
        for method in ("check", "bank-transfer", "credit card", ""):
            flags = flag_ids(clean(payment_method=method))
            self.assertNotIn("irreversible_payment", flags, method)

    def test_landlord_abroad_and_cannot_show(self):
        flags = flag_ids(clean(landlord_abroad=True, cannot_show=True))
        self.assertIn("landlord_abroad_cannot_show", flags)

    def test_landlord_abroad_alone_does_not_flag(self):
        # An owner abroad with a local agent who shows the unit is
        # not, by itself, a flag.
        flags = flag_ids(clean(landlord_abroad=True, cannot_show=False))
        self.assertNotIn("landlord_abroad_cannot_show", flags)

    def test_cannot_show_alone_does_not_flag_abroad_flag(self):
        flags = flag_ids(clean(landlord_abroad=False, cannot_show=True))
        self.assertNotIn("landlord_abroad_cannot_show", flags)

    def test_duplicate_listing(self):
        flags = flag_ids(clean(duplicate_listing=True))
        self.assertEqual(flags["duplicate_listing"].weight, "strong")

    def test_listed_for_sale_elsewhere(self):
        flags = flag_ids(clean(listed_for_sale_elsewhere=True))
        self.assertEqual(flags["listed_for_sale_elsewhere"].weight, "strong")

    def test_viewing_none_is_refusal(self):
        flags = flag_ids(clean(viewing="none"))
        self.assertIn("viewing_refused", flags)
        self.assertEqual(flags["viewing_refused"].weight, "strong")

    def test_self_tour_only_is_refusal(self):
        flags = flag_ids(clean(viewing="self-tour"))
        self.assertIn("viewing_refused", flags)

    def test_in_person_and_live_video_are_not_refusals(self):
        for viewing in ("in-person", "live-video"):
            flags = flag_ids(clean(viewing=viewing))
            self.assertNotIn("viewing_refused", flags, viewing)

    def test_price_below_median_is_strong(self):
        price = {"flagged": True, "pct_below_median_rent": 30.0,
                 "median_rent": 2875.0, "basis": None}
        flags = flag_ids(clean(), price=price)
        self.assertIn("price_below_median", flags)
        self.assertEqual(flags["price_below_median"].weight, "strong")

    def test_no_price_flag_when_price_not_flagged(self):
        price = {"flagged": False, "pct_below_median_rent": 5.0,
                 "median_rent": 2875.0, "basis": None}
        flags = flag_ids(clean(), price=price)
        self.assertNotIn("price_below_median", flags)


class TestWeakFlags(unittest.TestCase):
    def test_urgency_from_text(self):
        flags = flag_ids(clean(
            listing_text="Act now, another applicant is about to pay."))
        self.assertIn("urgency_pressure", flags)
        self.assertEqual(flags["urgency_pressure"].weight, "weak")

    def test_urgency_from_explicit_flag(self):
        flags = flag_ids(clean(urgency=True))
        self.assertIn("urgency_pressure", flags)

    def test_plain_text_has_no_urgency(self):
        flags = flag_ids(clean(listing_text="One bedroom, in-person tours."))
        self.assertNotIn("urgency_pressure", flags)

    def test_free_email_is_weak_only(self):
        for email in ("a@gmail.com", "a@yahoo.com", "a@outlook.com"):
            flags = flag_ids(clean(contact_email=email))
            self.assertIn("free_email_contact", flags, email)
            self.assertEqual(flags["free_email_contact"].weight, "weak")

    def test_property_domain_email_does_not_flag(self):
        flags = flag_ids(clean(contact_email="leasing@example-property.com"))
        self.assertNotIn("free_email_contact", flags)

    def test_name_mismatch_is_weak_only(self):
        flags = flag_ids(clean(name_mismatch=True))
        self.assertIn("name_mismatch", flags)
        self.assertEqual(flags["name_mismatch"].weight, "weak")


class TestTiering(unittest.TestCase):
    def test_no_flags_is_green(self):
        self.assertEqual(tier_for_flags(detect_flags(clean())), "GREEN")

    def test_one_strong_flag_is_check_not_red(self):
        self.assertEqual(
            tier_for_flags(detect_flags(clean(deposit_before_viewing=True))),
            "CHECK")

    def test_two_strong_flags_is_red(self):
        listing = clean(deposit_before_viewing=True, payment_method="wire")
        self.assertEqual(tier_for_flags(detect_flags(listing)), "RED")

    def test_weak_flags_alone_never_red(self):
        listing = clean(urgency=True, name_mismatch=True,
                        contact_email="a@gmail.com")
        self.assertEqual(tier_for_flags(detect_flags(listing)), "CHECK")

    def test_no_grammar_or_language_flag_exists(self):
        # The scorer must never flag wording, spelling, or accent.
        # This test pins that rule: a listing with unusual English and
        # no other signals scores GREEN.
        listing = clean(listing_text="This house is very good, you come see, ok?")
        flags = detect_flags(listing)
        self.assertEqual(flags, [])
        self.assertEqual(tier_for_flags(flags), "GREEN")


if __name__ == "__main__":
    unittest.main()
