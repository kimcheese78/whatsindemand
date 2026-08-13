from app.services.data_quality import (
    evaluate_qualification, MIN_ROLE_ACTIVE, MIN_COHORT, MAX_CONCENTRATION,
)


def test_qualifies_when_all_floors_cleared():
    ok, reasons, conf = evaluate_qualification(active=120, cohort_size=18, top_share=0.15)
    assert ok is True
    assert reasons == []
    assert 0.0 <= conf <= 1.0


def test_fails_on_low_volume():
    ok, reasons, _ = evaluate_qualification(active=MIN_ROLE_ACTIVE - 1, cohort_size=18, top_share=0.1)
    assert ok is False
    assert any('volume' in r for r in reasons)


def test_fails_on_low_breadth():
    ok, reasons, _ = evaluate_qualification(active=200, cohort_size=MIN_COHORT - 1, top_share=0.1)
    assert ok is False
    assert any('breadth' in r for r in reasons)


def test_fails_on_concentration():
    ok, reasons, _ = evaluate_qualification(active=200, cohort_size=20, top_share=MAX_CONCENTRATION + 0.2)
    assert ok is False
    assert any('concentrated' in r for r in reasons)


def test_confidence_bounded_and_higher_for_stronger_data():
    _, _, weak = evaluate_qualification(active=55, cohort_size=10, top_share=0.29)
    _, _, strong = evaluate_qualification(active=400, cohort_size=40, top_share=0.05)
    assert 0.0 <= weak <= 1.0
    assert 0.0 <= strong <= 1.0
    assert strong > weak


def test_boundary_exactly_at_floors_qualifies():
    ok, reasons, _ = evaluate_qualification(active=MIN_ROLE_ACTIVE, cohort_size=MIN_COHORT,
                                            top_share=MAX_CONCENTRATION)
    assert ok is True, reasons
