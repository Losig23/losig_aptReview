"""Trust-flag rules and tiering for RentTrust.

Weights, from the FTC-style red flags in the README:
  strong -- deposit before viewing/lease, irreversible payment,
            landlord abroad who cannot show the unit, duplicate listing,
            listed for sale elsewhere, refusal of an accompanied viewing,
            rent 20%+ below the comparable median.
  weak / contextual -- urgency pressure, free-email contact, name
            mismatch. Weak flags never cause RED on their own.

Tiering (transparent, no hidden score):
  RED   -- 2 or more strong flags.
  CHECK -- 1 strong flag, or any weak / price-only flag, or any flag at all.
  GREEN -- no flags found.

A tier is not a verdict. GREEN still means "tour before paying";
RED means "multiple strong flags -- do not send money or personal
details until each flag is verified", not "this landlord is a scammer".

Deliberately absent: grammar / "foreign-sounding English" scoring.
Language quality is a biased and unreliable signal and it punishes
legitimate landlords. See README.md for why it is left out.
"""

from collections import namedtuple

# Payment methods where the money is effectively unrecoverable once sent.
IRREVERSIBLE_PAYMENTS = {
    "wire",
    "wire transfer",
    "wire-transfer",
    "gift card",
    "gift-card",
    "giftcard",
    "crypto",
    "cryptocurrency",
    "bitcoin",
    "western union",
    "western-union",
    "moneygram",
    "money gram",
}

FREE_EMAIL_DOMAINS = {
    "gmail.com",
    "yahoo.com",
    "outlook.com",
    "hotmail.com",
    "aol.com",
    "protonmail.com",
    "icloud.com",
    "mail.com",
    "gmx.com",
    "yandex.com",
}

# Phrases that indicate urgency pressure. Matching is substring-based on
# the listing text the user pastes in; it is a weak signal only.
URGENCY_PHRASES = (
    "act now",
    "act fast",
    "decide today",
    "decide now",
    "won't last",
    "will not last",
    "another applicant",
    "about to pay",
    "first come",
    "first served",
    "going fast",
    "don't miss",
    "do not miss",
    "must decide",
    "urgent",
    "immediately",
    "today only",
)

VERIFICATION_CHECKLIST = [
    "Tour in person, or have someone you trust tour, before paying anything.",
    "Check county property-tax / assessor records to confirm who owns the property.",
    "Reverse-image search the listing photos to check whether they were copied from elsewhere.",
    "Never wire money, or pay by gift card or crypto, before a signed lease and a viewing.",
    "Never send SSN, bank details, or ID copies before you have verified the listing and the landlord.",
]

Flag = namedtuple("Flag", ["id", "weight", "title", "detail", "verify"])
PriceComparison = namedtuple(
    "PriceComparison",
    [
        "basis",
        "n",
        "median_rent",
        "median_rent_per_sqft",
        "listing_rent",
        "listing_rent_per_sqft",
        "pct_below_median_rent",
        "pct_below_median_per_sqft",
        "flagged",
    ],
)
ScoreResult = namedtuple(
    "ScoreResult", ["tier", "flags", "price", "checklist", "disclaimer"]
)

DISCLAIMER = (
    "RentTrust flags patterns that warrant verification. It does not "
    "determine whether a listing is genuine and it does not accuse any "
    "named person of wrongdoing. Verify each flag before proceeding."
)

TIER_DESCRIPTIONS = {
    "GREEN": "No major flags found. Still tour before paying.",
    "CHECK": "Flags found. Verify before proceeding.",
    "RED": "Multiple strong flags. Do not send money or personal details "
    "until each flag is verified.",
}


