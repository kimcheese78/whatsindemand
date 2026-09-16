from app.services.ai_verdict import bls_for


SAMPLE = {
    "15-1252": {"pct": 15.0, "period": "2024 to 2034", "employment_base": 1692100},
}


def test_returns_record_for_known_code():
    rec = bls_for("15-1252", table=SAMPLE)
    assert rec["pct"] == 15.0
    assert rec["period"] == "2024 to 2034"


def test_returns_none_for_unknown_code():
    assert bls_for("99-9999", table=SAMPLE) is None


def test_returns_none_for_missing_code():
    assert bls_for(None, table=SAMPLE) is None


def test_default_table_loads_from_json():
    # Should not raise; the shipped JSON must be valid and a dict.
    result = bls_for("does-not-exist")
    assert result is None
