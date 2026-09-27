"""Audit publicly observed Google Maps listing fields; not a GMB API client."""
import argparse,csv,json,os,sys
from datetime import datetime,timezone
from pathlib import Path
from urllib.error import HTTPError,URLError
from urllib.parse import urlencode,urlsplit
from urllib.request import Request,urlopen

DATASET="gd_m8ebnr0q2qlklc02fz"
REVIEWS_DATASET="gd_luzfs1dn2oa0teb81"
REQUIRED=("address","phone","website","category")
FIELDS=["listing_name","source_url","address","phone","website","category","rating","reviews_count","missing_observed_fields","observed_fields_status","checked_at","scope_note"]
REVIEW_THEMES={"wait_time":("wait", "slow", "long line", "late"),"service":("service", "rude", "helpful", "friendly", "staff"),"cleanliness":("clean", "dirty", "hygiene"),"price":("price", "expensive", "overpriced", "value"),"quality":("quality", "broken", "poor", "excellent", "great")}

def validate_url(url):
    try:
        p=urlsplit(url)
        hostname=p.hostname
        port=p.port
    except (TypeError, ValueError):
        raise ValueError("Only public Google Maps HTTPS listing URLs are accepted") from None
    maps_path=p.path in {"/maps", "/maps/"} or p.path.startswith("/maps/")
    short_maps_url=hostname=="maps.google.com" and p.path in {"", "/"}
    if p.scheme!="https" or hostname not in {"google.com","www.google.com","maps.google.com"} or p.username or p.password or port not in {None,443} or not (maps_path or short_maps_url): raise ValueError("Only public Google Maps HTTPS listing URLs are accepted")
    return url

def field_present(value):
    return value is not None and (not isinstance(value,str) or bool(value.strip()))

def csv_safe(value):
    if isinstance(value, str) and value.lstrip(" \t\r\n\x00").startswith(("=", "+", "-", "@")): return "'" + value
    return value

def audit(records):
    if not isinstance(records, (list, tuple)) or any(not isinstance(record, dict) for record in records):
        raise ValueError("Listing records must be objects")
    output=[]; checked=datetime.now(timezone.utc).isoformat()
    for raw in records:
        selected={"address":raw.get("address"),"phone":raw.get("phone"),"website":raw.get("website") if field_present(raw.get("website")) else raw.get("open_website"),"category":raw.get("category")}
        missing=[field for field in REQUIRED if not field_present(selected[field])]
        output.append({"listing_name":raw.get("name") or "","source_url":raw.get("url") or "","address":selected["address"] if field_present(selected["address"]) else None,"phone":selected["phone"] if field_present(selected["phone"]) else None,"website":selected["website"] if field_present(selected["website"]) else None,"category":selected["category"] if field_present(selected["category"]) else None,"rating":raw.get("rating"),"reviews_count":raw.get("reviews_count"),"missing_observed_fields":missing,"observed_fields_status":"all_selected_fields_returned" if not missing else "some_selected_fields_not_returned","checked_at":checked,"scope_note":"Public Maps scraper observation only; missing means not returned, not proof absent. Not Google Business Profile API data."})
    return output

def triage_reviews(records):
    if not isinstance(records,(list,tuple)) or any(not isinstance(record,dict) for record in records):
        raise ValueError("Review records must be objects")
    normalized=[]
    for raw in records:
        text=str(raw.get("review_text") or "")
        lowered=text.lower()
        themes=[theme for theme,terms in REVIEW_THEMES.items() if any(term in lowered for term in terms)]
        rating=raw.get("rating")
        try: score=float(rating) if rating is not None else None
        except (TypeError,ValueError): score=None
        triage="priority_human_review" if score is not None and score <= 2 else "monitor" if score == 3 else "positive_or_unrated"
        normalized.append({"place_id":raw.get("place_id"),"place_name":raw.get("place_name"),"rating":score,"review_date":raw.get("review_date") or None,"themes":themes,"triage":triage,"review_excerpt":text[:300]})
    places={}
    for review in normalized:
        key=review["place_id"] or review["place_name"] or "unknown_location"
        summary=places.setdefault(key,{"place_id":review["place_id"],"place_name":review["place_name"],"review_count":0,"low_rating_count":0,"theme_counts":{}})
        summary["review_count"]+=1
        if review["triage"]=="priority_human_review": summary["low_rating_count"]+=1
        for theme in review["themes"]: summary["theme_counts"][theme]=summary["theme_counts"].get(theme,0)+1
    return {"summary":{"reviews":len(normalized),"locations":len(places),"low_rating_reviews":sum(1 for row in normalized if row["triage"]=="priority_human_review")},"locations":list(places.values()),"reviews":normalized,"caveat":"Public review triage cues only. No owner response status is available or inferred; excerpts and themes require human review. This is not automated reputation management."}

def collect(urls,key):
    if len(urls)>20: raise ValueError("Synchronous Google Maps collection supports at most 20 URLs")
    if not key: raise ValueError("Set BRIGHT_DATA_API_KEY for live collection")
    req=Request("https://api.brightdata.com/datasets/v3/scrape?"+urlencode({"dataset_id":DATASET,"format":"json"}),data=json.dumps({"input":[{"url":validate_url(u)} for u in urls]}).encode(),headers={"Authorization":"Bearer "+key,"Content-Type":"application/json"},method="POST")
    try:
        with urlopen(req,timeout=90) as response: data=json.loads(response.read())
    except HTTPError as e: raise RuntimeError("Bright Data returned HTTP "+str(e.code)) from None
    except (URLError,TimeoutError) as e: raise RuntimeError("Maps request failed: "+str(e)) from None
    if not isinstance(data,list): raise RuntimeError("Async snapshot response is not handled in this demo")
    return data

