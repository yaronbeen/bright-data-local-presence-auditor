# Local Presence Auditor

An evidence-first audit of fields returned for public Google Maps listings. It is **not** a Google Business Profile (formerly Google My Business) API client, cannot access account-private profile data, and never changes a listing.

## What it helps with

Review a small agency/client-provided set of Maps listing URLs and flag whether selected observed fields (address, phone, website, category) were returned. It also carries through public rating and review count when supplied. This creates a human-review checklist, not a definitive completeness verdict.

## Verified integration and architecture

Bright Data documents a Google Scraper API with Google Maps full-info dataset `gd_m8ebnr0q2qlklc02fz` and a separate Google Maps Reviews dataset `gd_luzfs1dn2oa0teb81`. This demo calls only the Maps full-info dataset for supplied URLs. It does not call a Google Business Profile API or claim profile ownership verification. A field missing from a scrape can mean not returned, not necessarily absent on the live listing.

Flow: `CSV Maps URLs -> Bright Data Google Maps dataset -> observed field checks -> JSON/CSV`. Offline sample records use the same audit logic. Python 3.10+ standard library runtime.

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
```

For live lookups create CSV with a `url` column containing public `google.com/maps` listing URLs:

```bash
python auditor.py listings.csv audit.json
python auditor.py listings.csv audit.json --dry-run
```

Dry-run validates local URL shape and makes no API call. Synchronous collection is capped at the documented 20 URLs per request. Live requests can incur per-record charges; review current [Web Scraper pricing](https://brightdata.com/pricing/web-scraper), product billing, and your plan first. Long-running responses may return async snapshot IDs, which this intentionally bounded demo reports as unsupported rather than polling invisibly. Reviews are not fetched: the separate product requires a separately scoped integration/cost.

## Output schema

`listing_name`, `source_url`, `address`, `phone`, `website`, `category`, `rating`, `reviews_count`, `missing_observed_fields`, `observed_fields_status`, `checked_at`, `scope_note`. Status is `all_selected_fields_returned` only when all four selected observation fields were returned; otherwise `some_selected_fields_not_returned`. It says nothing about opening hours, service areas, ownership, verification, policy compliance, or whether a field is actually absent.

## Privacy and platform boundaries

Only user-supplied public listing URLs. No account login, profile editing, verification, review replies, access-control bypass, collection of customer/reviewer identities, or outreach. Public visibility is not authorization. Obtain appropriate client authorization, minimize retained data, follow applicable platform terms/law, and honor corrections/deletions. The tool does not assert legal or Google policy compliance.

## Troubleshooting and tests

- Missing key: offline JSON and dry-run work without credentials.
- URL rejected: use an HTTPS Google Maps listing URL, not a search or unrelated page.
- HTTP 401/403: confirm key and Google Maps dataset access.
- HTTP 429: stop and reduce request rate.
- Missing fields: inspect the primary source; the API output may be incomplete or changed.
- Async response: this example is limited to synchronous URL collections.

```bash
python3 -m pytest -q
```

Tests include observed/missing distinction, unsafe URL rejection, and field limits. Samples are illustrative. MIT License.
