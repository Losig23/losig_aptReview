"""Command-line interface for RentTrust.

Usage (from the repo root):

    python -m renttrust score --rent 2900 --beds 1 --sqft 650 \\
        --neighborhood "Mission District" --viewing in-person --payment check

    python -m renttrust score --input demo/clean_listing.json
    python -m renttrust score --input demo/red_flag_listing.json --json
    python -m renttrust evaluate
    python -m renttrust score --interactive

No field in this CLI accepts SSN, bank details, or ID numbers. Do not
paste personal data into a listing; the scorer only needs the listing
itself, the contact channel, the payment method requested, and whether
a viewing is offered.
"""

import argparse
import json
import os
import sys

from .price import compare_price, load_sample_listings
from .scorer import (
    TIER_DESCRIPTIONS,
    Listing,
    score_listing,
)

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEFAULT_SAMPLE_CSV = os.path.join(REPO_ROOT, "data", "sample_listings.csv")
DEFAULT_LABELED = os.path.join(REPO_ROOT, "data", "labeled_test_set.json")


def _resolve_sample_csv(path):
    if path:
        return path
    # Allow running from the repo root (data/sample_listings.csv) as well
    # as from anywhere else (the copy bundled next to this package).
    if os.path.exists(DEFAULT_SAMPLE_CSV):
        return DEFAULT_SAMPLE_CSV
    local = os.path.join(os.getcwd(), "data", "sample_listings.csv")
    return local


def _load_price(listing, sample_csv, no_price):
    if no_price:
        return None
    path = _resolve_sample_csv(sample_csv)
    if not os.path.exists(path):
        return None
    sample = load_sample_listings(path)
    return compare_price(listing.to_dict(), sample)


def _result_to_dict(result):
    price = result.price
    return {
        "tier": result.tier,
        "tier_description": TIER_DESCRIPTIONS[result.tier],
        "flags": [
            {
                "id": flag.id,
                "weight": flag.weight,
                "title": flag.title,
                "detail": flag.detail,
                "verify": flag.verify,
            }
            for flag in result.flags
        ],
        "price_comparison": (
            {
                "basis": (
                    {"kind": price.basis.kind, "n": price.basis.n}
                    if price.basis is not None
                    else None
                ),
                "n": price.n,
                "median_rent": price.median_rent,
                "median_rent_per_sqft": price.median_rent_per_sqft,
                "listing_rent": price.listing_rent,
                "listing_rent_per_sqft": price.listing_rent_per_sqft,
                "pct_below_median_rent": price.pct_below_median_rent,
                "pct_below_median_per_sqft": price.pct_below_median_per_sqft,
                "flagged": price.flagged,
            }
            if price is not None
            else None
        ),
        "verification_checklist": result.checklist,
        "disclaimer": result.disclaimer,
    }


def _print_result(result, listing):
    print("=" * 64)
    print("RentTrust v0.1 -- %s" % result.tier)
    print(TIER_DESCRIPTIONS[result.tier])
    print("=" * 64)
    print(
        "Listing: %s-bed, %s, %s"
        % (
            listing.beds if listing.beds is not None else "?",
            listing.neighborhood or "?",
            listing.city or "?",
        )
    )
    if listing.rent is not None:
        rent_text = "$%.0f" % listing.rent
        if listing.sqft:
            rent_text += "  (%.2f/sqft, %d sqft)" % (
                listing.rent / listing.sqft,
                listing.sqft,
            )
        print("Rent: %s" % rent_text)
    print("Viewing: %s | Payment requested: %s" % (listing.viewing, listing.payment_method or "not stated"))
    print("")
    if result.price is not None:
        price = result.price
        if price.median_rent is None:
            print("Price check: no comparable sample -- no price flag raised.")
        else:
            print(
                "Price check: median for %s is $%.0f (n=%d)."
                % (price.basis.kind, price.median_rent, price.n)
            )
            if price.pct_below_median_rent is not None:
                print(
                    "  This listing is %.1f%% %s the median rent."
                    % (
                        abs(price.pct_below_median_rent),
                        "below" if price.pct_below_median_rent >= 0 else "above",
                    )
                )
            if price.median_rent_per_sqft and price.listing_rent_per_sqft:
                print(
                    "  Rent/sqft: $%.2f vs median $%.2f (%.1f%% %s)."
                    % (
                        price.listing_rent_per_sqft,
                        price.median_rent_per_sqft,
                        abs(price.pct_below_median_per_sqft or 0),
                        "below"
                        if (price.pct_below_median_per_sqft or 0) >= 0
                        else "above",
                    )
                )
        print("")
    if result.flags:
        print("Flags found (%d):" % len(result.flags))
        for flag in result.flags:
            print("  [%s] %s" % (flag.weight.upper(), flag.title))
            print("        %s" % flag.detail)
            print("        Verify: %s" % flag.verify)
    else:
        print("Flags found: none.")
    print("")
    print("Verification checklist (always do these before paying):")
    for item in result.checklist:
        print("  - %s" % item)
    print("")
    print(result.disclaimer)