def collect_reviews(urls,key,days_limit):
    if len(urls)>20: raise ValueError("Synchronous Google Maps Reviews collection supports at most 20 URLs")
    if not key: raise ValueError("Set BRIGHT_DATA_API_KEY for live review collection")
    inputs=[{"url":validate_url(url),"days_limit":days_limit} for url in urls]
    req=Request("https://api.brightdata.com/datasets/v3/scrape?"+urlencode({"dataset_id":REVIEWS_DATASET,"format":"json"}),data=json.dumps({"input":inputs}).encode(),headers={"Authorization":"Bearer "+key,"Content-Type":"application/json"},method="POST")
    try:
        with urlopen(req,timeout=90) as response: data=json.loads(response.read())
    except HTTPError as e: raise RuntimeError("Bright Data Reviews API returned HTTP "+str(e.code)) from None
    except (URLError,TimeoutError) as e: raise RuntimeError("Maps Reviews request failed: "+str(e)) from None
    if not isinstance(data,list): raise RuntimeError("Async review snapshot response is not handled in this demo")
    return data

def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__); p.add_argument("input",help="JSON listing records or CSV with public Maps URLs"); p.add_argument("output",nargs="?",default="presence_audit.json"); p.add_argument("--live",action="store_true",help="Explicitly collect supplied public Maps URLs (may incur charges)"); p.add_argument("--reviews",action="store_true",help="Collect public reviews in an additional separately billable dataset request; requires --live"); p.add_argument("--reviews-file",help="Offline JSON fixture of review records"); p.add_argument("--review-days",type=int,default=30); p.add_argument("--dry-run",action="store_true"); a=p.parse_args(argv)
    try:
        if a.reviews and a.reviews_file: raise ValueError("choose live --reviews or offline --reviews-file, not both")
        if (a.reviews or a.reviews_file) and not a.output.lower().endswith(".json"): raise ValueError("review reports require a .json output path")
        if a.review_days<1: raise ValueError("--review-days must be at least 1")
        text=Path(a.input).read_text(encoding="utf-8"); rows=json.loads(text) if a.input.endswith(".json") else list(csv.DictReader(text.splitlines()))
        if not isinstance(rows,list) or any(not isinstance(r,dict) for r in rows): raise ValueError("input must be a JSON array or CSV")
        url_only=bool(rows) and all("url" in row and not any(field_present(row.get(field)) for field in ("address","phone","website","open_website","category","rating","reviews_count")) for row in rows)
        if a.reviews and not a.live: raise ValueError("--reviews requires explicit --live collection")
        if a.live:
            if not rows: raise ValueError("live collection requires at least one public Maps listing URL")
            if any(not field_present(row.get("url")) for row in rows): raise ValueError("every live input row must contain a public Maps URL")
            for row in rows: validate_url(row.get("url", ""))
        elif url_only: raise ValueError("URL-only input is not collected automatically; pass --live to explicitly request billable collection")
        if a.live and len(rows)>20: raise ValueError("Synchronous Maps collection supports at most 20 listing URLs")
        if a.dry_run:
            calls=int(a.live)+int(a.reviews)
            print(f"Dry run: {len(rows)} listing(s), {calls} dataset API call(s) planned; 0 requests made"); return 0
        urls=[r["url"] for r in rows] if a.live else []
        if a.live: rows=collect(urls,os.getenv("BRIGHT_DATA_API_KEY"))
        out=audit(rows)
        if a.reviews: reviews=triage_reviews(collect_reviews(urls,os.getenv("BRIGHT_DATA_API_KEY"),a.review_days))
        elif a.reviews_file:
            review_data=json.loads(Path(a.reviews_file).read_text(encoding="utf-8"))
            if not isinstance(review_data,list): raise ValueError("reviews file must contain a JSON array")
            reviews=triage_reviews(review_data)
        else: reviews=None
        if reviews is not None:
            report={"listings":out,"review_operations":reviews}
            Path(a.output).write_text(json.dumps(report,indent=2,ensure_ascii=False)+"\n",encoding="utf-8")
            print(f"Audited {len(out)} listings and triaged {reviews['summary']['reviews']} public reviews"); return 0
        if a.output.endswith(".csv"):
            with Path(a.output).open("w",newline="",encoding="utf-8") as f:
                w=csv.DictWriter(f,fieldnames=FIELDS); w.writeheader()
                for row in out:
                    row={**row,"missing_observed_fields":";".join(row["missing_observed_fields"])}
                    w.writerow({key:csv_safe(value) for key,value in row.items()})
        else: Path(a.output).write_text(json.dumps(out,indent=2,ensure_ascii=False)+"\n",encoding="utf-8")
        print(f"Audited {len(out)} public listing observation(s)"); return 0
    except (ValueError,OSError,RuntimeError,json.JSONDecodeError) as e: print("Error: "+str(e),file=sys.stderr); return 2

if __name__=="__main__": raise SystemExit(main())
