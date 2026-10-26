# RentTrust v0.1

A transparent, renter-side scorer for a rental listing. You paste in or
manually enter a listing, and it returns a **tier + reasons, never a
verdict**:

- **GREEN** — no major flags found. Still tour before paying.
- **CHECK** — flags found. Verify before proceeding.
- **RED** — multiple strong flags. Do not send money or personal details
  until each flag is verified.

Every run also shows a verification checklist. RentTrust does not
determine whether a listing is genuine, and it never accuses a named
person of wrongdoing. Its output is always "flags warranting
verification."

## Quick start

Requires Python 3.9+ and nothing else (standard library only).

```bash
# A clean listing
python -m renttrust score --input demo/clean_listing.json

# A listing with multiple strong flags
python -m renttrust score --input demo/red_flag_listing.json

# Score a listing from the command line
python -m renttrust score --rent 2900 --beds 1 --sqft 680 \
  --neighborhood "Mission District" --viewing in-person --payment check

# Answer prompts instead of passing flags
python -m renttrust score --interactive

# JSON output
python -m renttrust score --input demo/red_flag_listing.json --json

# Evaluate on the labeled test set
python -m renttrust evaluate
```

Full CLI options: `python -m renttrust score --help`. The score command
accepts rent, beds, baths, sqft, neighborhood/city, listing text
(`--listing-text` or `--listing-file`), amenities text, landlord contact
channel and email, payment method requested, and viewing offered
(`in-person` / `live-video` / `none` / `self-tour`), plus explicit flags
such as `--deposit-before-viewing`, `--landlord-abroad`,
`--cannot-show`, `--duplicate-listing`, and
`--listed-for-sale-elsewhere`.

## What it does

**Price check.** Rent and rent/sqft are compared to a median computed
from `data/sample_listings.csv`, a manually entered sample of 37
listings across San Francisco, Oakland, Berkeley, and Daly City. The
comparison always shows its numbers, for example:

> Median for 1-bed in Mission District: $2,875. This listing: $1,750
> (39.1% below).

A price flag fires when rent is **20% or more below** the comparable
median rent, or rent/sqft is 20% or more below the comparable median
rent/sqft. Comparable selection prefers the same neighbourhood and bed
count, then the same city and bed count, then neighbourhood, then city
— and requires at least 3 rows. If no comparable set exists, **no price
flag is raised**. Matching bed count before falling back to a
neighbourhood-wide median matters: a studio compared to a median that
mixes studios with two-bedrooms would look "cheap" just for being
small.

**Trust flags, weighted.** Strong flags (each counts toward RED):

- Deposit or first month requested **before** a viewing or signed lease
- Payment by wire transfer, gift card, crypto, or a similar
  irreversible method
- Landlord described as out of the country **and** unable to show the
  unit (abroad alone, with a local agent showing the unit, is not a flag)
- Same listing under different names or details elsewhere
- Property listed **for sale** elsewhere
- No accompanied viewing offered (`none`, or `self-tour` only)
- Rent 20%+ below the comparable median (see above)

Weak / contextual flags (never decisive alone, never cause RED):

- Urgency pressure ("decide today", "another applicant is about to pay")
- Free-email contact (many legitimate landlords use Gmail too)
- Contact name mismatch

**Tiering (no hidden score).** RED = 2 or more strong flags. CHECK =
any flag at all, including a single strong flag or weak flags only.
GREEN = no flags found. A single strong flag is CHECK, not RED, and
weak flags alone can only ever produce CHECK.

**Verification checklist, always shown:**

1. Tour in person, or have someone you trust tour, before paying anything.
2. Check county property-tax / assessor records to confirm who owns the property.
3. Reverse-image search the listing photos to check whether they were copied from elsewhere.
4. Never wire money, or pay by gift card or crypto, before a signed lease and a viewing.
5. Never send SSN, bank details, or ID copies before you have verified the listing and the landlord.

## What it does NOT do

- It does not say a listing is genuine or fraudulent, and it does not
  accuse any named landlord of being a scammer.
- It does not scrape listing sites. v0.1 is manual entry / paste only.
  Any future scraping step must first check the site's terms and get
  explicit approval.