def _prompt_listing():
    print("Enter the listing (press Enter to leave a field blank).")
    print("Do not enter SSN, bank details, or ID numbers.")

    def ask(prompt):
        try:
            return input(prompt).strip()
        except EOFError:
            return ""

    def ask_int(prompt):
        value = ask(prompt)
        try:
            return int(float(value)) if value else None
        except ValueError:
            return None

    def ask_float(prompt):
        value = ask(prompt)
        try:
            return float(value) if value else None
        except ValueError:
            return None

    def ask_bool(prompt):
        return ask(prompt + " (y/N): ").lower() in ("y", "yes")

    return Listing(
        rent=ask_float("Rent ($): "),
        beds=ask_int("Beds: "),
        baths=ask_float("Baths: "),
        sqft=ask_int("Sqft: "),
        neighborhood=ask("Neighborhood: "),
        city=ask("City [San Francisco]: ") or "San Francisco",
        listing_text=ask("Listing text (paste): "),
        amenities_text=ask("Amenities text: "),
        contact_channel=ask("Landlord contact channel (email/phone/messaging): "),
        contact_email=ask("Contact email (if any): "),
        payment_method=ask("Payment method requested: "),
        viewing=ask("Viewing offered (in-person / live-video / none / self-tour): ")
        or "in-person",
        deposit_before_viewing=ask_bool("Deposit requested before viewing?"),
        deposit_before_lease=ask_bool("Deposit requested before a signed lease?"),
        landlord_abroad=ask_bool("Landlord described as out of the country?"),
        cannot_show=ask_bool("Landlord cannot show the unit?"),
        duplicate_listing=ask_bool("Same listing under different names/details elsewhere?"),
        listed_for_sale_elsewhere=ask_bool("Property listed for sale elsewhere?"),
        urgency=ask_bool("Urgency pressure in the listing/messages?"),
        name_mismatch=ask_bool("Contact name mismatch?"),
    )


def _score_args(parser):
    parser.add_argument("--rent", type=float, default=None)
    parser.add_argument("--beds", type=int, default=None)
    parser.add_argument("--baths", type=float, default=None)
    parser.add_argument("--sqft", type=int, default=None)
    parser.add_argument("--neighborhood", default="")
    parser.add_argument("--city", default="San Francisco")
    parser.add_argument("--listing-text", default="")
    parser.add_argument("--listing-file", default=None,
                        help="File containing listing text to paste in")
    parser.add_argument("--amenities-text", default="")
    parser.add_argument("--contact-channel", default="")
    parser.add_argument("--contact-email", default="")
    parser.add_argument("--payment-method", default="", dest="payment_method")
    parser.add_argument("--payment", default=None,
                        help="Alias for --payment-method")
    parser.add_argument("--viewing", default="in-person",
                        choices=["in-person", "live-video", "none", "self-tour"])
    parser.add_argument("--deposit-before-viewing", action="store_true")
    parser.add_argument("--deposit-before-lease", action="store_true")
    parser.add_argument("--landlord-abroad", action="store_true")
    parser.add_argument("--cannot-show", action="store_true")
    parser.add_argument("--duplicate-listing", action="store_true")
    parser.add_argument("--listed-for-sale-elsewhere", action="store_true")
    parser.add_argument("--urgency", action="store_true")
    parser.add_argument("--name-mismatch", action="store_true")
    parser.add_argument("--input", default=None,
                        help="JSON file with listing fields")
    parser.add_argument("--interactive", action="store_true")
    parser.add_argument("--sample-csv", default=None)
    parser.add_argument("--no-price-check", action="store_true")
    parser.add_argument("--json", action="store_true")


