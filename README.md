# Bright Data Google Maps Public Listing & Review Audit

**Repository:** [bright-data-local-presence-auditor](https://github.com/yaronbeen/bright-data-local-presence-auditor) · **Data provider:** [Bright Data](https://brightdata.com/)

**Auditing several client Google Maps listings?** This CLI gives a local-marketing agency a consistent checklist of selected fields returned for supplied public listing URLs and, optionally, a human triage queue for returned public reviews. It helps decide which listings or reviews deserve manual verification. It is **not** a Google Business Profile API client and cannot verify ownership or edit a profile.

## What it helps with

For an agency or local-marketing operator, check which selected fields were returned for client-provided public Google Maps URLs and optionally sort returned public review records into a human triage queue. “Not returned” is an API observation, not a confirmed defect on the live listing. Review collection is a separate Bright Data Google Maps Reviews dataset request. This creates an audit checklist, not a Google Business Profile workflow or automated reputation-management system.

## Example: returned fields to a manual checklist

An agency receives five public Maps listing URLs from a client before a local campaign. It runs the listing audit, then reviews the `missing_observed_fields` column. Synthetic illustration: if `phone` was not returned for two of the five URLs, the useful action is to open those two sources and verify the client-provided details before updating an internal checklist. The result is **not** proof that the live listings lack phone numbers; “not returned” can reflect incomplete source data.

If the agency also opts into review collection, returned reviews are separately grouped by simple text themes and rating-based triage labels. For example, a low-rated record matching the literal “wait” cue can be routed for a person to read in context. The tool does not know whether an owner replied, diagnose root causes, or post a response.

Offline examples (no Bright Data request):

```bash
python3 auditor.py sample_listings.json audit.json
python3 auditor.py sample_listings.json reviews-audit.json --reviews-file sample_reviews.json
```

The first writes listing observations. The second adds an offline review-triage report. Live listing collection and live review collection are separate explicit options; live review collection makes an additional dataset request and may incur additional charges.

## Verified integration and architecture

Bright Data documents a Google Scraper API with Google Maps full-info dataset `gd_m8ebnr0q2qlklc02fz` and separate Reviews dataset `gd_luzfs1dn2oa0teb81`. Listing checks and optional reviews are distinct calls and can each incur charges. Review records document public rating, text, date, and place identifiers; this tool does not infer owner-response status because that field is not in the documented response example. It does not call Google Business Profile APIs or claim ownership verification. Missing listing fields mean not returned, not necessarily absent.

Flow: `explicit --live + CSV Maps URLs -> Bright Data Google Maps dataset -> observed field checks -> JSON/CSV`. Offline sample records use the same audit logic. Python 3.10+ standard library runtime.

## Setup

```bash
python3 -m venv .venv && . .venv/bin/activate
pip install -r requirements-dev.txt
cp .env.example .env
```

Create a key from [Bright Data account settings](https://brightdata.com/cp/setting/users), then export `BRIGHT_DATA_API_KEY`. Credentials are read from the process environment only. Official references: [Google Scraper API](https://docs.brightdata.com/products/scrapers/google/introduction.md), [Google Maps collect by URL](https://docs.brightdata.com/api-reference/scrapers/search-engines-apis/google-maps-collect-by-url), [Google Maps reviews](https://docs.brightdata.com/api-reference/scrapers/search-engines-apis/google-maps-reviews-collect-by-url), [sync/async requests](https://docs.brightdata.com/products/scrapers/scrapers-library/async-requests.md).

## Run

```bash
python auditor.py sample_listings.json audit.json
python auditor.py sample_listings.json audit.csv
python auditor.py sample_listings.json reviews-audit.json --reviews-file sample_reviews.json
```

For live lookups create CSV with a `url` column containing public `google.com/maps` listing URLs:

```bash
python auditor.py listings.csv audit.json --live
python auditor.py listings.csv audit.json --live --dry-run
python auditor.py listings.csv reviews-audit.json --live --reviews --review-days 30
```

All public URL collection requires explicit `--live`; URL-only input without it is rejected. Dry-run with `--live` validates every URL and prints the planned dataset-call count but makes no API call. Synchronous collection is capped at the documented 20 URLs per request. `--reviews` also requires `--live`, makes a second request to the separate Reviews dataset, and passes `--review-days` (default 30) as Bright Data's documented `days_limit` input. This asks the dataset to limit review age; it is not a local post-fetch date filter or a guarantee of complete coverage/recency. The report reflects only returned rows and their returned dates; inspect `review_date` values. Review retrieval is an additional billable operation. Review current [Web Scraper pricing](https://brightdata.com/pricing/web-scraper), product billing, and your plan before live runs. Long-running responses may return async snapshot IDs, which this bounded demo reports as unsupported rather than polling invisibly.

## Output schema

`listing_name`, `source_url`, `address`, `phone`, `website`, `category`, `rating`, `reviews_count`, `missing_observed_fields`, `observed_fields_status`, `checked_at`, `scope_note`. Status is `all_selected_fields_returned` only when all four selected observation fields were returned; otherwise `some_selected_fields_not_returned`. This is a returned-field checklist for the client-supplied URL, not a claim that the listing is deficient. It says nothing about opening hours, service areas, ownership, verification, policy compliance, or whether a field is actually absent. CSV formula-leading text is prefixed to reduce spreadsheet formula injection risk.

Illustrative decision: if `phone` was not returned for two of five supplied listings, route those URLs for manual source verification. Do not treat the count as proof that either live listing lacks a phone number.

When review mode is used, JSON additionally contains `review_operations.summary`, per-location review and low-rating counts, and review triage rows with `rating`, returned `review_date`, `themes`, and a shortened `review_excerpt`. Ratings 1–2 are flagged for priority human review and 3-star reviews for monitoring. These are sorting rules, not sentiment truth or response-status indicators. The report does not assert a guaranteed date range; the request's `days_limit` is advisory to the dataset and the output reflects only records actually returned.

## How this differs from existing tools

Unlike `bright-data-google-maps-scraper`, which supports place discovery/collection and data export, this project is a client-URL returned-field checklist plus a theme-based review triage queue. The integration boundary is public Google Maps scraper data only: it does not use the Google Business Profile (GBP/GMB) API, access private owner data, verify ownership, track owner replies, respond to reviews, or edit listings. URL-only input requires `--live`; the checklist never labels a non-returned field a confirmed listing problem.

## Privacy and platform boundaries

Only user-supplied public listing URLs. No account login, profile editing, verification, review replies, access-control bypass, identity enrichment, profiling, or outreach. Bright Data's documented review example contains reviewer name/URL fields. The adapter allowlists location ID/name, rating, date, themes, and a shortened excerpt; it discards reviewer name, URL, and any unrecognized reviewer identifier fields from normalized output and never saves the raw response. Public visibility is not authorization. Obtain appropriate client authorization, minimize retained data, follow applicable platform terms/law, and honor corrections/deletions. The tool does not assert legal or Google policy compliance.

## Troubleshooting and tests

- Missing key: offline JSON and dry-run work without credentials.
- URL rejected: use an HTTPS Google Maps listing URL, not a search or unrelated page.
- HTTP 401/403: confirm key and Google Maps dataset access.
- HTTP 429: stop and reduce request rate.
- Missing fields: inspect the primary source; the API output may be incomplete or changed.
- Async response: this example is limited to synchronous URL collections.
- Review collection is separate: `--live --reviews` adds a second dataset request and may add cost.

```bash
python3 -m pytest -q
```

Tests include observed/missing distinction, Maps route validation, malformed rows, review theme triage, separate review dataset request shape, and sync limits. Samples are illustrative. MIT License.

## FAQ

**Does this audit or edit a Google Business Profile account?** No. It uses public Google Maps scraper observations only. It cannot access private account data, verify ownership, edit listings, inspect owner response status, or reply to reviews.

**Does a missing field mean the listing is wrong?** No. It means the field was not returned by the dataset for that request. Verify it against the live source before treating it as an issue.

**Are reviews collected automatically with listing data?** No. `--reviews` is a separate live collection against a separate dataset and requires `--live`; it may incur another charge. `--reviews-file` is for local fixture review triage.

**Are review themes sentiment analysis?** No. Themes use simple literal word rules, and rating-based labels only prioritize human review. Read the excerpt and original source before drawing conclusions.

**Can I run the examples without credentials?** Yes. The supplied JSON examples and dry-run are local. Live collection requires a Bright Data API key and may incur charges.