- It does not verify ownership, identity, or photos itself. It tells
  you which checks to run; you (or someone you trust) run them.
- It does not score grammar, spelling, or "foreign-sounding English."
  See below.
- It does not collect, store, or accept SSN, bank details, driver's
  license, or other ID data. There is no field for them. Do not paste
  personal data into a listing.

## Why grammar is not scored

Language quality is a biased and unreliable signal. It punishes
legitimate landlords who write in a second language, people writing
quickly on a phone, and anyone whose English differs from the
reviewer's expectations, while fluent scammers pass it easily. A flag
that systematically disadvantages one group of legitimate landlords
while missing fluent bad actors is worse than no flag. So RentTrust
leaves it out entirely — there is no grammar, spelling, or accent
check in the code, and a test pins that rule
(`test_no_grammar_or_language_flag_exists`).

## Evaluation

`data/labeled_test_set.json` holds 20 anonymized cases: 10
scam-pattern cases reconstructed from FTC-style red flags (not real
listings, not real victims, no real names) and 10 ordinary legitimate
listings. One legitimate case is deliberately borderline — a free-email
contact plus urgency wording — to show that weak flags alone produce
CHECK, never RED.

Running `python -m renttrust evaluate` reports:

| Metric | Result |
| --- | --- |
| Flag recall, scam-pattern cases (CHECK or RED) | 10/10 — 100% |
| RED recall, scam-pattern cases | 5/10 — 50% |
| Expected flags detected | 24/24 — 100% |
| False-positive rate, legitimate cases (CHECK or RED) | 1/10 — 10% |
| False-positive rate, legitimate cases (RED only) | 0/10 — 0% |

Read those numbers for what they are: performance on a small,
reconstructed test set, not real-world accuracy. The 50% RED recall is
honest, not a failure — five scam-pattern cases carry only one strong
flag each, and by design a single strong flag is CHECK, not RED. A
scorer that flagged everything would score 100% recall and be useless;
that is why recall and false-positive rate are always reported together.

## Sample data — read this before relying on a price check

`data/sample_listings.csv` (37 rows) is a manually entered **starter
sample** in market-range values for the SF Bay Area, not live scraped
listings and not a market index. It contains no personal data and no
landlord contact details — only city, neighbourhood, beds, baths,
sqft, and rent. Treat its medians as a sanity check, not a pricing
authority. For a real apartment hunt, replace it with your own manually
collected sample for the neighbourhoods you are actually considering
(same CSV columns), and the price check will use yours instead:
`python -m renttrust score ... --sample-csv path/to/your_sample.csv`.

## Limitations

- The sample is small (37 rows) and the medians move with it. A thin
  neighbourhood sample falls back to city-wide bed-count medians, and
  with fewer than 3 comparables no price flag is raised at all.
- Flags depend on what you enter. If a landlord's demand (wire payment,
  deposit before viewing) only appears in messages you do not paste
  in, the scorer cannot see it.
- Urgency detection is keyword-based on pasted text; it misses
  paraphrases and can trigger on quoted text. That is why it is weak
  only.
- Duplicate / for-sale detection is user-reported in v0.1 (you tick
  the box when you find the other listing). There is no automated
  cross-site matching yet.
- A GREEN tier is not a clean bill of health. It means no flags were
  found in what was entered — tour before paying, every time.
- A RED tier is not proof of fraud. It means multiple strong flags
  warrant verification before any money or personal details change hands.

## Project layout

```
renttrust/            Scoring rules, price comparison, CLI, evaluation
data/
  sample_listings.csv      Manually entered starter sample (37 rows)
  labeled_test_set.json    Anonymized labeled test set (20 cases)
demo/
  clean_listing.json       Example GREEN listing
  red_flag_listing.json    Example RED listing
tests/
  test_price.py            Price comparison and threshold tests
  test_flags.py            Every flag rule + tiering tests
  test_scorer.py           End-to-end + labeled-set evaluation tests
```

## Tests

```bash
python -m unittest discover -s tests -v
```

41 tests, standard library only, no network access.