def _cmd_score(args):
    if args.interactive:
        listing = _prompt_listing()
    elif args.input:
        with open(args.input, encoding="utf-8") as handle:
            listing = Listing.from_dict(json.load(handle))
    else:
        listing_text = args.listing_text
        if args.listing_file:
            with open(args.listing_file, encoding="utf-8") as handle:
                listing_text = handle.read()
        payment = args.payment_method or args.payment or ""
        listing = Listing(
            rent=args.rent,
            beds=args.beds,
            baths=args.baths,
            sqft=args.sqft,
            neighborhood=args.neighborhood,
            city=args.city,
            listing_text=listing_text,
            amenities_text=args.amenities_text,
            contact_channel=args.contact_channel,
            contact_email=args.contact_email,
            payment_method=payment,
            viewing=args.viewing,
            deposit_before_viewing=args.deposit_before_viewing,
            deposit_before_lease=args.deposit_before_lease,
            landlord_abroad=args.landlord_abroad,
            cannot_show=args.cannot_show,
            duplicate_listing=args.duplicate_listing,
            listed_for_sale_elsewhere=args.listed_for_sale_elsewhere,
            urgency=args.urgency,
            name_mismatch=args.name_mismatch,
        )
    price = _load_price(listing, args.sample_csv, args.no_price_check)
    result = score_listing(listing, price=price)
    if args.json:
        print(json.dumps(_result_to_dict(result), indent=2))
    else:
        _print_result(result, listing)
    return 0


def _cmd_evaluate(args):
    from .evaluate import evaluate_file

    metrics = evaluate_file(args.labeled, args.sample_csv)
    if args.json:
        print(json.dumps(metrics, indent=2, default=str))
    else:
        print("RentTrust v0.1 -- labeled-set evaluation")
        print("Scam-pattern cases: %d" % metrics["n_scam_pattern"])
        print("  Flagged (CHECK or RED): %d (%.0f%% recall)"
              % (metrics["scam_flagged"], metrics["flag_recall_pct"]))
        print("  RED: %d (%.0f%%)" % (metrics["scam_red"], metrics["red_recall_pct"]))
        print("  Expected flags detected: %d/%d (%.0f%%)"
              % (metrics["expected_flags_detected"],
                 metrics["expected_flags_total"],
                 metrics["expected_flag_recall_pct"]))
        print("Legitimate cases: %d" % metrics["n_legitimate"])
        print("  Flagged (CHECK or RED): %d (%.0f%% false-positive rate)"
              % (metrics["legit_flagged"], metrics["false_positive_rate_pct"]))
        print("  RED: %d (%.0f%% false-positive rate for RED)"
              % (metrics["legit_red"], metrics["red_false_positive_rate_pct"]))
        print("")
        print("Note: n=%d total. These rates describe this small, "
              "reconstructed test set only -- not real-world accuracy."
              % metrics["n_total"])
        for case in metrics["cases"]:
            print("  %s [%s] -> %s (expected %s)"
                  % (case["id"], case["label"], case["tier"], case["expected_tier"]))
    return 0


def build_parser():
    parser = argparse.ArgumentParser(prog="renttrust")
    sub = parser.add_subparsers(dest="command", required=True)
    score_parser = sub.add_parser("score", help="Score one listing")
    _score_args(score_parser)
    score_parser.set_defaults(func=_cmd_score)
    eval_parser = sub.add_parser("evaluate", help="Evaluate on the labeled test set")
    eval_parser.add_argument("--labeled", default=None)
    eval_parser.add_argument("--sample-csv", default=None)
    eval_parser.add_argument("--json", action="store_true")
    eval_parser.set_defaults(func=_cmd_evaluate)
    return parser


def main(argv=None):
    parser = build_parser()
    args = parser.parse_args(argv)
    if getattr(args, "labeled", None) is None and args.command == "evaluate":
        args.labeled = DEFAULT_LABELED
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
