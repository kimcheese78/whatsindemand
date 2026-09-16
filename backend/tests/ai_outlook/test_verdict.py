from app.services.ai_verdict import decide_verdict, LENS_PHRASE


def test_growing_when_bls_strongly_positive():
    v = decide_verdict(role_plural="software engineers", ai_pct=34,
                       total=17151, bls_pct=15.0, bls_period="2024 to 2034")
    assert v["stance"] == "no"
    assert v["diverges"] is False
    assert "aren't being replaced" in v["headline"].lower() or "not being replaced" in v["headline"].lower()
    assert "15%" in v["detail"]
    assert "34%" in v["detail"]
    assert LENS_PHRASE in v["detail"]


def test_flat_when_bls_near_zero():
    v = decide_verdict(role_plural="accountants", ai_pct=20,
                       total=472, bls_pct=1.0, bls_period="2024 to 2034")
    assert v["stance"] == "unlikely"
    assert v["diverges"] is False
    assert "20%" in v["detail"]


def test_contested_when_bls_declines_but_still_hiring():
    v = decide_verdict(role_plural="paralegals", ai_pct=12,
                       total=310, bls_pct=-8.0, bls_period="2024 to 2034")
    assert v["stance"] == "contested"
    assert v["diverges"] is True
    # Two-horizon: names both the decline and the live openings, plainly.
    assert "8%" in v["detail"]
    assert "310" in v["detail"]
    assert "both be true" in v["detail"].lower()


def test_adoption_only_when_bls_unmapped():
    v = decide_verdict(role_plural="prompt engineers", ai_pct=61,
                       total=140, bls_pct=None)
    assert v["stance"] == "adoption_only"
    assert v["diverges"] is False
    assert "61%" in v["detail"]
    assert LENS_PHRASE in v["detail"]
    # No fabricated projection when we don't have one.
    assert "project" not in v["headline"].lower()


def test_numbers_are_plain_no_jargon():
    v = decide_verdict(role_plural="data scientists", ai_pct=45,
                       total=820, bls_pct=36.0, bls_period="2024 to 2034")
    for text in (v["headline"], v["detail"]):
        low = text.lower()
        for banned in ("cagr", "augmentation", "leverage", "synerg", "utilize"):
            assert banned not in low