class Listing(object):
    """A listing as entered by the user. No SSN, bank, or ID fields exist."""

    def __init__(
        self,
        rent=None,
        beds=None,
        baths=None,
        sqft=None,
        neighborhood="",
        city="San Francisco",
        listing_text="",
        amenities_text="",
        contact_channel="",
        contact_email="",
        payment_method="",
        viewing="in-person",
        deposit_before_viewing=False,
        deposit_before_lease=False,
        landlord_abroad=False,
        cannot_show=False,
        duplicate_listing=False,
        listed_for_sale_elsewhere=False,
        urgency=False,
        name_mismatch=False,
    ):
        self.rent = rent
        self.beds = beds
        self.baths = baths
        self.sqft = sqft
        self.neighborhood = neighborhood
        self.city = city
        self.listing_text = listing_text or ""
        self.amenities_text = amenities_text or ""
        self.contact_channel = contact_channel or ""
        self.contact_email = contact_email or ""
        self.payment_method = payment_method or ""
        self.viewing = (viewing or "in-person").strip().lower()
        self.deposit_before_viewing = bool(deposit_before_viewing)
        self.deposit_before_lease = bool(deposit_before_lease)
        self.landlord_abroad = bool(landlord_abroad)
        self.cannot_show = bool(cannot_show)
        self.duplicate_listing = bool(duplicate_listing)
        self.listed_for_sale_elsewhere = bool(listed_for_sale_elsewhere)
        self.urgency = bool(urgency)
        self.name_mismatch = bool(name_mismatch)

    @classmethod
    def from_dict(cls, data):
        data = dict(data or {})
        # Accept both spellings used by the demo JSON files.
        if "deposit_before_viewing_or_lease" in data:
            data.setdefault("deposit_before_viewing", data["deposit_before_viewing_or_lease"])
        return cls(**{k: v for k, v in data.items() if k in _LISTING_FIELDS})

    def to_dict(self):
        return {
            "rent": self.rent,
            "beds": self.beds,
            "baths": self.baths,
            "sqft": self.sqft,
            "neighborhood": self.neighborhood,
            "city": self.city,
            "listing_text": self.listing_text,
            "amenities_text": self.amenities_text,
            "contact_channel": self.contact_channel,
            "contact_email": self.contact_email,
            "payment_method": self.payment_method,
            "viewing": self.viewing,
            "deposit_before_viewing": self.deposit_before_viewing,
            "deposit_before_lease": self.deposit_before_lease,
            "landlord_abroad": self.landlord_abroad,
            "cannot_show": self.cannot_show,
            "duplicate_listing": self.duplicate_listing,
            "listed_for_sale_elsewhere": self.listed_for_sale_elsewhere,
            "urgency": self.urgency,
            "name_mismatch": self.name_mismatch,
        }


_LISTING_FIELDS = {
    "rent",
    "beds",
    "baths",
    "sqft",
    "neighborhood",
    "city",
    "listing_text",
    "amenities_text",
    "contact_channel",
    "contact_email",
    "payment_method",
    "viewing",
    "deposit_before_viewing",
    "deposit_before_lease",
    "landlord_abroad",
    "cannot_show",
    "duplicate_listing",
    "listed_for_sale_elsewhere",
    "urgency",
    "name_mismatch",
}


def _normalize_payment(method):
    return " ".join((method or "").strip().lower().replace("-", " ").replace("_", " ").split())


def _email_domain(email):
    email = (email or "").strip().lower()
    if "@" not in email:
        return ""
    return email.rsplit("@", 1)[-1]


def _has_urgency(listing):
    if listing.urgency:
        return True
    text = (listing.listing_text + " " + listing.amenities_text).lower()
    return any(phrase in text for phrase in URGENCY_PHRASES)


