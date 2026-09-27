"""Audit publicly observed Google Maps listing fields; not a GMB API client."""
import argparse,csv,json,os,sys
from datetime import datetime,timezone
from pathlib import Path
from urllib.error import HTTPError,URLError
from urllib.parse import urlencode,urlsplit
from urllib.request import Request,urlopen

DATASET="gd_m8ebnr0q2qlklc02fz"
REQUIRED=("address","phone","website","category")
FIELDS=["listing_name","source_url","address","phone","website","category","rating","reviews_count","missing_observed_fields","observed_fields_status","checked_at","scope_note"]

def validate_url(url):
    try:
        p=urlsplit(url)
        hostname=p.hostname
        p.port
    except (TypeError, ValueError):
        raise ValueError("Only public Google Maps HTTPS listing URLs are accepted") from None
    maps_path=p.path in {"/maps", "/maps/"} or p.path.startswith("/maps/")
    short_maps_url=hostname=="maps.google.com" and p.path in {"", "/"}
    if p.scheme!="https" or hostname not in {"google.com","www.google.com","maps.google.com"} or p.username or p.password or not (maps_path or short_maps_url): raise ValueError("Only public Google Maps HTTPS listing URLs are accepted")
    return url

def audit(records):
    if not isinstance(records, (list, tuple)) or any(not isinstance(record, dict) for record in records):
        raise ValueError("Listing records must be objects")
    output=[]; checked=datetime.now(timezone.utc).isoformat()
    for raw in records:
        missing=[field for field in REQUIRED if not raw.get(field)]
        output.append({"listing_name":raw.get("name") or "","source_url":raw.get("url") or "","address":raw.get("address") or None,"phone":raw.get("phone") or None,"website":raw.get("website") or raw.get("open_website") or None,"category":raw.get("category") or None,"rating":raw.get("rating"),"reviews_count":raw.get("reviews_count"),"missing_observed_fields":missing,"observed_fields_status":"all_selected_fields_returned" if not missing else "some_selected_fields_not_returned","checked_at":checked,"scope_note":"Public Maps scraper observation only; missing means not returned, not proof absent. Not Google Business Profile API data."})
    return output

def collect(urls,key):
    if len(urls)>20: raise ValueError("Synchronous Google Maps collection supports at most 20 URLs")
    if not key: raise ValueError("Set BRIGHT_DATA_API_KEY for live collection")
    req=Request("https://api.brightdata.com/datasets/v3/scrape?"+urlencode({"dataset_id":DATASET,"format":"json"}),data=json.dumps([{"url":validate_url(u)} for u in urls]).encode(),headers={"Authorization":"Bearer "+key,"Content-Type":"application/json"},method="POST")
    try:
        with urlopen(req,timeout=90) as response: data=json.loads(response.read())
    except HTTPError as e: raise RuntimeError("Bright Data returned HTTP "+str(e.code)) from None
    except (URLError,TimeoutError) as e: raise RuntimeError("Maps request failed: "+str(e)) from None
    if not isinstance(data,list): raise RuntimeError("Async snapshot response is not handled in this demo")
    return data

def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__); p.add_argument("input",help="JSON listing records or CSV with public Maps URLs"); p.add_argument("output",nargs="?",default="presence_audit.json"); p.add_argument("--dry-run",action="store_true"); a=p.parse_args(argv)
    try:
        text=Path(a.input).read_text(encoding="utf-8"); rows=json.loads(text) if a.input.endswith(".json") else list(csv.DictReader(text.splitlines()))
        if not isinstance(rows,list) or any(not isinstance(r,dict) for r in rows): raise ValueError("input must be a JSON array or CSV")
        live=bool(rows) and "url" in rows[0] and not any("address" in r for r in rows)
        if live:
            for row in rows: validate_url(row.get("url", ""))
        if a.dry_run: print(f"Dry run: {len(rows)} listing(s); 0 requests made"); return 0
        if live: rows=collect([r["url"] for r in rows],os.getenv("BRIGHT_DATA_API_KEY"))
        out=audit(rows)
        if a.output.endswith(".csv"):
            with Path(a.output).open("w",newline="",encoding="utf-8") as f:
                w=csv.DictWriter(f,fieldnames=FIELDS); w.writeheader()
                for row in out: w.writerow({**row,"missing_observed_fields":";".join(row["missing_observed_fields"])})
        else: Path(a.output).write_text(json.dumps(out,indent=2,ensure_ascii=False)+"\n",encoding="utf-8")
        print(f"Audited {len(out)} public listing observation(s)"); return 0
    except (ValueError,OSError,RuntimeError,json.JSONDecodeError) as e: print("Error: "+str(e),file=sys.stderr); return 2

if __name__=="__main__": raise SystemExit(main())
