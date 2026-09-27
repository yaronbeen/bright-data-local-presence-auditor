import auditor


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
    for url in ("https://www.google.com/mapsfoo", "https://www.google.com/maps.evil.test/path"):
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


def test_live_csv_rejects_missing_url_as_cli_error(tmp_path):
    source = tmp_path / "listings.csv"
    source.write_text("url,name\nhttps://www.google.com/maps/place/Cafe,Cafe\n,Missing URL\n")
    assert auditor.main([str(source), str(tmp_path / "out.json")]) == 2


def test_sync_collection_limit_is_explicit():
    try:
        auditor.collect(["https://www.google.com/maps/place/Cafe"] * 21, "token")
    except ValueError as exc:
        assert "20" in str(exc)
    else:
        assert False, "sync collector must reject more than 20 URLs"
