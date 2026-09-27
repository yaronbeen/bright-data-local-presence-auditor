import auditor
import json


def test_audit_only_reports_fields_present_or_missing_without_inference():
    rows = auditor.audit([{"name": "Cafe", "url": "https://maps.google.com/?cid=1", "address": "Main St", "phone": "+1", "website": "https://cafe.example", "category": "Cafe", "rating": 4.2, "reviews_count": 17}])
    row = rows[0]
    assert row["listing_name"] == "Cafe"
    assert row["observed_fields_status"] == "all_selected_fields_returned"
    assert row["source_url"].startswith("https://")
    assert "hours" not in row


def test_missing_fields_are_unknown_not_listing_claims():
    row = auditor.audit([{"name": "Cafe", "url": "https://maps.google.com/?cid=1"}])[0]
    assert row["observed_fields_status"] == "some_selected_fields_not_returned"
    assert "address" in row["missing_observed_fields"]
    assert row["rating"] is None


def test_bad_url_rejected():
    try:
        auditor.validate_url("file:///etc/passwd")
    except ValueError:
        pass
    else:
        assert False, "non-Maps URLs must fail"


def test_maps_path_must_be_a_real_maps_route():
    for url in ("https://www.google.com/mapsfoo", "https://www.google.com/maps.evil.test/path", "https://www.google.com:444/maps/place/Cafe"):
        try:
            auditor.validate_url(url)
        except ValueError:
            continue
        assert False, f"invalid Maps route accepted: {url}"


def test_audit_rejects_malformed_records_cleanly():
    try:
        auditor.audit([7])
    except ValueError as exc:
        assert "object" in str(exc)
    else:
        assert False, "non-object records must fail with a validation error"


def test_whitespace_only_fields_are_not_counted_as_observed():
    row = auditor.audit([{"name": "Cafe", "address": "   ", "phone": "0", "website": "https://x.test", "category": "Cafe"}])[0]
    assert "address" in row["missing_observed_fields"]
    assert "phone" not in row["missing_observed_fields"]


def test_website_alias_counts_as_returned_field():
    row = auditor.audit([{"name": "Cafe", "address": "Main St", "phone": "0", "open_website": "https://cafe.example", "category": "Cafe"}])[0]
    assert "website" not in row["missing_observed_fields"]
    assert row["website"] == "https://cafe.example"


def test_live_csv_rejects_missing_url_as_cli_error(tmp_path):
    source = tmp_path / "listings.csv"
    source.write_text("url,name\nhttps://www.google.com/maps/place/Cafe,Cafe\n,Missing URL\n")
    assert auditor.main([str(source), str(tmp_path / "out.json"), "--live"]) == 2


def test_sync_collection_limit_is_explicit():
    try:
        auditor.collect(["https://www.google.com/maps/place/Cafe"] * 21, "token")
    except ValueError as exc:
        assert "20" in str(exc)
    else:
        assert False, "sync collector must reject more than 20 URLs"


def test_review_triage_is_public_operations_audit_not_response_status():
    report = auditor.triage_reviews([
        {"place_id": "p1", "place_name": "Cafe", "reviewer_name": "Review User", "reviewer_url": "https://www.google.com/maps/contrib/123", "reviewer_id": "reviewer-123", "rating": 1, "review_text": "Very long wait and rude staff", "review_date": "2026-09-20T10:00:00Z"},
        {"place_id": "p1", "place_name": "Cafe", "rating": 5, "review_text": "Lovely coffee", "review_date": "2026-09-21T10:00:00Z"},
    ])
    assert report["summary"]["reviews"] == 2
    assert report["summary"]["low_rating_reviews"] == 1
    assert "response_status" not in report["reviews"][0]
    assert "reviewer_name" not in report["reviews"][0]
    assert "reviewer_url" not in report["reviews"][0]
    assert "reviewer_id" not in report["reviews"][0]
    assert "wait_time" in report["reviews"][0]["themes"]


def test_reviews_collector_uses_documented_dataset_and_days_limit(monkeypatch):
    captured = {}

    class Response:
        def __enter__(self): return self
        def __exit__(self, *args): return False
        def read(self): return b'[]'

    def fake_urlopen(request, timeout):
        from urllib.parse import parse_qs, urlsplit
        captured["query"] = parse_qs(urlsplit(request.full_url).query)
        captured["payload"] = json.loads(request.data)
        return Response()

    monkeypatch.setattr(auditor, "urlopen", fake_urlopen)
    auditor.collect_reviews(["https://www.google.com/maps/place/Cafe"], "test-key", 30)
    assert captured["query"]["dataset_id"] == [auditor.REVIEWS_DATASET]
    assert captured["payload"] == {"input": [{"url": "https://www.google.com/maps/place/Cafe", "days_limit": 30}]}


def test_review_option_requires_live_listing_urls(capsys):
    assert auditor.main(["sample_listings.json", "/tmp/review-test.json", "--reviews"]) == 2
    assert "requires explicit --live" in capsys.readouterr().err.lower()


def test_reviews_dry_run_reports_dataset_calls_not_record_count(tmp_path, capsys):
    source = tmp_path / "places.csv"
    source.write_text("url\nhttps://www.google.com/maps/place/Cafe\nhttps://www.google.com/maps/place/Bakery\n")
    assert auditor.main([str(source), str(tmp_path / "out.json"), "--live", "--reviews", "--dry-run"]) == 0
    assert "2 dataset API call(s) planned" in capsys.readouterr().out


def test_live_mode_is_explicit_and_validates_every_url_before_collection(tmp_path, monkeypatch):
    source = tmp_path / "places.csv"
    source.write_text("url\nhttps://www.google.com/maps/place/Cafe\nhttps://google.com.evil.test/maps/place/Bad\n")
    monkeypatch.setattr(auditor, "collect", lambda *args: (_ for _ in ()).throw(AssertionError("request happened before validation")))
    assert auditor.main([str(source), "--live", "--dry-run"]) == 2


def test_url_only_input_without_live_flag_never_collects(tmp_path, monkeypatch, capsys):
    source = tmp_path / "places.csv"
    source.write_text("url\nhttps://www.google.com/maps/place/Cafe\n")
    monkeypatch.setattr(auditor, "collect", lambda *args: (_ for _ in ()).throw(AssertionError("unexpected live request")))
    assert auditor.main([str(source), str(tmp_path / "out.json")]) == 2
    assert "--live" in capsys.readouterr().err


def test_csv_formula_values_are_neutralized(tmp_path):
    import json
    source = tmp_path / "input.json"
    source.write_text(json.dumps([{"name": "=HYPERLINK(\"x\")"}]))
    assert auditor.main([str(source), str(tmp_path / "safe.csv")]) == 0
    assert "'=HYPERLINK" in (tmp_path / "safe.csv").read_text()


def test_listing_collect_request_uses_documented_body(monkeypatch):
    captured = {}
    class Response:
        def __enter__(self): return self
        def __exit__(self, *args): return False
        def read(self): return b'[]'
    def fake_urlopen(request, timeout):
        captured["payload"] = json.loads(request.data)
        return Response()
    monkeypatch.setattr(auditor, "urlopen", fake_urlopen)
    auditor.collect(["https://www.google.com/maps/place/Cafe"], "token")
    assert captured["payload"] == {"input": [{"url": "https://www.google.com/maps/place/Cafe"}]}