def detect_flags(listing, price=None):
    """Return the list of flags for a listing, in a stable order."""
    flags = []

    if listing.deposit_before_viewing or listing.deposit_before_lease:
        flags.append(
            Flag(
                "deposit_before_viewing_or_lease",
                "strong",
                "Deposit requested before viewing or signed lease",
                "A deposit or first month's rent is requested before you "
                "have viewed the unit or signed a lease.",
                "Do not pay until you have viewed the unit and have a "
                "signed lease. Confirm the recipient owns or manages it.",
            )
        )

    if _normalize_payment(listing.payment_method) in IRREVERSIBLE_PAYMENTS:
        flags.append(
            Flag(
                "irreversible_payment",
                "strong",
                "Irreversible payment requested",
                "Payment is requested by wire transfer, gift card, crypto, "
                "or a similar method that is hard or impossible to reverse.",
                "Use a traceable, reversible payment method only after a "
                "viewing and a signed lease.",
            )
        )

    if listing.landlord_abroad and listing.cannot_show:
        flags.append(
            Flag(
                "landlord_abroad_cannot_show",
                "strong",
                "Landlord abroad and cannot show the unit",
                "The landlord is described as out of the country and "
                "cannot show the unit in person or by live video.",
                "Ask for a local agent or trusted person to show the unit, "
                "and verify ownership in county property-tax records.",
            )
        )

    if listing.duplicate_listing:
        flags.append(
            Flag(
                "duplicate_listing",
                "strong",
                "Same listing under different names or details",
                "This listing also appears elsewhere under different names "
                "or with different details.",
                "Compare the listings side by side and check which, if any, "
                "matches the property-tax owner and a real showing.",
            )
        )

    if listing.listed_for_sale_elsewhere:
        flags.append(
            Flag(
                "listed_for_sale_elsewhere",
                "strong",
                "Property listed for sale elsewhere",
                "The same property is listed for sale, not for rent, "
                "somewhere else.",
                "Check county records and the sale listing; a for-sale "
                "home offered for rent needs extra verification.",
            )
        )

    if listing.viewing in ("none", "self-tour", "self_tour", "tour it yourself"):
        if listing.viewing == "none":
            detail = "No viewing is offered -- neither in person nor by live video."
        else:
            detail = (
                "Only a self-tour is offered -- no accompanied in-person "
                "or live-video viewing of the inside of the unit."
            )
        flags.append(
            Flag(
                "viewing_refused",
                "strong",
                "No accompanied viewing offered",
                detail,
                "Do not pay before an accompanied viewing. Have someone "
                "you trust tour if you cannot go yourself.",
            )
        )

    if price is not None and price.get("flagged"):
        pct = price.get("pct_below_median_rent")
        median = price.get("median_rent")
        basis = price.get("basis")
        basis_text = ""
        if basis is not None:
            basis_text = " (%s, n=%d)" % (basis.kind, basis.n)
        flags.append(
            Flag(
                "price_below_median",
                "strong",
                "Rent well below the comparable median",
                "This rent is %.1f%% below the median rent of $%.0f%s."
                % (pct if pct is not None else 0.0, median or 0, basis_text),
                "Ask why the rent is below market, and verify ownership "
                "and viewing before proceeding -- low rent alone is not "
                "proof of anything, but it warrants a check.",
            )
        )

    if _has_urgency(listing):
        flags.append(
            Flag(
                "urgency_pressure",
                "weak",
                "Urgency pressure",
                "The listing or messages pressure a fast decision "
                "(for example, 'decide today' or 'another applicant is "
                "about to pay').",
                "Take the time to verify anyway. Pressure to decide fast "
                "is a reason to slow down, not to pay faster.",
            )
        )

    if _email_domain(listing.contact_email) in FREE_EMAIL_DOMAINS:
        flags.append(
            Flag(
                "free_email_contact",
                "weak",
                "Free-email contact",
                "The contact uses a free email provider. Many legitimate "
                "landlords do this too, so this is contextual only.",
                "Cross-check the contact against the property manager or "
                "owner on record, and prefer a showing through a verifiable channel.",
            )
        )

    if listing.name_mismatch:
        flags.append(
            Flag(
                "name_mismatch",
                "weak",
                "Contact name does not match",
                "The name used in the listing or messages does not match "
                "the name on the contact account or documents.",
                "Ask which name is on the lease and in county records, "
                "and confirm they match before paying.",
            )
        )

    return flags


def tier_for_flags(flags):
    strong = sum(1 for flag in flags if flag.weight == "strong")
    if strong >= 2:
        return "RED"
    if flags:
        return "CHECK"
    return "GREEN"


def score_listing(listing, price=None):
    """Score a listing. ``price`` is the dict returned by price.compare_price."""
    flags = detect_flags(listing, price=price)
    price_obj = None
    if price is not None:
        price_obj = PriceComparison(
            basis=price.get("basis"),
            n=price.get("n", 0),
            median_rent=price.get("median_rent"),
            median_rent_per_sqft=price.get("median_rent_per_sqft"),
            listing_rent=price.get("listing_rent"),
            listing_rent_per_sqft=price.get("listing_rent_per_sqft"),
            pct_below_median_rent=price.get("pct_below_median_rent"),
            pct_below_median_per_sqft=price.get("pct_below_median_per_sqft"),
            flagged=price.get("flagged", False),
        )
    return ScoreResult(
        tier=tier_for_flags(flags),
        flags=flags,
        price=price_obj,
        checklist=list(VERIFICATION_CHECKLIST),
        disclaimer=DISCLAIMER,
    )
